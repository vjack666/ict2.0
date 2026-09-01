from __future__ import annotations

import pandas as pd

from engine.Wyckoff import (
    WyckoffEventType,
    WyckoffPhaseState,
    build_wyckoff_snapshot,
)
from engine.Wyckoff.classifier import classify_alignment
from engine.Wyckoff.types import WyckoffPhase
from engine.daily_motor import DailyMotorConfig, build_daily_motor_snapshot


def _frame(direction: str = "BULLISH", n: int = 20) -> pd.DataFrame:
    times = pd.date_range("2020-01-01", periods=n, freq="h")
    base = [1.10 + i * 0.002 for i in range(n)] if direction == "BULLISH" else [1.20 - i * 0.002 for i in range(n)]
    return pd.DataFrame(
        {
            "time": times,
            "open": base,
            "high": [v + 0.001 for v in base],
            "low": [v - 0.001 for v in base],
            "close": base,
            "trend": [direction] * n,
            "tick_volume": [100] * n,
        }
    )


def _context(direction: str = "BULLISH") -> dict:
    return {
        "constraints": {
            "direction_hint": direction,
            "sequence_required": True,
        },
        "status": "OK",
    }


def test_wyckoff_snapshot_is_serializable_and_has_explicit_authority():
    frames = {tf: _frame() for tf in ("D1", "H4", "H1", "M15")}
    snapshot = build_wyckoff_snapshot(
        frames,
        pd.Timestamp("2020-01-01 19:00", tz="UTC"),
        context_state=_context(),
        authority_tf="D1",
    )
    data = snapshot.to_dict()
    assert data["authority_tf"] == "D1"
    assert data["phase_state"] == WyckoffPhaseState.PRO_TREND.value
    assert set(data["layers"]) == {"D1", "H4", "H1", "M15"}
    assert data["policy"] == "WYCKOFF_CONTEXT_ONLY_NOT_ENTRY"


def test_spring_event_is_causal_and_future_does_not_change_snapshot():
    frame = _frame(direction="BEARISH", n=10)
    frame.loc[9, "low"] = 1.05
    frame.loc[9, "close"] = 1.19
    frame.loc[9, "open"] = 1.10
    frame.loc[9, "high"] = 1.16
    decision_time = pd.Timestamp("2020-01-01 09:00", tz="UTC")
    before = build_wyckoff_snapshot({"D1": frame}, decision_time, context_state=_context("BULLISH"))
    future = pd.DataFrame(
        {
            "time": [pd.Timestamp("2020-01-01 12:00")],
            "open": [1.15], "high": [1.18], "low": [1.14], "close": [1.17], "tick_volume": [300],
        }
    )
    after = build_wyckoff_snapshot(
        {"D1": pd.concat([frame, future], ignore_index=True)},
        decision_time,
        context_state=_context("BULLISH"),
    )
    assert before.to_dict() == after.to_dict()
    assert any(event["event_type"] == WyckoffEventType.SPRING.value for event in before.to_dict()["events"])
    assert before.to_dict()["phase_state"] == WyckoffPhaseState.COUNTERTREND.value


def test_conflict_is_evidence_and_never_changes_ict_direction_or_entry_policy():
    frames = {tf: _frame(direction="BEARISH") for tf in ("D1", "H4", "H1", "M15")}
    snapshot = build_wyckoff_snapshot(
        frames,
        pd.Timestamp("2020-01-01 19:00", tz="UTC"),
        context_state=_context("BULLISH"),
        authority_tf="D1",
    )
    result = build_daily_motor_snapshot(
        frames,
        decision_time=pd.Timestamp("2020-01-01 19:00", tz="UTC"),
        config=DailyMotorConfig(require_d1=False, require_itf=False, require_context=False, require_pd=False),
        context_snapshot={"direction_hint": "BULLISH"},
        wyckoff_snapshot=snapshot,
    )
    assert result["direction_label"] == "BULLISH"
    assert result["wyckoff"]["conflict"] is True
    assert result["entry_authorized"] is False


def test_all_integrated_phase_states_are_explicit():
    assert classify_alignment(WyckoffPhase.MARKUP, 1)[0] is WyckoffPhaseState.PRO_TREND
    assert classify_alignment(WyckoffPhase.MARKDOWN, 1)[0] is WyckoffPhaseState.TRANSITION
    assert classify_alignment(WyckoffPhase.TRANSITION, 1)[0] is WyckoffPhaseState.TRANSITION
    assert classify_alignment(WyckoffPhase.UNKNOWN, 1)[0] is WyckoffPhaseState.NEUTRAL
