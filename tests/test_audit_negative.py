"""Pruebas negativas del auditor (Codex H1-H4) — ejecutadas por Agente 5."""
import sys
from datetime import datetime, timezone

import pytest
from engine.market_state import MarketState
from engine.market_object import MarketObject, ObjectType, ObjectState, Role
from engine import lifecycle
from engine.setup_builder import build_setups_at, classify_eligibility, Setup, SetupEligibility


def _ts(n):
    return datetime(2026, 1, 1, 0, n, 0, tzinfo=timezone.utc)


def _obj(oid, ot, tf, t, role=Role.POI, state=ObjectState.ACTIVE, direction=1):
    return MarketObject(
        id=oid, symbol="EURUSD", type=ot, role=role, origin_tf=tf,
        creation_time=_ts(t), state=state,
        zone_low=1.0, zone_high=2.0, direction=direction,
        authority_tf=tf, lifecycle_tf=tf, observation_tf=tf, execution_tf=tf,
    )


def test_H1_snapshot_no_lookahead():
    ms = MarketState()
    ob = _obj("OB1", ObjectType.ORDER_BLOCK, "H4", 10)
    ms.ingest(ob)
    ms.advance_bar("OB1", {"tf": "H4", "time": _ts(10), "index": 10, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5})
    state_t10 = ms.state_at("OB1", _ts(10))
    # Invalidar en T=13
    ms.advance_bar("OB1", {"tf": "H4", "time": _ts(13), "index": 13, "open": 1.0, "high": 2.0, "low": 0.5, "close": 0.4})
    assert ms.state_at("OB1", _ts(13)) == ObjectState.INVALIDATED
    # snapshot en T=10 NO debe mostrar INVALIDATED (sin look-ahead)
    assert ms.state_at("OB1", _ts(10)) == state_t10
    assert ms.state_at("OB1", _ts(10)) != ObjectState.INVALIDATED
    snap10 = ms.snapshot_at(_ts(10))
    assert "OB1" not in snap10["dead_ids"]
    proj = ms.projection_at(_ts(10))
    assert "OB1" in proj and proj["OB1"].state != ObjectState.INVALIDATED


def test_H3_bearish_under_bullish_blocked():
    ms = MarketState()
    ob = _obj("OB1", ObjectType.ORDER_BLOCK, "H4", 10, direction=-1)
    ms.ingest(ob)
    ctx = {"htf_bias": "bullish"}
    s = Setup(symbol="EURUSD", direction=-1, poi=ob)
    elig = classify_eligibility(s, ctx)
    assert elig == SetupEligibility.BLOCKED, f"esperado BLOCKED, got {elig}"


def test_H2_incomplete_setup_blocked():
    ms = MarketState()
    ob = _obj("OB1", ObjectType.ORDER_BLOCK, "H4", 10)
    ms.ingest(ob)
    ctx = {"htf_bias": "bullish"}
    # Sin confirmation ni trigger => require_complete debe bloquear
    s = Setup(symbol="EURUSD", direction=1, poi=ob, refinement=ob)
    elig = classify_eligibility(s, ctx, require_complete=True)
    assert elig == SetupEligibility.BLOCKED


def test_H4_m15_later_by_timestamp_lower_index_observed():
    # OB H4 con tradable en índice 10; vela M15 índice 5 (menor) pero timestamp posterior
    ob = _obj("OB1", ObjectType.ORDER_BLOCK, "H4", 10)
    ob.tradable_bar = 10
    bar_m15 = {"tf": "M15", "time": _ts(20), "index": 5, "open": 1.0, "high": 2.0, "low": 0.9, "close": 1.1}
    dec = lifecycle.observe_lower_tf(ob, bar_m15, observed_tf="M15", decision_time=_ts(20))
    assert dec.changed is True or dec.reason != "BEFORE_TRADABLE", f"M15 posterior debe observarse, got {dec.reason}"


def test_H4_disguised_tf_rejected():
    ob = _obj("OB1", ObjectType.ORDER_BLOCK, "H4", 10)
    bar_m15 = {"tf": "M15", "time": _ts(11), "index": 11, "open": 1.0, "high": 2.0, "low": 0.9, "close": 1.1}
    with pytest.raises(ValueError):
        lifecycle.observe_lower_tf(ob, bar_m15, observed_tf="H4", decision_time=_ts(11))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-q"]))
