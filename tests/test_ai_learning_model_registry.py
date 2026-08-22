from __future__ import annotations

import json

import pytest

from runtime.ai_learning.dataset_snapshots import CertifiedDatasetReader, hash_dataset
from runtime.ai_learning.model_registry import (
    DuplicateCheckpointError,
    DuplicateModelError,
    ModelCompatibilityError,
    ModelLineageError,
    ModelRegistry,
    ModelRegistryError,
    validate_model_dataset_compatibility,
)


def _manifest(dataset_path: str, dataset_hash: str) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "EXP-MODEL-001",
        "verdict": "PASS",
        "gate": "PASS",
        "dataset_hash": dataset_hash,
        "code_commit": "b" * 40,
        "scope": {"symbol": "EURUSD", "tf": "H1"},
        "metrics": {"rows": 2},
        "artifact_paths": [dataset_path, "reports/certified/EXP-MODEL-001.json"],
        "produced_at": "2026-08-21T12:00:00+00:00",
        "certifier": "hermes-gatekeeper",
    }


def _snapshot(tmp_path):
    source = tmp_path / "certified.jsonl"
    source.write_text(
        '{"swing":1.0,"liquidity":0.5,"label":1}\n'
        '{"swing":2.0,"liquidity":0.7,"label":0}\n',
        encoding="utf-8",
    )
    reader = CertifiedDatasetReader(tmp_path)
    manifest = _manifest("certified.jsonl", hash_dataset(source))
    return reader.create_snapshot(
        manifest,
        source,
        tmp_path / "owned-snapshots",
        config={"split": "temporal", "seed": 7},
        consumer_code_commit="c" * 40,
        created_at="2026-08-21T13:00:00+00:00",
    )


def _register(registry: ModelRegistry, snapshot) -> object:
    return registry.register_model(
        "ict-model",
        "1.0.0",
        git_commit="d" * 40,
        snapshot=snapshot,
        features=["swing", "liquidity"],
        labels=["label"],
        seed=7,
        config={"algorithm": "baseline", "learning_rate": 0.1},
        created_at="2026-08-21T14:00:00+00:00",
    )


def test_model_registry_persists_complete_lineage_and_reloads(tmp_path):
    snapshot = _snapshot(tmp_path)
    registry_root = tmp_path / "model-registry"
    record = _register(ModelRegistry(registry_root), snapshot)

    assert record.model_id == "ict-model"
    assert record.snapshot_id == snapshot.snapshot_id
    assert record.dataset_hash == snapshot.dataset_hash
    payload = json.loads((registry_root / "registry.json").read_text(encoding="utf-8"))
    assert payload["models"][0]["features"] == ["swing", "liquidity"]
    assert payload["models"][0]["labels"] == ["label"]

    reloaded = ModelRegistry(registry_root)
    assert reloaded.get_model("ict-model", "1.0.0") == record


def test_registry_rejects_incomplete_lineage_and_does_not_write(tmp_path):
    registry = ModelRegistry(tmp_path / "model-registry")

    with pytest.raises(ModelLineageError, match="snapshot certificado"):
        registry.register_model(
            "ict-model",
            "1.0.0",
            git_commit="d" * 40,
            dataset_hash="a" * 64,
            features=["swing"],
            labels=["label"],
            seed=7,
            config={"algorithm": "baseline"},
        )
    assert not registry.registry_path.exists()


def test_model_id_and_version_cannot_be_overwritten(tmp_path):
    snapshot = _snapshot(tmp_path)
    registry = ModelRegistry(tmp_path / "model-registry")
    first = _register(registry, snapshot)
    before = registry.registry_path.read_bytes()

    with pytest.raises(DuplicateModelError):
        _register(registry, snapshot)

    assert registry.registry_path.read_bytes() == before
    assert registry.get_model("ict-model", "1.0.0") == first


def test_model_dataset_compatibility_rejects_unknown_or_overlapping_fields(tmp_path):
    snapshot = _snapshot(tmp_path)

    with pytest.raises(ModelCompatibilityError, match="ausentes"):
        validate_model_dataset_compatibility(
            snapshot, features=["swing", "future_value"], labels=["label"]
        )
    with pytest.raises(ModelCompatibilityError, match="solapan"):
        validate_model_dataset_compatibility(
            snapshot, features=["swing"], labels=["swing"]
        )


def test_checkpoints_are_immutable_and_recover_deterministically(tmp_path):
    snapshot = _snapshot(tmp_path)
    registry_root = tmp_path / "model-registry"
    registry = ModelRegistry(registry_root)
    _register(registry, snapshot)

    checkpoint = registry.register_checkpoint(
        "ict-model", "1.0.0", "epoch-0001", b"checkpoint-state", metadata={"epoch": 1}
    )
    before = checkpoint.checkpoint_path.read_bytes()
    assert registry.recover_checkpoint("ict-model", "1.0.0", "epoch-0001") == before

    with pytest.raises(DuplicateCheckpointError):
        registry.register_checkpoint(
            "ict-model", "1.0.0", "epoch-0001", b"different-state"
        )
    assert checkpoint.checkpoint_path.read_bytes() == before

    reloaded = ModelRegistry(registry_root)
    assert reloaded.rollback("ict-model", "1.0.0", "epoch-0001") == before

    checkpoint.checkpoint_path.write_bytes(b"tampered")
    with pytest.raises(ModelRegistryError, match="alterado"):
        reloaded.load_checkpoint("ict-model", "1.0.0", "epoch-0001")


def test_registry_destination_cannot_be_inside_hermes_lab(tmp_path):
    with pytest.raises(ModelRegistryError, match="protegida"):
        ModelRegistry(tmp_path / "scripts" / "lab" / "models")


def test_registry_rejects_nested_experiment_destination(tmp_path):
    with pytest.raises(ModelRegistryError, match="frontera Hermes"):
        ModelRegistry(tmp_path / "owned" / "reports" / "audits" / "experiments" / "models")


def test_checkpoint_metadata_is_completed_from_model_and_incompatible_values_rejected(tmp_path):
    snapshot = _snapshot(tmp_path)
    registry = ModelRegistry(tmp_path / "model-registry")
    _register(registry, snapshot)

    checkpoint = registry.register_checkpoint("ict-model", "1.0.0", "epoch-0001", b"state")
    assert checkpoint.metadata["dataset_hash"] == snapshot.dataset_hash
    assert checkpoint.metadata["features"] == ["swing", "liquidity"]
    with pytest.raises(ModelCompatibilityError, match="incompatible"):
        registry.register_checkpoint(
            "ict-model", "1.0.0", "epoch-0002", b"state", metadata={"seed": 99}
        )
