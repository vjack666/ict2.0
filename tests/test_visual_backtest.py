"""Schema, temporal-boundary and serialization tests for visual replay v1.1."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from backtest.replay import (
    ReplayConfig,
    _canonical_frame,
    _first_closed_at_or_after,
    extract_structure_events,
    load_raw_frames,
    run_visual_replay,
)
from backtest.schema import artifact_content_sha256, validate_visual_backtest, write_visual_backtest


def _fixture(rows: int = 48, freq: str = "h") -> pd.DataFrame:
    index = np.arange(rows)
    close = 1.10 + np.sin(index / 3.0) * 0.01 + index * 0.00001
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=rows, freq=freq, tz="UTC"),
            "open": close,
            "high": close + 0.002,
            "low": close - 0.002,
            "close": close,
            "tick_volume": 100 + index,
        }
    )


def _artifact(rows: int = 32):
    frame = _fixture(rows)
    return run_visual_replay(
        {"H1": frame},
        ReplayConfig(
            symbol="TEST", timeframe="H1", timeframes=("H1",), authority_tf="H1",
            warmup_bars=0, wyckoff_enabled=False, git_commit="fixture-commit",
        ),
    )


def test_v11_schema_is_valid_safe_and_has_no_old_backtest_imports():
    payload = _artifact().to_dict()
    validate_visual_backtest(payload)
    assert payload["schema_version"] == "1.1"
    assert payload["run_metadata"]["legacy_backtest"] is False
    assert payload["run_metadata"]["git_branch"] == "UNKNOWN"
    assert payload["run_metadata"]["generator_worktree_clean_before_run"] is False
    assert payload["run_metadata"]["python_version"]
    assert payload["run_metadata"]["node_version"] == "NOT_APPLICABLE"
    assert payload["visible_window"]["warmup_bars"] == 0
    assert payload["policy"] == {
        "diagnostic_only": True,
        "entry_authorized": False,
        "can_trade": False,
        "can_train": False,
        "promotion_authorized": False,
    }
    assert payload["scientific_status"]["edge_claimed"] is False

    for path in ("backtest/__init__.py", "backtest/replay.py", "backtest/schema.py"):
        tree = ast.parse(open(path, encoding="utf-8").read())
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        assert all("ict_backtest" not in ast.unparse(node) for node in imports)


def test_structure_events_are_prefix_stable_and_parents_are_causal():
    frame = _fixture(80)
    full = extract_structure_events(frame)
    prefix = extract_structure_events(frame.iloc[:40])
    assert [event for event in full if event["index"] < 40] == prefix
    seen = set()
    for event in full:
        if event.get("parent_id") is not None:
            assert event["parent_id"] in seen
        assert event["confirmed_index"] >= event["index"]
        if event.get("formation_index") is not None:
            assert event["formation_index"] < event["confirmed_index"]
        seen.add(event["id"])


def test_open_time_is_shifted_to_close_and_future_is_not_in_timeline():
    payload = _artifact(12).to_dict()
    assert payload["candles"][0]["source_time"] == "2024-01-01T00:00:00+00:00"
    assert payload["candles"][0]["bar_close_time"] == "2024-01-01T01:00:00+00:00"
    assert payload["timeline"][0]["decision_time"] == payload["candles"][0]["bar_close_time"]
    assert payload["candles"][0]["available_time"] == payload["candles"][0]["bar_close_time"]
    assert "ict" in payload["timeline"][0] and "wyckoff" in payload["timeline"][0]
    for point in payload["timeline"]:
        decision = pd.Timestamp(point["decision_time"])
        assert all(pd.Timestamp(asof) <= decision for asof in point["asof_by_tf"].values() if asof)


def test_loader_hides_warmup_and_records_tick_volume_provenance(tmp_path):
    data_dir = tmp_path / "raw"
    symbol_dir = data_dir / "TEST"
    symbol_dir.mkdir(parents=True)
    _fixture(40, "15min").to_parquet(symbol_dir / "TEST_M15.parquet", index=False)
    frames = load_raw_frames(
        "TEST", ("M15",), data_dir=data_dir,
        start="2024-01-01T02:00:00Z", end="2024-01-01T04:00:00Z",
        warmup_bars=5, timestamp_semantics="open",
    )
    frame = frames["M15"]
    manifest = frame.attrs["manifest"]
    assert manifest["warmup_rows"] == 5
    assert manifest["visible_rows"] == 8
    assert manifest["timestamp_semantics"] == "OPEN_TIME"
    assert manifest["volume_source"] == "TICK_VOLUME_PROXY"
    assert manifest["relative_source_path"] == "TEST/TEST_M15.parquet"
    assert manifest["used_rows"] == manifest["warmup_rows"] + manifest["visible_rows"]
    assert manifest["warmup_first_time"] is not None
    assert manifest["warmup_last_time"] < manifest["visible_first_time"]
    assert manifest["last_asof_available"] == manifest["visible_last_time"]
    assert len(manifest["source_file_sha256"]) == 64
    assert len(manifest["slice_sha256"]) == 64


def test_payload_and_hash_are_deterministic_and_write_is_atomic(tmp_path):
    first = _artifact(24).to_dict()
    second = _artifact(24).to_dict()
    assert first == second
    output = tmp_path / "visual_backtest.json"
    write_visual_backtest(first, output)
    assert json.loads(output.read_text(encoding="utf-8")) == first
    assert not output.with_suffix(".json.tmp").exists()

    lineage_variant = copy.deepcopy(first)
    lineage_variant["run_metadata"].update({
        "git_branch": "another-local-branch",
        "generator_worktree_clean_before_run": True,
        "python_version": "different-runtime",
        "node_version": "different-node",
    })
    assert artifact_content_sha256(lineage_variant) == artifact_content_sha256(first)


def test_cli_two_exports_with_same_inputs_produce_identical_payload_and_hash(tmp_path):
    data_dir = tmp_path / "raw"
    symbol_dir = data_dir / "TEST"
    symbol_dir.mkdir(parents=True)
    _fixture(40, "15min").to_parquet(symbol_dir / "TEST_M15.parquet", index=False)
    payloads = []
    for label in ("a", "b"):
        run_dir = tmp_path / f"runs-{label}"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/export_visual_backtest.py",
                "--symbol", "TEST",
                "--timeframe", "M15",
                "--tfs", "M15",
                "--data-dir", str(data_dir),
                "--start", "2024-01-01T02:00:00Z",
                "--end", "2024-01-01T04:00:00Z",
                "--warmup-bars", "5",
                "--timestamp-semantics", "open",
                "--wyckoff-authority-tf", "M15",
                "--run-dir", str(run_dir),
            ],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
        run_id = next(
            line.split("=", 1)[1]
            for line in completed.stdout.splitlines()
            if line.startswith("run_id=")
        )
        payloads.append(json.loads((run_dir / run_id / "visual_backtest.json").read_text(encoding="utf-8")))
    assert payloads[0] == payloads[1]
    assert payloads[0]["run_metadata"]["artifact_content_sha256"] == artifact_content_sha256(payloads[0])


def test_result_availability_maps_to_first_main_close_at_or_after_exit():
    frame = _canonical_frame(
        _fixture(6), name="H1", timeframe="H1", timestamp_semantics="open"
    )
    assert _first_closed_at_or_after(frame, "2024-01-01T01:30:00Z") == 1
    assert _first_closed_at_or_after(frame, "2024-01-01T02:00:00Z") == 1
    assert _first_closed_at_or_after(frame, "2024-01-01T06:30:00Z") is None


def test_v10_nonfinite_and_unsafe_policy_are_rejected():
    payload = _artifact(8).to_dict()
    old = copy.deepcopy(payload)
    old["schema_version"] = "1.0"
    with pytest.raises(ValueError, match="unsupported"):
        validate_visual_backtest(old)
    invalid = copy.deepcopy(payload)
    invalid["candles"][0]["open"] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        validate_visual_backtest(invalid)
    unsafe = copy.deepcopy(payload)
    unsafe["policy"]["can_trade"] = True
    with pytest.raises(ValueError, match="unsafe policy"):
        validate_visual_backtest(unsafe)


def test_fail_closed_rejects_temporal_ohlc_parent_trade_manifest_and_hash_defects():
    payload = _artifact(16).to_dict()

    duplicate = copy.deepcopy(payload)
    duplicate["candles"][1]["bar_open_time"] = "2024-01-01T00:30:00+00:00"
    duplicate["candles"][1]["bar_close_time"] = duplicate["candles"][0]["bar_close_time"]
    duplicate["candles"][1]["available_time"] = duplicate["candles"][0]["bar_close_time"]
    duplicate["timeline"][1]["decision_time"] = duplicate["candles"][0]["bar_close_time"]
    with pytest.raises(ValueError, match="strictly increasing"):
        validate_visual_backtest(duplicate)

    incoherent = copy.deepcopy(payload)
    incoherent["candles"][0]["high"] = incoherent["candles"][0]["low"] - 1.0
    with pytest.raises(ValueError, match="incoherent candle OHLC"):
        validate_visual_backtest(incoherent)

    future_asof = copy.deepcopy(payload)
    future_asof["timeline"][0]["asof_by_tf"]["H1"] = "2099-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="future as-of"):
        validate_visual_backtest(future_asof)

    wrong_authority = copy.deepcopy(payload)
    wrong_authority["timeline"][0]["wyckoff"]["policy"] = "ACTIVE"
    wrong_authority["timeline"][0]["wyckoff"]["authority_tf"] = "M15"
    with pytest.raises(ValueError, match="authority"):
        validate_visual_backtest(wrong_authority)

    bad_parent = copy.deepcopy(payload)
    bad_parent["structure_events"] = [{
        "id": "CHILD", "kind": "BOS", "index": 0, "confirmed_index": 0,
        "time": payload["candles"][0]["bar_close_time"],
        "confirmed_time": payload["candles"][0]["bar_close_time"],
        "parent_id": "MISSING", "direction": "bullish", "price": 1.0,
        "status": "emitted",
    }]
    with pytest.raises(ValueError, match="parent must precede"):
        validate_visual_backtest(bad_parent)

    premature_trade = copy.deepcopy(payload)
    premature_trade["trades"] = [{
        "id": "TRADE_BAD", "entry_index": 0,
        "entry_time": payload["candles"][0]["bar_close_time"],
        "exit_index": None, "exit_time": None, "exit_price": None,
        "outcome": "TP", "exit_r": 2.0, "bars_held": None,
        "result_confirmed_index": None,
    }]
    with pytest.raises(ValueError, match="before result confirmation"):
        validate_visual_backtest(premature_trade)

    bad_volume = copy.deepcopy(payload)
    bad_volume["data_manifest"]["timeframes"]["H1"]["volume_source"] = "MADE_UP"
    with pytest.raises(ValueError, match="volume source invalid"):
        validate_visual_backtest(bad_volume)

    bad_hash = copy.deepcopy(payload)
    bad_hash["run_metadata"]["config_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="config_sha256"):
        validate_visual_backtest(bad_hash)
