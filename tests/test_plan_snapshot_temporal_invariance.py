"""Point-in-time contract for structural snapshots.

The H4/D1/H1 context frozen at a decision time must be identical whether the
caller has only the historical prefix or has also loaded later candles.  A
later CHOCH can supersede the bias for a *later* decision, but cannot rewrite
the past snapshot.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import engine.plan as plan


def _h4_frame() -> pd.DataFrame:
    times = pd.date_range("2022-06-01T00:00:00Z", periods=5, freq="4h")
    return pd.DataFrame(
        {
            "time": times,
            "open": [1.10, 1.11, 1.12, 1.11, 1.10],
            "high": [1.11, 1.12, 1.13, 1.12, 1.11],
            "low": [1.09, 1.10, 1.11, 1.10, 1.09],
            "close": [1.10, 1.11, 1.12, 1.11, 1.10],
            # The bullish BOS is known at 04:00. The bearish CHOCH at
            # 12:00 is deliberately a future event from the 08:00 decision.
            "bos_dir": [0, 1, 0, 0, 0],
            "bos_status": ["none", "active", "none", "none", "none"],
            "choch_dir": [0, 0, 0, -1, 0],
            "choch_status": ["none", "none", "none", "active", "none"],
        }
    )


def test_snapshot_tf_is_invariant_when_future_choch_supersedes_bias(monkeypatch):
    """A future structural reversal must not change the bias stored at t."""
    full = _h4_frame()
    decision_time = full.loc[2, "time"]  # 08:00; future CHOCH is 12:00.
    historical_prefix = full.iloc[:3].copy()

    # The production detector is separately tested. Here its output is kept
    # deterministic so this test isolates the snapshot contract: it must pass
    # only the point-in-time prefix to structural interpretation.
    monkeypatch.setattr(
        plan,
        "detect_market_structure",
        lambda frame, _config: SimpleNamespace(frame=frame),
    )

    from_prefix = plan.snapshot_tf({"H4": historical_prefix}, "H4", decision_time)
    with_future_loaded = plan.snapshot_tf({"H4": full}, "H4", decision_time)

    assert from_prefix == with_future_loaded
    assert from_prefix["trend"] == "BULLISH"
    assert from_prefix["asof_time"] == str(decision_time)
    assert from_prefix["asof_bar"] == 2

    # The later decision may correctly observe the later reversal. This makes
    # the test sensitive to accidentally filtering all CHOCH events.
    later = plan.snapshot_tf({"H4": full}, "H4", full.loc[3, "time"])
    assert later["trend"] == "BEARISH"
