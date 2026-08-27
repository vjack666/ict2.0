"""FASE 4 (SDD v1.2): Schema 1.2 validation tests.

Verifies that schema 1.2 validates market_state/setups, rejects malformed
projections, and that the fail-closed guarantees are preserved.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from backtest.replay import ReplayConfig, run_visual_replay
from backtest.schema import SCHEMA_VERSION, validate_visual_backtest


def _fixture(rows: int = 40, freq: str = "h") -> pd.DataFrame:
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


def test_schema_version_is_1_2():
    assert SCHEMA_VERSION == "1.2"
    payload = _artifact().to_dict()
    assert payload["schema_version"] == "1.2"


def test_missing_market_state_is_rejected():
    payload = _artifact().to_dict()
    del payload["market_state"]
    with pytest.raises(ValueError, match="missing keys"):
        validate_visual_backtest(payload)


def test_missing_setups_is_rejected():
    payload = _artifact().to_dict()
    del payload["setups"]
    with pytest.raises(ValueError, match="missing keys"):
        validate_visual_backtest(payload)


def test_market_state_length_mismatch_is_rejected():
    payload = _artifact().to_dict()
    payload["market_state"] = payload["market_state"][:-1]
    with pytest.raises(ValueError, match="one snapshot per visible candle"):
        validate_visual_backtest(payload)


def test_market_state_decision_time_mismatch_is_rejected():
    payload = _artifact().to_dict()
    payload["market_state"][0]["decision_time"] = "2099-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="decision_time mismatch"):
        validate_visual_backtest(payload)


def test_market_state_entity_invalid_state_is_rejected():
    payload = _artifact().to_dict()
    # Force an invalid state on the first entity of the first snapshot.
    snapshot = payload["market_state"][0]
    if snapshot["entities"]:
        snapshot["entities"][0]["state"] = "BOGUS"
        with pytest.raises(ValueError, match="invalid state"):
            validate_visual_backtest(payload)


def test_setup_invalid_estado_is_rejected():
    payload = _artifact().to_dict()
    payload["setups"][0]["estado"] = "BOGUS"
    with pytest.raises(ValueError, match="invalid estado"):
        validate_visual_backtest(payload)


def test_setup_policy_must_be_context_only():
    payload = _artifact().to_dict()
    payload["setups"][0]["policy"] = "ENTRY_SIGNAL"
    with pytest.raises(ValueError, match="context-only policy"):
        validate_visual_backtest(payload)


def test_unsafe_policy_still_rejected_in_v12():
    payload = _artifact().to_dict()
    payload["policy"]["can_trade"] = True
    with pytest.raises(ValueError, match="unsafe policy"):
        validate_visual_backtest(payload)
