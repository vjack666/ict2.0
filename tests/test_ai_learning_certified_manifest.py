from __future__ import annotations

import json

import pytest

from runtime.ai_learning.certified_artifacts import (
    CertifiedArtifactError,
    CertifiedExperimentManifest,
    load_certified_manifest,
)


def valid_manifest() -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "EXP-CERT-001",
        "verdict": "PASS",
        "gate": "PASS",
        "dataset_hash": "a" * 64,
        "code_commit": "b" * 40,
        "scope": {"symbol": "EURUSD", "tf": "H1", "period": "2019-2024"},
        "metrics": {"n": 196, "mean_r": 0.2584, "ci95_low": 0.0938},
        "artifact_paths": ["reports/certified/EXP-CERT-001.json"],
        "produced_at": "2026-08-21T12:00:00+00:00",
        "certifier": "hermes-gatekeeper",
    }


def test_valid_manifest_is_immutable_and_typed():
    payload = valid_manifest()

    result = CertifiedExperimentManifest.from_mapping(payload)

    assert result.experiment_id == "EXP-CERT-001"
    assert result.artifact_paths == ("reports/certified/EXP-CERT-001.json",)
    assert result.verdict == "PASS"
    assert payload["verdict"] == "PASS"


def test_real_current_audit_is_rejected_when_handoff_fields_are_missing():
    with pytest.raises(CertifiedArtifactError, match="experiment_id"):
        load_certified_manifest("reports/audits/experiments/current_batch/EXP_A1_audit.json")


@pytest.mark.parametrize("verdict", ["FAIL", "BLOCKED", "INCONCLUSIVE", "MEASURED", "pending"])
def test_non_pass_verdicts_are_rejected(verdict: str):
    payload = valid_manifest()
    payload["verdict"] = verdict

    with pytest.raises(CertifiedArtifactError, match="verdict"):
        CertifiedExperimentManifest.from_mapping(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset_hash", "bad", "dataset_hash"),
        ("code_commit", "not-a-commit", "code_commit"),
        ("scope", {}, "scope"),
        ("metrics", {}, "metrics"),
        ("artifact_paths", ["../outside.json"], "artifact_paths"),
        ("produced_at", "not-a-date", "produced_at"),
    ],
)
def test_contract_rejects_invalid_fields(field: str, value: object, message: str):
    payload = valid_manifest()
    payload[field] = value

    with pytest.raises(CertifiedArtifactError, match=message):
        CertifiedExperimentManifest.from_mapping(payload)


def test_loader_is_read_only(tmp_path):
    path = tmp_path / "manifest.json"
    payload = valid_manifest()
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = load_certified_manifest(path)

    assert result.code_commit == "b" * 40
    assert json.loads(path.read_text(encoding="utf-8")) == payload
