from __future__ import annotations

import json

import pytest

from runtime.ai_learning.checkpoint_store import CheckpointStore
from runtime.ai_learning.dataset_snapshots import CertifiedDatasetReader, hash_dataset
from runtime.ai_learning.model_registry import ModelRegistry
from runtime.ai_learning.training_pipeline import (
    DatasetCertificationError,
    TemporalSplitError,
    TrainingPipeline,
    TrainingRegistryError,
    TrainingResumeError,
)


CONFIG = {"algorithm": "contract-skeleton", "learning_rate": 0.1}


def _manifest(dataset_path: str, dataset_hash: str) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "EXP-INF4-001",
        "verdict": "PASS",
        "gate": "PASS",
        "dataset_hash": dataset_hash,
        "code_commit": "b" * 40,
        "scope": {"symbol": "EURUSD", "tf": "H1"},
        "metrics": {"rows": 10},
        "artifact_paths": [dataset_path, "reports/certified/EXP-INF4-001.json"],
        "produced_at": "2026-08-21T12:00:00+00:00",
        "certifier": "hermes-gatekeeper",
    }


def _snapshot(tmp_path, *, duplicate_boundary=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "certified.jsonl"
    rows = [
        {
            "timestamp": f"2026-01-{day:02d}T00:00:00+00:00",
            "feature": float(day),
            "label": day % 2,
            "row_id": day,
        }
        for day in range(1, 11)
    ]
    if duplicate_boundary:
        rows[5]["timestamp"] = rows[6]["timestamp"]
    source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    reader = CertifiedDatasetReader(tmp_path)
    return reader.create_snapshot(
        _manifest("certified.jsonl", hash_dataset(source)),
        source,
        tmp_path / "owned-snapshots",
        config={"source": "certified", "seed": 7},
        consumer_code_commit="c" * 40,
        created_at="2026-08-21T13:00:00+00:00",
    )


def _pipeline(tmp_path, snapshot=None, *, seed=7, config=None, **overrides):
    snapshot = snapshot or _snapshot(tmp_path)
    registry = ModelRegistry(tmp_path / "model-registry")
    registry.register_model(
        "skeleton-model",
        "1.0.0",
        git_commit="d" * 40,
        snapshot=snapshot,
        features=["feature"],
        labels=["label"],
        seed=seed,
        config=config or CONFIG,
        created_at="2026-08-21T14:00:00+00:00",
    )
    return TrainingPipeline(
        snapshot=snapshot,
        registry=registry,
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints"),
        model_id="skeleton-model",
        model_version="1.0.0",
        features=["feature"],
        labels=["label"],
        seed=seed,
        config=config or CONFIG,
        **overrides,
    )


def test_temporal_split_reserves_oos_test_from_selection(tmp_path):
    result = _pipeline(tmp_path).run()

    assert [row["row_id"] for row in result.split.train] == [1, 2, 3, 4, 5, 6]
    assert [row["row_id"] for row in result.split.validation] == [7, 8]
    assert [row["row_id"] for row in result.split.test] == [9, 10]
    assert {row["row_id"] for row in result.selection_rows}.isdisjoint(
        {row["row_id"] for row in result.oos_test_rows}
    )
    assert result.metrics["selection_scope"] == "train+validation"
    assert result.metrics["oos_scope"] == "test"
    assert result.metrics["model_training_executed"] is False


def test_pipeline_is_deterministic_and_checkpoint_state_is_a_skeleton(tmp_path):
    first = _pipeline(tmp_path / "first").run()
    second = _pipeline(tmp_path / "second").run()

    assert first.run_id == second.run_id
    assert first.checkpoint.state == second.checkpoint.state
    assert first.checkpoint.state["model_training"] == {
        "executed": False,
        "kind": "contract-skeleton",
    }
    assert first.checkpoint.metadata["seed"] == 7
    assert first.checkpoint.metadata["dataset_hash"] == first.plan.dataset_hash


def test_resume_reloads_only_the_matching_checkpoint(tmp_path):
    pipeline = _pipeline(tmp_path)
    first = pipeline.run()
    resumed = pipeline.run(resume_from=first.checkpoint.checkpoint_id)

    assert resumed.resumed is True
    assert resumed.run_id == first.run_id
    assert resumed.checkpoint.state == first.checkpoint.state

    state_path = first.checkpoint.checkpoint_path / "state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    payload["state"]["seed"] = 999
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TrainingResumeError, match="reanudar checkpoint|integridad"):
        pipeline.run(resume_from=first.checkpoint.checkpoint_id)


def test_raw_or_non_certified_dataset_is_rejected(tmp_path):
    source = tmp_path / "not-a-snapshot.jsonl"
    source.write_text('{"timestamp":"2026-01-01T00:00:00+00:00"}\n', encoding="utf-8")
    pipeline = TrainingPipeline(
        snapshot=source,
        registry=ModelRegistry(tmp_path / "empty-registry"),
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints"),
        model_id="skeleton-model",
        model_version="1.0.0",
        features=["feature"],
        labels=["label"],
        seed=7,
        config=CONFIG,
    )
    with pytest.raises(DatasetCertificationError, match="snapshot no certificado|certificado"):
        pipeline.plan()


def test_registry_configuration_and_seed_must_match_pipeline(tmp_path):
    snapshot = _snapshot(tmp_path)
    pipeline = _pipeline(
        tmp_path / "mismatch",
        snapshot=snapshot,
        seed=7,
        config={"algorithm": "different"},
    )
    # The helper registered the same config. A changed contract is rejected
    # before any checkpoint is created.
    pipeline.config = {"algorithm": "changed"}
    with pytest.raises(TrainingRegistryError, match="config"):
        pipeline.plan()


def test_equal_timestamps_cannot_cross_a_partition_boundary(tmp_path):
    snapshot = _snapshot(tmp_path, duplicate_boundary=True)

    with pytest.raises(TemporalSplitError, match="timestamps iguales"):
        _pipeline(tmp_path / "duplicate-time", snapshot=snapshot).plan()
