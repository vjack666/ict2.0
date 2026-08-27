"""FASE 4 (SDD v1.2): Market State projection tests.

Verifies that the persistent Market State is causal (no look-ahead), deterministic,
FULL==PREFIX stable, and that terminal objects are kept as history but not drawn
as active entities.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from backtest.market_state import build_market_state
from backtest.replay import ReplayConfig, run_visual_replay
from backtest.schema import validate_visual_backtest


def _fixture(rows: int = 60, freq: str = "h") -> pd.DataFrame:
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


def _artifact(rows: int = 40):
    frame = _fixture(rows)
    return run_visual_replay(
        {"H1": frame},
        ReplayConfig(
            symbol="TEST", timeframe="H1", timeframes=("H1",), authority_tf="H1",
            warmup_bars=0, wyckoff_enabled=False, git_commit="fixture-commit",
        ),
    )


def test_market_state_has_one_snapshot_per_visible_candle():
    payload = _artifact().to_dict()
    assert len(payload["market_state"]) == len(payload["candles"])
    for snapshot, point in zip(payload["market_state"], payload["timeline"], strict=True):
        assert snapshot["decision_time"] == point["decision_time"]
        assert snapshot["authority_tf"] == "H1"
        assert isinstance(snapshot["entities"], list)
        assert isinstance(snapshot["terminal_entities"], list)
        assert set(snapshot["delta"]) == {"created", "transitioned", "terminal"}


def test_market_state_has_no_future_decision_time():
    payload = _artifact().to_dict()
    for snapshot, point in zip(payload["market_state"], payload["timeline"], strict=True):
        assert pd.Timestamp(snapshot["decision_time"]) == pd.Timestamp(point["decision_time"])


def test_market_state_entities_use_canonical_contract():
    payload = _artifact().to_dict()
    required = {
        "id", "type", "origin_tf", "role", "direction", "zone_high", "zone_low",
        "state", "parent_object", "related_objects", "candidate_bar",
        "confirmation_bar", "tradable_bar", "first_touch_bar", "invalidated_bar",
        "mitigation_level", "age_bars",
    }
    for snapshot in payload["market_state"]:
        for entity in snapshot["entities"]:
            assert required <= set(entity)
            assert entity["origin_tf"] in payload["data_manifest"]["timeframes"]
            assert entity["state"] in {
                "CREATED", "ACTIVE", "PARTIALLY_MITIGATED", "MITIGATED",
                "INVALIDATED", "EXPIRED", "CONSUMED",
            }


def test_market_state_is_deterministic():
    first = _artifact(40).to_dict()["market_state"]
    second = _artifact(40).to_dict()["market_state"]
    assert first == second


def test_market_state_full_equals_prefix():
    """FULL == PREFIX: the state at T is identical whether computed from the
    start or from a later prefix (no look-ahead, causal projection)."""
    frame = _fixture(60)
    config = ReplayConfig(
        symbol="TEST", timeframe="H1", timeframes=("H1",), authority_tf="H1",
        warmup_bars=0, wyckoff_enabled=False, git_commit="fixture-commit",
    )
    full = run_visual_replay({"H1": frame}, config).to_dict()["market_state"]

    # Re-run with a shorter visible window (prefix) and compare the overlapping
    # snapshots. The projection only uses time <= decision_time, so the state at
    # each T must be identical.
    prefix_config = ReplayConfig(
        symbol="TEST", timeframe="H1", timeframes=("H1",), authority_tf="H1",
        warmup_bars=0, wyckoff_enabled=False, git_commit="fixture-commit",
        visible_start="2024-01-01T00:00:00Z", visible_end="2024-01-01T20:00:00Z",
    )
    prefix = run_visual_replay({"H1": frame}, prefix_config).to_dict()["market_state"]
    # Compare the first N snapshots of the full run with the prefix run.
    n = len(prefix)
    assert full[:n] == prefix


def test_artifact_with_market_state_validates():
    payload = _artifact(32).to_dict()
    validate_visual_backtest(payload)


def test_terminal_objects_are_kept_as_history_not_active():
    """Terminal objects must appear in terminal_entities (history) and not in
    entities (active)."""
    payload = _artifact(60).to_dict()
    for snapshot in payload["market_state"]:
        active_ids = {e["id"] for e in snapshot["entities"]}
        terminal_ids = {e["id"] for e in snapshot["terminal_entities"]}
        assert not (active_ids & terminal_ids)
