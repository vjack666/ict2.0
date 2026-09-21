from __future__ import annotations

import pandas as pd

from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.poi_anchor import _ParentEvent, resolve_htf_poi_event
from engine.sequence import (
    SequenceConfig,
    SequenceState,
    _freeze_context_anchor,
    run_sequence_traced,
)


def _bullish(_i):
    return {"trend": "BULLISH", "sweep_up": False, "sweep_down": False}


def _frame(*, all_flags_on_sweep: bool = False) -> pd.DataFrame:
    rows = []
    for i in range(6):
        rows.append(
            {
                "time": pd.Timestamp("2026-01-01T10:00:00Z") + pd.Timedelta(minutes=15 * i),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "atr": 2.0,
                "liquidity_sweep_down": False,
                "liquidity_sweep_up": False,
                "displacement_bullish": False,
                "displacement_bearish": False,
                "bos_dir": 0,
                "choch_dir": 0,
                "bos_level": float("nan"),
                "fvg_bullish": False,
                "fvg_bearish": False,
                "ob_direction": "-",
                "ob_bullish": False,
                "ob_bearish": False,
            }
        )
    rows[1]["liquidity_sweep_down"] = True
    if all_flags_on_sweep:
        rows[1]["displacement_bullish"] = True
        rows[1]["bos_dir"] = 1
        rows[1]["bos_level"] = 101.0
        rows[1]["fvg_bullish"] = True
    else:
        rows[2]["displacement_bullish"] = True
        rows[2]["fvg_bullish"] = True
        rows[2]["low"] = 100.0
        rows[2]["high"] = 101.0
        rows[3]["bos_dir"] = 1
        rows[3]["bos_level"] = 101.0
        rows[4]["low"] = 100.25
        rows[4]["high"] = 100.75
        rows[4]["close"] = 100.5
    return pd.DataFrame(rows)


def _context_obj(time: str = "2026-01-01T09:00:00Z") -> MarketObject:
    ts = pd.Timestamp(time)
    return MarketObject(
        id="HTF_CONTEXT_H4_BOS_TEST",
        symbol="EURUSD",
        type=ObjectType.BOS,
        origin_tf="H4",
        role=Role.CONTEXT,
        direction=1,
        zone_low=100.0,
        zone_high=100.0,
        creation_time=ts,
        state=ObjectState.ACTIVE,
        bar_index=777,
        bar_time=ts,
        candidate_bar=777,
        candidate_time=ts,
        confirmation_bar=777,
        confirmation_time=ts,
        tradable_bar=777,
        tradable_time=ts,
        meta={"context_only": True},
    )


def _six_tf_context() -> dict:
    out = {}
    for n, tf in enumerate(("D1", "H4", "H1", "M15", "M5", "M1")):
        out[tf] = {
            "tf": tf,
            "available": True,
            "asof_time": f"2026-01-01T0{min(n,9)}:00:00Z",
            "asof_bar": 100 + n,
            "trend": "BULLISH",
            "bos_dir": 1,
            "sweep_up": False,
            "sweep_down": tf == "M15",
            "pd_side": "DISCOUNT" if tf in {"D1", "H4"} else "UNKNOWN",
        }
    return out


def test_htf_parent_resolution_uses_real_time_not_cross_tf_bar_index():
    events = [
        _ParentEvent(pd.Timestamp("2026-01-01T09:00:00Z"), 1, "BOS", "H4", 1.10, 999999),
        _ParentEvent(pd.Timestamp("2026-01-01T09:30:00Z"), -1, "CHOCH", "H1", 1.09, 2),
    ]
    found = resolve_htf_poi_event(events, "2026-01-01T10:00:00Z", 1)
    assert found is not None
    assert found.tf == "H4"
    assert found.bar_index == 999999
    assert found.time == pd.Timestamp("2026-01-01T09:00:00Z")


def test_same_close_htf_parent_is_rejected_in_strict_mode():
    events = [
        _ParentEvent(pd.Timestamp("2026-01-01T09:00:00Z"), 1, "BOS", "H4", 1.10, 1),
        _ParentEvent(pd.Timestamp("2026-01-01T10:00:00Z"), 1, "BOS", "H1", 1.11, 2),
    ]
    found = resolve_htf_poi_event(events, "2026-01-01T10:00:00Z", 1, strict_before=True)
    assert found is not None
    assert found.time == pd.Timestamp("2026-01-01T09:00:00Z")


def test_birth_snapshot_freezes_all_six_timeframes():
    anchor = _freeze_context_anchor(
        _six_tf_context(), "H4", {"trend": "BULLISH"}, "2026-01-01T10:15:00Z"
    )
    assert tuple(anchor["layers"].keys()) == ("D1", "H4", "H1", "M15", "M5", "M1")
    assert all(anchor["layers"][tf]["available"] for tf in anchor["layers"])


def test_one_candle_cannot_complete_multiple_core_sequence_stages():
    audit = {}
    signals, phase_seen, _exp, state = run_sequence_traced(
        _frame(all_flags_on_sweep=True),
        _bullish,
        SequenceConfig(invalidate_on_opposite_swing=False),
        ltf_tf="M15",
        htf="H4",
        audit=audit,
    )
    assert signals == []
    assert phase_seen == {"SWEEP": 1, "DISPLACE": 0, "BOS": 0, "ENTRY": 0}
    assert state.phase == "SWEEP_DONE"
    assert audit["policy"]["strict_later_bar_per_core_stage"] is True


def test_multibar_sequence_is_strict_and_preserves_real_htf_context():
    ctx = _context_obj()
    signals, phase_seen, expedientes, state = run_sequence_traced(
        _frame(),
        _bullish,
        SequenceConfig(invalidate_on_opposite_swing=False),
        ltf_tf="M15",
        htf="H4",
        htf_context_object_fn=lambda _i, _d: ctx,
        audit={},
    )
    assert phase_seen == {"SWEEP": 1, "DISPLACE": 1, "BOS": 1, "ENTRY": 1}
    assert len(signals) == 1
    sig = signals[0]
    assert (sig["sweep_at"], sig["displace_at"], sig["bos_at"], sig["entry_at"]) == (1, 2, 3, 4)
    assert sig["strict_multibar_core"] is True
    assert sig["sequence_span_bars"] == 3
    assert sig["event_ids"]["CONTEXT"] == ctx.id
    context_dict = sig["event_objects"][ctx.id]
    assert context_dict["origin_tf"] == "H4"
    assert context_dict["role"] == "CONTEXT"
    assert pd.Timestamp(context_dict["tradable_time"]) < pd.Timestamp(sig["time"])
    assert len(expedientes) == 1
    assert state.phase == "IDLE"


def test_sequence_state_roundtrip_preserves_context_lineage():
    ctx = _context_obj()
    state = SequenceState(phase="SWEEP_DONE", direction=1, sweep_idx=3)
    state.context_id = ctx.id
    state.event_objs[ctx.id] = ctx
    restored = SequenceState.from_snapshot(state.to_snapshot())
    assert restored.context_id == ctx.id
    assert restored.event_objs[ctx.id].origin_tf == "H4"
    assert restored.event_objs[ctx.id].role is Role.CONTEXT
    assert pd.Timestamp(restored.event_objs[ctx.id].tradable_time) == pd.Timestamp(ctx.tradable_time)
