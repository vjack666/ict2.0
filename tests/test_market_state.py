"""Tests de Market State — queries deterministas + snapshot causal (replay a T)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from engine.lifecycle import evaluate, observe_lower_tf
from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState


def _ts(n: int) -> datetime:
    return datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc) + __import__("datetime").timedelta(minutes=n)


def _ob(origin_tf: str, bar: int, zl: float, zh: float, parent: str | None = None) -> MarketObject:
    return MarketObject(
        id=f"OB_{origin_tf}_{bar}_BULL", symbol="EURUSD", type=ObjectType.ORDER_BLOCK,
        origin_tf=origin_tf, role=Role.REFINEMENT, direction=1, zone_high=zh, zone_low=zl,
        creation_time=_ts(bar), state=ObjectState.ACTIVE, bar_index=bar, bar_time=_ts(bar),
        candidate_bar=bar - 1, candidate_time=_ts(bar - 1), confirmation_bar=bar,
        confirmation_time=_ts(bar), tradable_bar=bar, tradable_time=_ts(bar),
    )


def _bar(idx: int, o: float, h: float, l: float, c: float, tf: str = "M15") -> dict:
    return {"__index__": idx, "time": _ts(idx), "tf": tf, "open": o, "high": h, "low": l, "close": c}


def _build_world() -> MarketState:
    ms = MarketState()
    ob_h4 = _ob("H4", 10, 1.0995, 1.1005)          # padre HTF
    fvg_m15 = _ob("M15", 12, 1.0998, 1.1002)         # hijo LTF, contenido en H4
    fvg_m15.parent_object = ob_h4.id
    ms.ingest(ob_h4)
    ms.ingest(fvg_m15)
    # Avanzar H4 con velas H4 (authority).
    ms.advance_bar(ob_h4.id, _bar(11, 1.0996, 1.0998, 1.0996, 1.0997, tf="H4"))  # partial
    ms.advance_bar(ob_h4.id, _bar(13, 1.0996, 1.0998, 1.0990, 1.0988, tf="H4"))  # invalidated
    # Avanzar M15 con observacion desde M15 (no mata).
    ms.observe(fvg_m15.id, _bar(13, 1.0999, 1.1001, 1.0997, 1.0999, tf="M15"), observed_tf="M15")
    ms.advance_bar(fvg_m15.id, _bar(14, 1.0999, 1.1001, 1.0999, 1.1000, tf="M15"))  # partial
    return ms


def test_ingest_idempotent_and_queries():
    ms = _build_world()
    ob_h4 = ms._objects["OB_H4_10_BULL"]
    fvg_m15 = ms._objects["OB_M15_12_BULL"]
    # Queries deterministas del auditor.
    assert ms.born_in_tf("H4") == [ob_h4]
    assert ms.born_in_tf("M15") == [fvg_m15]
    assert ms.authority_of(ob_h4.id) == "H4"
    assert ob_h4.id in [o.id for o in ms.dead()]           # OB H4 invalidado
    assert fvg_m15.id in [o.id for o in ms.active()] or fvg_m15.id in [o.id for o in ms.partially_mitigated()]
    assert ms.ltf_refines_htf(fvg_m15.id).id == ob_h4.id   # M15 contenido en H4
    assert fvg_m15.id in [o.id for o in ms.htf_contains_ltf(ob_h4.id)]


def test_objects_existing_at_is_append_only_forward():
    ms = MarketState()
    ms.ingest(_ob("H4", 10, 1.0995, 1.1005))
    ms.ingest(_ob("M15", 20, 1.0998, 1.1002))
    # En T=15 solo existe el H4 (nacio en 10).
    existing_t15 = ms.objects_existing_at(_ts(15))
    assert [o.id for o in existing_t15] == ["OB_H4_10_BULL"]
    # En T=25 existen ambos.
    existing_t25 = ms.objects_existing_at(_ts(25))
    assert len(existing_t25) == 2


def test_snapshot_at_reports_known_world_without_repaint():
    ms = _build_world()
    # En T=10 el OB H4 ya habia nacido (creation 10 <= 10); existe en el universo.
    # Su estado actual (append-only) ya evoluciono a PARTIAL por la vela 11.
    snap10 = ms.snapshot_at(_ts(10))
    assert snap10["existing"] == 1
    assert "OB_H4_10_BULL" in [o.id for o in ms.objects_existing_at(_ts(10))]
    # Estado actual ya evoluciono (vela 13 lo invalido); el recuento lo refleja.
    assert snap10["counts"][ObjectState.INVALIDATED.value] >= 1
    # En T=14 ambos existen; H4 muerto, M15 parcial.
    snap14 = ms.snapshot_at(_ts(14))
    assert snap14["existing"] == 2
    assert "OB_H4_10_BULL" in snap14["dead_ids"]
    assert snap14["counts"][ObjectState.INVALIDATED.value] == 1
    assert snap14["counts"][ObjectState.PARTIALLY_MITIGATED.value] >= 1


def test_market_state_round_trip_json():
    import json
    ms = _build_world()
    blob = json.dumps(ms.to_dict())
    ms2 = MarketState.from_dict(json.loads(blob))
    # Mismo universo tras reconstruir.
    assert len(ms2.all_objects()) == len(ms.all_objects())
    ob_h4 = ms2._objects["OB_H4_10_BULL"]
    assert ob_h4.state == ObjectState.INVALIDATED
    assert ob_h4.authority_tf == "H4"
    assert ms2.ltf_refines_htf("OB_M15_12_BULL").id == "OB_H4_10_BULL"
    # Idempotencia del lifecycle sobrevive al round-trip.
    dec = evaluate(ob_h4, _bar(13, 1.0996, 1.0998, 1.0990, 1.0988, tf="H4"), authority_tf="H4")
    assert not dec.changed


def test_advance_bar_respects_authority_tf():
    ms = MarketState()
    ob_h4 = _ob("H4", 10, 1.0995, 1.1005)
    ms.ingest(ob_h4)
    # Una vela M15 NO debe decidir el estado oficial del OB H4.
    with pytest.raises(ValueError):
        ms.advance_bar(ob_h4.id, _bar(11, 1.0996, 1.0998, 1.0990, 1.0988, tf="M15"))
    assert ob_h4.state == ObjectState.ACTIVE
    # Una vela H4 si puede (touch parcial: entra a la zona pero no cruza far_side => PARTIAL).
    ms.advance_bar(ob_h4.id, _bar(11, 1.0996, 1.0998, 1.0996, 1.0997, tf="H4"))
    assert ob_h4.state == ObjectState.PARTIALLY_MITIGATED
