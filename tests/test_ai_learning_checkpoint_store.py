from __future__ import annotations

import json

import pytest

import runtime.ai_learning.checkpoint_store as checkpoint_store_module
from runtime.ai_learning.checkpoint_store import (
    CheckpointExistsError,
    CheckpointIntegrityError,
    CheckpointStore,
    CheckpointStoreError,
)


DATASET_HASH = "a" * 64


def _save(store: CheckpointStore, checkpoint_id: str = "cp-001"):
    return store.save(
        {"weights": [1, 2, 3], "bias": 0.5},
        model_id="hermes-demo",
        model_version="1.2.0",
        dataset_hash=DATASET_HASH,
        features=["open", "close"],
        labels=["direction"],
        seed=7,
        checkpoint_id=checkpoint_id,
    )


def test_save_load_round_trip_and_metadata(tmp_path):
    store = CheckpointStore(tmp_path / "checkpoints")

    checkpoint = _save(store)
    loaded = store.load("cp-001")

    assert checkpoint.checkpoint_path == store.root_dir / "cp-001"
    assert loaded.state == {"weights": [1, 2, 3], "bias": 0.5}
    assert loaded.model_id == "hermes-demo"
    assert loaded.model_version == "1.2.0"
    assert loaded.dataset_hash == DATASET_HASH
    assert loaded.features == ["open", "close"]
    assert loaded.labels == ["direction"]
    assert loaded.seed == 7
    assert {"metadata.json", "state.json", "manifest.json"} == {
        path.name for path in loaded.checkpoint_path.iterdir()
    }


def test_load_recovers_after_new_store_instance(tmp_path):
    root = tmp_path / "checkpoints"
    first_store = CheckpointStore(root)
    expected = _save(first_store)

    recovered = CheckpointStore(root).load("cp-001")

    assert recovered.checkpoint_id == expected.checkpoint_id
    assert recovered.state == expected.state


def test_duplicate_id_is_rejected_without_overwriting_existing_checkpoint(tmp_path):
    store = CheckpointStore(tmp_path / "checkpoints")
    checkpoint = _save(store)
    before = {
        name: (checkpoint.checkpoint_path / name).read_bytes()
        for name in ("metadata.json", "state.json", "manifest.json")
    }

    with pytest.raises(CheckpointExistsError, match="no se sobrescribe"):
        store.save(
            {"weights": [999]},
            model_id="other-model",
            model_version="9.9.9",
            dataset_hash=DATASET_HASH,
            features=["different"],
            labels=["different"],
            seed=99,
            checkpoint_id="cp-001",
        )

    assert {
        name: (checkpoint.checkpoint_path / name).read_bytes()
        for name in before
    } == before


@pytest.mark.parametrize("filename", ["metadata.json", "state.json", "manifest.json"])
def test_tampering_any_checkpoint_file_is_detected(tmp_path, filename):
    store = CheckpointStore(tmp_path / "checkpoints")
    checkpoint = _save(store)
    path = checkpoint.checkpoint_path / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    if filename == "state.json":
        payload["state"]["weights"][0] = 999
    elif filename == "metadata.json":
        payload["model_version"] = "tampered"
    else:
        payload["state_hash"] = "b" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CheckpointIntegrityError, match="integridad|hash|coincide"):
        store.load("cp-001")


def test_rollback_changes_only_active_pointer_and_survives_restart(tmp_path):
    root = tmp_path / "checkpoints"
    store = CheckpointStore(root)
    first = _save(store, "cp-001")
    second = _save(store, "cp-002")
    second_before = {
        name: (second.checkpoint_path / name).read_bytes()
        for name in ("metadata.json", "state.json", "manifest.json")
    }

    assert store.rollback("cp-001").checkpoint_id == "cp-001"
    assert store.load().checkpoint_id == "cp-001"
    assert CheckpointStore(root).load().checkpoint_id == "cp-001"
    assert {
        name: (second.checkpoint_path / name).read_bytes()
        for name in second_before
    } == second_before
    assert first.checkpoint_path.is_dir()
    assert (root / "active.json").is_file()


@pytest.mark.parametrize(
    "root_name",
    [
        "datasets/checkpoints",
        "runners/checkpoints",
        "lab/checkpoints",
        "pipeline/checkpoints",
        "scripts/lab/checkpoints",
        "data/learning/pipeline/checkpoints",
        "reports/audits/experiments/checkpoints",
    ],
)
def test_protected_routes_are_rejected_before_creation(tmp_path, root_name):
    root = tmp_path / root_name

    with pytest.raises(CheckpointStoreError, match="proteg"):
        CheckpointStore(root)

    assert not root.exists()


def test_resolved_traversal_and_checkpoint_id_are_rejected(tmp_path):
    with pytest.raises(CheckpointStoreError, match="protegida"):
        CheckpointStore(tmp_path / "safe" / ".." / "datasets")

    store = CheckpointStore(tmp_path / "checkpoints")
    with pytest.raises(CheckpointStoreError, match="nombre local seguro"):
        _save(store, "../outside")


def test_model_metadata_cannot_encode_a_path(tmp_path):
    store = CheckpointStore(tmp_path / "checkpoints")
    with pytest.raises(CheckpointStoreError, match="model_id"):
        store.save(
            {"weights": [1]},
            model_id="../model",
            model_version="1.0.0",
            dataset_hash=DATASET_HASH,
            features=["feature"],
            labels=["label"],
            seed=1,
            checkpoint_id="cp-path",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_hash", "invalid"),
        ("features", []),
        ("labels", "label"),
        ("seed", True),
    ],
)
def test_metadata_contract_is_validated(field, value, tmp_path):
    store = CheckpointStore(tmp_path / "checkpoints")
    values = {
        "state": {"weights": [1]},
        "model_id": "hermes-demo",
        "model_version": "1.0.0",
        "dataset_hash": DATASET_HASH,
        "features": ["feature"],
        "labels": ["label"],
        "seed": 1,
        "checkpoint_id": "cp-invalid",
    }
    values[field] = value

    with pytest.raises(CheckpointStoreError, match=field):
        store.save(**values)


def test_failed_publication_cleans_only_its_temporary_directory(tmp_path, monkeypatch):
    store = CheckpointStore(tmp_path / "checkpoints")
    original_write = checkpoint_store_module._write_json
    calls = 0

    def fail_on_state(path, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated write failure")
        original_write(path, payload)

    monkeypatch.setattr(checkpoint_store_module, "_write_json", fail_on_state)
    with pytest.raises(CheckpointStoreError, match="no se pudo publicar"):
        _save(store, "cp-failed")

    assert not (store.root_dir / "cp-failed").exists()
    assert not any(path.name.endswith(".tmp") for path in store.root_dir.glob("*"))
