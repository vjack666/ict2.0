from __future__ import annotations

import pandas as pd

from engine.daily_motor import DailyMotorConfig, build_daily_motor_snapshot


def _frame(tf: str, n: int = 30, *, trend: str = "BULLISH", future: bool = False) -> pd.DataFrame:
    start = "2030-01-01" if future else "2020-01-01"
    t = pd.date_range(start, periods=n, freq="h")
    close = [1.1000 + i * 0.0001 for i in range(n)]
    return pd.DataFrame(
        {
            "time": t,
            "open": close,
            "high": [x + 0.0002 for x in close],
            "low": [x - 0.0002 for x in close],
            "close": close,
            "trend": [trend] * n,
            "bos_dir": [1] * n if trend == "BULLISH" else [-1] * n,
            "bos_status": ["active"] * n,
            "fvg_state": ["ACTIVE"] * n if tf == "M15" else ["NONE"] * n,
            "ob_direction": ["BULLISH"] * n if tf == "M15" else ["-"] * n,
        }
    )


def _frames() -> dict[str, pd.DataFrame]:
    return {tf: _frame(tf) for tf in ("D1", "H4", "H1", "M15")}


def test_daily_motor_is_observe_only_and_reports_ltf():
    result = build_daily_motor_snapshot(_frames(), decision_time=pd.Timestamp("2020-01-02"))
    assert result["policy"] == "OBSERVE_ONLY_NO_ORDER"
    assert result["entry_authorized"] is False
    assert "entry" not in result
    assert result["ltf"]["tf"] == "M15"
    assert result["ltf"]["zone_present"] is True


def test_daily_motor_ignores_future_ltf_and_htf_rows():
    frames = _frames()
    t = pd.Timestamp("2020-01-01 12:00", tz="UTC")
    before = build_daily_motor_snapshot(frames, decision_time=t)
    for tf in frames:
        frames[tf] = pd.concat([frames[tf], _frame(tf, n=5, future=True)], ignore_index=True)
    after = build_daily_motor_snapshot(frames, decision_time=t)
    assert after["decision_time"] == before["decision_time"]
    assert after["direction"] == before["direction"]
    assert after["status"] == before["status"]
    assert after["ltf"]["asof_time"] == before["ltf"]["asof_time"]


def test_daily_motor_missing_context_does_not_promote_ltf():
    frames = {"M15": _frame("M15")}
    result = build_daily_motor_snapshot(
        frames,
        decision_time=pd.Timestamp("2020-01-02"),
        config=DailyMotorConfig(require_d1=False, require_itf=False, require_context=False, require_pd=False),
    )
    assert result["status"] in {"WAIT_CONTEXT", "WAIT_LTF_CONFIRMATION", "WAIT_LTF_ZONE", "WAIT_RETEST"}
    assert result["entry_authorized"] is False
