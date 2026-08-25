"""Focused tests for the new visual-backtest consumer."""

from __future__ import annotations

import ast

import numpy as np
import pandas as pd

from backtest.replay import ReplayConfig, extract_structure_events, run_visual_replay
from backtest.schema import validate_visual_backtest


def _fixture(rows: int = 80) -> pd.DataFrame:
    index = np.arange(rows)
    close = 1.10 + np.sin(index / 3.0) * 0.01 + index * 0.00001
    return pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC"),
            "open": close,
            "high": close + 0.002,
            "low": close - 0.002,
            "close": close,
        }
    )


def test_new_replay_emits_valid_schema_without_old_backtest_imports():
    frame = _fixture()
    artifact = run_visual_replay(
        {"H1": frame},
        ReplayConfig(symbol="TEST", timeframe="H1", timeframes=("H1",)),
    )
    payload = artifact.to_dict()
    validate_visual_backtest(payload)
    assert payload["metadata"]["legacy_backtest"] is False
    assert payload["metadata"]["promotion_authorized"] is False

    for path in ("backtest/__init__.py", "backtest/replay.py", "backtest/schema.py"):
        tree = ast.parse(open(path, encoding="utf-8").read())
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        assert all("ict_backtest" not in ast.unparse(node) for node in imports)


def test_structure_events_are_prefix_stable_and_parents_are_causal():
    frame = _fixture()
    full = extract_structure_events(frame)
    prefix = extract_structure_events(frame.iloc[:40])
    assert [event for event in full if event["index"] < 40] == prefix

    seen = set()
    for event in full:
        parent_id = event.get("parent_id")
        if parent_id is not None:
            assert parent_id in seen
        assert event["confirmed_index"] >= event["index"]
        if event.get("formation_index") is not None:
            assert event["formation_index"] < event["confirmed_index"]
        seen.add(event["id"])


def test_candles_preserve_source_ohlc_and_no_trade_is_invented():
    frame = _fixture(32)
    artifact = run_visual_replay(
        {"H1": frame},
        ReplayConfig(symbol="TEST", timeframe="H1", timeframes=("H1",)),
    )
    assert artifact.candles[0]["open"] == float(frame.iloc[0]["open"])
    assert artifact.candles[-1]["close"] == float(frame.iloc[-1]["close"])
    assert artifact.trades == []


def test_exported_ids_are_deterministic_even_when_engine_objects_are_not():
    frame = _fixture(120)
    config = ReplayConfig(symbol="TEST", timeframe="H1", timeframes=("H1",))
    first = run_visual_replay({"H1": frame}, config).to_dict()
    second = run_visual_replay({"H1": frame}, config).to_dict()
    assert first == second
