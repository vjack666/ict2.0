from __future__ import annotations

import json

import pytest

from runtime.ai_learning.checkpoint_store import CheckpointStore
from runtime.ai_learning.dataset_snapshots import CertifiedDatasetReader, hash_dataset
from runtime.ai_learning.model_registry import ModelRegistry
from runtime.ai_learning.outcome_classifier import (
    FEATURE_NAMES,
    OUTCOME_CLASSES,
    TrainingAuthorizationError,
    train_outcome_classifier,
)
from runtime.ai_learning.training_pipeline import TrainingPipeline


CONFIG = {
    "algorithm": "deterministic_multinomial_softmax",
    "shadow_mode": True,
    "can_trade": False,
}


def _make_pipeline(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "certified.jsonl"
    rows = []
    for index in range(90):
        context = ("ALIGNED", "NEUTRAL", "AGAINST")[index % 3]
        label = OUTCOME_CLASSES[index % 3]
        rows.append(
            {
                "timestamp": f"2020-01-{(index // 3) + 1:02d}T{index % 3:02d}:00:00+00:00",
                "features_at_t": {
                    "context_inputs": {
                        "sequence_direction": 1,
                        "context_bucket": context,
                        "h1_alignment": context,
                        "d1_bias": "BULLISH" if context == "ALIGNED" else "UNKNOWN",
                        "h4_location": "DISCOUNT" if context == "ALIGNED" else "UNKNOWN",
                    },
                    "sequence": ["STRUCTURE", "FVG"] if context == "ALIGNED" else ["STRUCTURE"],
                },
                "direction": 1,
                "sequence_depth": 4 + (index % 3),
                "label_end_6": label,
                "can_trade": False,
            }
        )
    source.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "experiment_id": "EXP-AI-OUTCOME-001",
        "verdict": "PASS",
        "gate": "PASS",
        "dataset_hash": hash_dataset(source),
        "code_commit": "a" * 40,
        "scope": {"symbol": "EURUSD", "tf": "H1"},
        "metrics": {"rows": len(rows)},
        "artifact_paths": ["certified.jsonl"],
        "produced_at": "2026-08-31T12:00:00+00:00",
        "certifier": "test",
    }
    snapshot = CertifiedDatasetReader(tmp_path).create_snapshot(
        manifest,
        source,
        tmp_path / "snapshots",
        config={"source": "Dukascopy-research", "seed": 7},
        consumer_code_commit="b" * 40,
        created_at="2026-08-31T12:01:00+00:00",
    )
    registry = ModelRegistry(tmp_path / "registry")
    registry.register_model(
        "outcome-classifier",
        "1.0.0",
        git_commit="c" * 40,
        snapshot=snapshot,
        features=["features_at_t"],
        labels=["label_end_6"],
        seed=7,
        config=CONFIG,
        created_at="2026-08-31T12:02:00+00:00",
    )
    pipeline = TrainingPipeline(
        snapshot=snapshot,
        registry=registry,
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints"),
        model_id="outcome-classifier",
        model_version="1.0.0",
        features=["features_at_t"],
        labels=["label_end_6"],
        seed=7,
        config=CONFIG,
        allow_configured_temporal_split=True,
    )
    return pipeline, snapshot, rows


def _gate(snapshot):
    return {
        "status": "PASS",
        "verdict": "TRAINING_ELIGIBLE",
        "dataset_hash": snapshot.dataset_hash,
    }


def test_classifier_refuses_training_without_scientific_authorization(tmp_path):
    pipeline, snapshot, _ = _make_pipeline(tmp_path)

    with pytest.raises(TrainingAuthorizationError, match="TRAINING_ELIGIBLE"):
        train_outcome_classifier(
            pipeline,
            research_gate={"status": "PASS", "verdict": "INSUFFICIENT_N", "dataset_hash": snapshot.dataset_hash},
        )


def test_classifier_trains_temporally_and_predicts_shadow_only(tmp_path):
    pipeline, snapshot, rows = _make_pipeline(tmp_path)

    artifact = train_outcome_classifier(pipeline, research_gate=_gate(snapshot))
    prediction = artifact.predict(rows[-1], in_domain=True)

    assert artifact.feature_names == FEATURE_NAMES
    assert artifact.metrics["model_training_executed"] is True
    assert artifact.metrics["oos_scope"] == "TEST_OOS never used for fitting"
    assert prediction["prediction"] in OUTCOME_CLASSES
    assert prediction["shadow_mode"] is True
    assert prediction["can_trade"] is False
    assert prediction["lineage"]["dataset_hash"] == snapshot.dataset_hash
    assert prediction["lineage"]["source_code_commit"] == "c" * 40
    assert prediction["abstention"]["state"] in {"ACCEPT", "REVIEW", "ABSTAIN"}
    json.dumps(artifact.to_dict(), sort_keys=True, allow_nan=False)


def test_classifier_artifact_is_deterministic(tmp_path):
    first_pipeline, first_snapshot, _ = _make_pipeline(tmp_path / "first")
    second_pipeline, second_snapshot, _ = _make_pipeline(tmp_path / "second")

    first = train_outcome_classifier(first_pipeline, research_gate=_gate(first_snapshot))
    second = train_outcome_classifier(second_pipeline, research_gate=_gate(second_snapshot))

    assert first.to_dict() == second.to_dict()
