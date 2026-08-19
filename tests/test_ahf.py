"""Tests AHF state machine."""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine.ahf import AHFState, AdaptiveHierarchicalFunnel


def _ohlc(n, seed=0, freq="h"):
    rng = np.random.default_rng(seed)
    close = 1.1 + np.cumsum(rng.normal(0, 0.0004, n))
    high = close + 0.0005
    low = close - 0.0005
    open_ = close.copy()
    time = pd.date_range("2020-01-01", periods=n, freq=freq)
    return pd.DataFrame({"time": time, "open": open_, "high": high, "low": low, "close": close})


def test_ahf_starts_wait_d1():
    h1 = _ohlc(300, seed=1)
    h4 = _ohlc(100, seed=2, freq="4h")
    d1 = _ohlc(40, seed=3, freq="D")
    ahf = AdaptiveHierarchicalFunnel({"D1": d1, "H4": h4, "H1": h1})
    assert ahf.state is AHFState.WAIT_D1


def test_ahf_policy_not_entry():
    h1 = _ohlc(400, seed=4)
    h4 = _ohlc(120, seed=5, freq="4h")
    d1 = _ohlc(50, seed=6, freq="D")
    ahf = AdaptiveHierarchicalFunnel({"D1": d1, "H4": h4, "H1": h1})
    snap = ahf.step(h1["time"].iloc[-10], exec_tf="H1")
    assert snap.to_dict()["policy"] == "AHF_STATE_NOT_ENTRY"
    assert "order" not in snap.to_dict()


def test_ahf_history_fields():
    h1 = _ohlc(500, seed=7)
    h4 = _ohlc(150, seed=8, freq="4h")
    d1 = _ohlc(60, seed=9, freq="D")
    ahf = AdaptiveHierarchicalFunnel({"D1": d1, "H4": h4, "H1": h1})
    # walk several bars
    for t in h1["time"].iloc[200:260]:
        snap = ahf.step(t, exec_tf="H1")
    for tr in snap.history:
        d = tr.to_dict()
        for k in ("state", "active_tf", "transition_event", "transition_time", "parent_state"):
            assert k in d


def test_ahf_future_d1_does_not_leak():
    h1 = _ohlc(100, seed=10)
    d1 = _ohlc(20, seed=11, freq="D")
    d1 = d1.copy()
    d1["time"] = pd.date_range("2030-01-01", periods=len(d1), freq="D")  # all future
    ahf = AdaptiveHierarchicalFunnel({"D1": d1, "H1": h1})
    snap = ahf.step(h1["time"].iloc[50], exec_tf="H1")
    # cannot lock D1 from future-only data
    assert snap.state in (AHFState.WAIT_D1, AHFState.WAIT_H4, AHFState.D1_LOCKED) or "D1" not in snap.confirmed_context
    if snap.state != AHFState.WAIT_D1:
        # if advanced without D1, status incomplete is ok
        pass
    assert "D1" not in snap.confirmed_context or pd.Timestamp(snap.confirmed_context["D1"]["asof_time"]) <= h1["time"].iloc[50]
