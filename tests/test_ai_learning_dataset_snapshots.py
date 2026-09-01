from __future__ import annotations

import json

import pytest

from runtime.ai_learning import (
    CertifiedDatasetReader,
    DatasetSchemaChangedError,
    DatasetSnapshotError,
    detect_schema_change,
    hash_dataset,
    load_dataset_snapshot,
)


def _manifest(dataset_path: str, dataset_hash: str) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "EXP-CERT-002",
        "verdict": "PASS",
        "gate": "PASS",
        "dataset_hash": dataset_hash,
        "code_commit": "b" * 40,
        "scope": {"symbol": "EURUSD", "tf": "H1", "period": "2019-2024"},
        "metrics": {"n": 2},
        "artifact_paths": [dataset_path, "reports/certified/EXP-CERT-002.json"],
        "produced_at": "2026-08-21T12:00:00+00:00",
        "certifier": "hermes-gatekeeper",
    }


def _dataset(tmp_path):
    path = tmp_path / "certified.jsonl"
    path.write_text(
        '{"symbol":"EURUSD","tf":"H1","label":1}\n'
        '{"symbol":"EURUSD","tf":"H1","label":0}\n',
        encoding="utf-8",
    )
    return path


def test_snapshot_is_reproducible_and_keeps_lineage(tmp_path):
    source = _dataset(tmp_path)
    manifest = _manifest("certified.jsonl", hash_dataset(source))
    reader = CertifiedDatasetReader(tmp_path)
    output = tmp_path / "owned-snapshots"

    first = reader.create_snapshot(
        manifest,
        source,
        output,
        config={"split": "temporal", "seed": 7},
        consumer_code_commit="c" * 40,
        created_at="2026-08-21T13:00:00+00:00",
    )
    second = reader.create_snapshot(
        manifest,
        source,
        output,
        config={"seed": 7, "split": "temporal"},
        consumer_code_commit="c" * 40,
        created_at="2026-08-22T13:00:00+00:00",
    )

    assert first.snapshot_id == second.snapshot_id
    assert first.dataset_hash == manifest["dataset_hash"]
    assert first.source_path == "certified.jsonl"
    assert first.to_dict()["code_commit"] == manifest["code_commit"]
    assert first.to_dict()["certified_manifest"]["certifier"] == "hermes-gatekeeper"
    assert reader.read_snapshot(first.snapshot_path)[0]["label"] == 1
    assert load_dataset_snapshot(first.snapshot_path).experiment_id == "EXP-CERT-002"


def test_reader_rejects_hash_or_lineage_mismatch_without_writing_source(tmp_path):
    source = _dataset(tmp_path)
    original = source.read_bytes()
    manifest = _manifest("other.jsonl", hash_dataset(source))
    reader = CertifiedDatasetReader(tmp_path)

    with pytest.raises(DatasetSnapshotError, match="artifact_paths"):
        reader.create_snapshot(
            manifest,
            source,
            tmp_path / "owned-snapshots",
            config={"split": "temporal"},
            consumer_code_commit="c" * 40,
        )
    assert source.read_bytes() == original


def test_schema_change_is_detected_and_incompatible_data_is_rejected(tmp_path):
    source = _dataset(tmp_path)
    manifest = _manifest("certified.jsonl", hash_dataset(source))
    reader = CertifiedDatasetReader(tmp_path)
    snapshot = reader.create_snapshot(
        manifest,
        source,
        tmp_path / "owned-snapshots",
        config={"split": "temporal"},
        consumer_code_commit="c" * 40,
        created_at="2026-08-21T13:00:00+00:00",
    )

    changed = tmp_path / "changed.jsonl"
    changed.write_text(
        '{"symbol":"EURUSD","tf":"H1","label":1,"future":true}\n',
        encoding="utf-8",
    )
    assert reader.schema_changed(changed, snapshot.schema)
    assert detect_schema_change(snapshot.schema, json.loads(json.dumps(snapshot.schema.to_dict()))) is False
    with pytest.raises(DatasetSchemaChangedError, match="schema_hash incompatible"):
        reader.assert_schema_compatible(changed, snapshot.schema)


def test_protected_hermes_destination_is_rejected(tmp_path):
    source = _dataset(tmp_path)
    manifest = _manifest("certified.jsonl", hash_dataset(source))
    reader = CertifiedDatasetReader(tmp_path)

    with pytest.raises(DatasetSnapshotError, match="proteg"):
        reader.create_snapshot(
            manifest,
            source,
            tmp_path / "datasets" / "generated",
            config={"split": "temporal"},
            consumer_code_commit="c" * 40,
        )


def test_snapshot_tampering_is_detected(tmp_path):
    source = _dataset(tmp_path)
    manifest = _manifest("certified.jsonl", hash_dataset(source))
    reader = CertifiedDatasetReader(tmp_path)
    snapshot = reader.create_snapshot(
        manifest,
        source,
        tmp_path / "owned-snapshots",
        config={"split": "temporal"},
        consumer_code_commit="c" * 40,
    )
    snapshot.data_path.write_text(snapshot.data_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(DatasetSnapshotError, match="alterado"):
        reader.read_snapshot(snapshot.snapshot_path)
