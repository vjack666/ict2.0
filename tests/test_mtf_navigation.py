"""Tests del grafo de navegación multi-TF (Context State)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine.mtf_navigation import (
    MTFNavigator,
    NavigatorConfig,
    NavQuestion,
    StructureBias,
    TimeframeLayer,
)


def _ohlc(n: int, start: float = 1.10, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = start + np.cumsum(rng.normal(0, 0.0005, n))
    high = close + rng.uniform(0.0002, 0.0008, n)
    low = close - rng.uniform(0.0002, 0.0008, n)
    open_ = close + rng.normal(0, 0.0001, n)
    time = pd.date_range("2020-01-01", periods=n, freq="h")
    return pd.DataFrame({"time": time, "open": open_, "high": high, "low": low, "close": close})


def test_navigate_returns_context_not_entry():
    h1 = _ohlc(500, seed=1)
    h4 = _ohlc(200, seed=2)
    d1 = _ohlc(80, seed=3)
    # Align times roughly: use last H1 time
    nav = MTFNavigator({"D1": d1, "H4": h4, "H1": h1})
    state = nav.navigate(decision_time=h1["time"].iloc[-2], exec_tf="H1")
    assert state.constraints is not None
    assert state.constraints.to_dict()["policy"] == "CONTEXT_ONLY_NOT_ENTRY"
    assert "entry" not in state.to_dict()
    assert state.to_dict()["policy"] == "CONTEXT_STATE_NOT_ENTRY_SIGNAL"


def test_asof_ignores_future_htf_bars():
    h1 = _ohlc(100, seed=4)
    d1 = _ohlc(30, seed=5)
    # Force D1 last bars far in the future relative to mid H1
    d1 = d1.copy()
    d1["time"] = pd.date_range("2019-01-01", periods=len(d1), freq="D")
    decision = h1["time"].iloc[50]
    nav = MTFNavigator({"D1": d1, "H1": h1})
    state = nav.navigate(decision_time=decision, exec_tf="H1")
    if "D1" in state.layers:
        assert pd.Timestamp(state.layers["D1"].asof_time) <= pd.Timestamp(decision)


def test_path_has_ordered_questions():
    h1 = _ohlc(400, seed=6)
    h4 = _ohlc(120, seed=7)
    d1 = _ohlc(40, seed=8)
    nav = MTFNavigator({"D1": d1, "H4": h4, "H1": h1})
    state = nav.navigate(decision_time=h1["time"].iloc[-5], exec_tf="H1")
    qs = [s["question"] for s in state.path.steps]
    # D1 context question should appear before H1 structure if D1 present
    if NavQuestion.HAS_RELEVANT_CONTEXT.value in qs and NavQuestion.HAS_STRUCTURE.value in qs:
        assert qs.index(NavQuestion.HAS_RELEVANT_CONTEXT.value) < qs.index(NavQuestion.HAS_STRUCTURE.value)


def test_missing_layer_marks_incomplete():
    h1 = _ohlc(100, seed=9)
    nav = MTFNavigator({"H1": h1})  # no D1/H4
    state = nav.navigate(decision_time=h1["time"].iloc[-1], exec_tf="H1")
    assert state.status == "INCOMPLETE"


def test_full_prefix_market_state_is_identical_at_every_decision():
    """The complete MarketState must not depend on bars after the decision."""
    frames = {tf: _ohlc(140, seed=100 + i) for i, tf in enumerate(("D1", "H4", "H1"))}
    full = MTFNavigator(frames, NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))

    for i in range(30, len(frames["H1"])):
        decision_time = frames["H1"]["time"].iloc[i]
        prefix = {
            tf: df.loc[df["time"] <= decision_time].copy().reset_index(drop=True)
            for tf, df in frames.items()
        }
        pref = MTFNavigator(
            prefix,
            NavigatorConfig(precompute_sequences=True, sequence_tf="H1"),
        )
        assert full.navigate(decision_time, exec_tf="H1").to_dict() == pref.navigate(
            decision_time, exec_tf="H1"
        ).to_dict(), f"FULL-vs-PREFIX divergence at H1 bar {i}"
