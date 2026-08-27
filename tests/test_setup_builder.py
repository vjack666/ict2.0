"""FASE 4 (SDD v1.2): Setup State projection tests.

Verifies that setup_builder is an ADAPTER/PROJECTION/EXPLANATION of the canonical
Context State / AHF machine — it does NOT recompute AHF rules and it is NOT a
second setup FSM.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.replay import ReplayConfig, run_visual_replay
from backtest.schema import validate_visual_backtest
from backtest.setup_builder import SETUP_STATES, build_setup_state
from engine.ahf import AHFEvent, AHFSnapshot, AHFState, AHFTransition


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


def test_setups_have_one_entry_per_visible_candle():
    payload = _artifact().to_dict()
    assert len(payload["setups"]) == len(payload["candles"])
    for setup, point in zip(payload["setups"], payload["timeline"], strict=True):
        assert setup["decision_time"] == point["decision_time"]
        assert setup["estado"] in SETUP_STATES
        assert setup["policy"] == "CONTEXT_STATE_NOT_ENTRY_SIGNAL"
        assert isinstance(setup["condiciones_presentes"], list)
        assert isinstance(setup["condiciones_faltantes"], list)


def test_setup_state_is_deterministic():
    first = _artifact(40).to_dict()["setups"]
    second = _artifact(40).to_dict()["setups"]
    assert first == second


def test_setup_state_does_not_recompute_ahf():
    """The setup builder must project the canonical AHF funnel, not re-derive it.

    The replay serializes the REAL AdaptiveHierarchicalFunnel AHFSnapshot into
    timeline[i]["ict"]["context"]["ahf_snapshot"]. build_setup_state must translate
    exactly that snapshot. This test asserts every projected Setup State matches the
    canonical AHFSnapshot the replay produced (state, active_tf, invalidation). A
    passing test proves build_setup_state is a pure adapter, not a second FSM.
    """
    payload = run_visual_replay(
        {"H1": _fixture(60, freq="h")},
        ReplayConfig(
            symbol="TEST", timeframe="H1", timeframes=("H1",),
            authority_tf="H1", warmup_bars=0, wyckoff_enabled=False,
            git_commit="fixture-commit",
        ),
    ).to_dict()

    setups = payload["setups"]
    for setup, point in zip(setups, payload["timeline"]):
        ctx = point.get("ict", {}).get("context", {})
        snap = ctx.get("ahf_snapshot")
        assert snap is not None, "replay must serialize AHFSnapshot into ict.context"
        assert setup["estado"] == snap["state"], (
            f"setup state {setup['estado']!r} != AHF {snap['state']!r}"
        )
        assert setup["active_tf"] == snap["active_tf"]
        inv = snap.get("invalidation_reason")
        if inv:
            assert inv in setup["invalidacion"]
        else:
            assert setup["invalidacion"] == []


def test_artifact_with_setups_validates():
    payload = _artifact(32).to_dict()
    validate_visual_backtest(payload)


def test_setup_projection_preserves_invalidation_from_canonical_history():
    snapshot = AHFSnapshot(
        decision_time="2024-01-01T01:00:00+00:00",
        state=AHFState.WAIT_H1,
        active_tf="H1",
        confirmed_context={"D1": {"layer": "D1"}},
        constraints=None,
        history=[AHFTransition(
            state=AHFState.WAIT_H1.value,
            active_tf="H1",
            transition_event=AHFEvent.H1_INVALIDATED.value,
            transition_time="2024-01-01T01:00:00+00:00",
            parent_state=AHFState.SETUP_READY.value,
            invalidation_reason="H1 BOS down vs D1 bull lock",
        )],
        last_event=AHFEvent.H1_INVALIDATED,
    )
    timeline = [{"index": 0, "decision_time": snapshot.decision_time}]
    config = ReplayConfig(
        symbol="TEST", timeframe="H1", timeframes=("H1",), authority_tf="H1",
        warmup_bars=0, wyckoff_enabled=False, git_commit="fixture-commit",
    )
    setup = build_setup_state(timeline, config, ahf_snapshots=[snapshot])[0]
    assert setup["estado"] == AHFState.WAIT_H1.value
    assert setup["invalidacion"] == ["H1 BOS down vs D1 bull lock"]


def test_replay_fails_closed_when_canonical_ahf_fails(monkeypatch):
    import backtest.replay as replay_module

    class BrokenAHF:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("fixture AHF failure")

    monkeypatch.setattr(replay_module, "AdaptiveHierarchicalFunnel", BrokenAHF)
    with pytest.raises(RuntimeError, match="canonical AHF projection failed"):
        _artifact(20)
