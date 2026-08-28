"""Tests de autoridad de lifecycle (MarketObject) — gates congelados v1.

Cubre los 8 gates exigidos + la guarda PIT (nada antes de tradable_time):
  1. PIT / zero-lookahead (FULL vs PREFIX idéntico hasta t)
  2. Simetría bullish/bearish
  3. Autoridad MTF: M15 no invalida OB H4
  4. Terminalidad: objeto terminal no resucita
  5. Idempotencia: doble proceso de la misma vela => sin 2ª transición
  6. Timestamp exacto: first_touch_bar / invalidated_bar / decision_time
  7. Precedencia: fill + cierre allá => INVALIDATED > MITIGATED
  8. Replay pequeño real: secuencia de estados inspeccionable vela a vela
  + PIT tradable_time: sin toque/mitigación antes de tradable_time
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from engine.lifecycle import evaluate, observe_lower_tf
from engine.market_object import MarketObject, ObjectState, ObjectType, Role


def _ts(n: int) -> datetime:
    return datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc) + __import__("datetime").timedelta(minutes=n)


def _fvg_bull(bar: int, zone_low: float, zone_high: float) -> MarketObject:
    return MarketObject(
        id=f"FVG_M15_{bar}_BULL", symbol="EURUSD", type=ObjectType.FVG, origin_tf="M15",
        role=Role.REFINEMENT, direction=1, zone_high=zone_high, zone_low=zone_low,
        creation_time=_ts(bar), state=ObjectState.ACTIVE, bar_index=bar, bar_time=_ts(bar),
        candidate_bar=bar - 2, candidate_time=_ts(bar - 2), confirmation_bar=bar,
        confirmation_time=_ts(bar), tradable_bar=bar, tradable_time=_ts(bar),
        mitigation_level=zone_low, meta={"pattern": "3C_FVG", "side": "bullish"},
    )


def _ob_bull(bar: int, zone_low: float, zone_high: float, origin_tf: str = "H4") -> MarketObject:
    return MarketObject(
        id=f"OB_{origin_tf}_{bar}_BULL", symbol="EURUSD", type=ObjectType.ORDER_BLOCK,
        origin_tf=origin_tf, role=Role.REFINEMENT, direction=1, zone_high=zone_high,
        zone_low=zone_low, creation_time=_ts(bar), state=ObjectState.ACTIVE, bar_index=bar,
        bar_time=_ts(bar), candidate_bar=bar - 1, candidate_time=_ts(bar - 1),
        confirmation_bar=bar, confirmation_time=_ts(bar), tradable_bar=bar,
        tradable_time=_ts(bar), meta={"pattern": "OB_FOOTPRINT_FOLLOWTHROUGH"},
    )


def _bar(idx: int, o: float, h: float, l: float, c: float) -> dict:
    return {"__index__": idx, "time": _ts(idx), "open": o, "high": h, "low": l, "close": c}


# --- Gate 1: PIT / zero-lookahead -----------------------------------------
def test_pit_full_vs_prefix_identical_to_t():
    bars = [
        _bar(10, 1.1000, 1.1005, 1.0995, 1.1002),  # tradable
        _bar(11, 1.1002, 1.1010, 1.1000, 1.1008),  # penetra (partial)
        _bar(12, 1.1008, 1.1012, 1.0990, 1.0995),  # cruza far_side (low<=1.0995) pero cierra 1.0995 == far => MITIGATED
        _bar(13, 1.0995, 1.0998, 1.0990, 1.0988),  # cierra más allá => INVALIDATED
    ]
    # FULL: procesa todas las velas.
    obj_full = _fvg_bull(10, 1.0995, 1.1005)
    for b in bars[1:]:
        evaluate(obj_full, b, authority_tf="M15")
    # PREFIX(t=12): solo hasta la vela 12.
    obj_pre = _fvg_bull(10, 1.0995, 1.1005)
    for b in bars[1:3]:
        evaluate(obj_pre, b, authority_tf="M15")
    assert obj_pre.state == ObjectState.MITIGATED
    # Procesar la vela 13 sobre obj_pre (estado en t=12) debe dar INVALIDATED,
    # idéntico a obj_full tras la misma vela.
    dec = evaluate(obj_pre, bars[3], authority_tf="M15")
    assert obj_pre.state == obj_full.state == ObjectState.INVALIDATED
    assert dec.reason == "INVALIDATED_FAR_SIDE_CLOSE"


# --- Gate 2: simetría bullish/bearish -------------------------------------
def test_symmetry_bull_bear_same_geometry():
    bull = _fvg_bull(10, 1.0995, 1.1005)
    bear = MarketObject(
        id="FVG_M15_10_BEAR", symbol="EURUSD", type=ObjectType.FVG, origin_tf="M15",
        role=Role.REFINEMENT, direction=-1, zone_high=1.1005, zone_low=1.0995,
        creation_time=_ts(10), state=ObjectState.ACTIVE, bar_index=10, bar_time=_ts(10),
        candidate_bar=8, candidate_time=_ts(8), confirmation_bar=10, confirmation_time=_ts(10),
        tradable_bar=10, tradable_time=_ts(10), meta={"pattern": "3C_FVG", "side": "bearish"},
    )
    # Bull: vela que cierra DEBAJO del far_side (1.0995) => INVALIDATED.
    evaluate(bull, _bar(11, 1.0996, 1.0998, 1.0990, 1.0990), authority_tf="M15")
    # Bear: vela que cierra ENCIMA del far_side (1.1005) => INVALIDATED.
    evaluate(bear, _bar(11, 1.1004, 1.1008, 1.1002, 1.1008), authority_tf="M15")
    assert bull.state == bear.state == ObjectState.INVALIDATED


# --- Gate 3: autoridad MTF (M15 no invalida OB H4) ------------------------
def test_lower_tf_cannot_invalidate_higher_tf_object():
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    # Una vela M15 que cierra por debajo del far_side del OB H4.
    m15_bar = _bar(11, 1.0996, 1.0998, 1.0990, 1.0990)
    # observe_lower_tf solo observa (no transiciona, no toca metadatos oficiales).
    dec = observe_lower_tf(ob_h4, m15_bar, observed_tf="M15")
    assert dec.changed is False
    assert ob_h4.state == ObjectState.ACTIVE
    # La observación vive separada en observations["M15"], no en metadatos oficiales.
    assert ob_h4.meta.get("observations", {}).get("M15") is not None
    assert ob_h4.first_touch_bar is None  # H4 oficial intacto
    # Incluso un evaluate() con authority_tf=M15 debe ser RECHAZADO por el motor.
    with pytest.raises(ValueError):
        evaluate(ob_h4, m15_bar, authority_tf="M15")
    # Vela H4 que sí cierra allá => autoridad decide.
    h4_bar = _bar(12, 1.0996, 1.0998, 1.0990, 1.0990)
    dec2 = evaluate(ob_h4, h4_bar, authority_tf="H4")
    assert ob_h4.state == ObjectState.INVALIDATED
    assert dec2.reason == "INVALIDATED_FAR_SIDE_CLOSE"


# --- Gate 4: terminalidad ------------------------------------------------
def test_terminal_state_does_not_resurrect():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    evaluate(obj, _bar(11, 1.0996, 1.0998, 1.0990, 1.0990), authority_tf="M15")  # INVALIDATED
    assert obj.is_terminal
    dec = evaluate(obj, _bar(12, 1.1000, 1.1010, 1.0999, 1.1008), authority_tf="M15")
    assert dec.changed is False
    assert obj.state == ObjectState.INVALIDATED


# --- Gate 5: idempotencia ------------------------------------------------
def test_idempotent_same_bar():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    b = _bar(11, 1.1002, 1.1010, 1.1000, 1.1008)  # partial
    d1 = evaluate(obj, b, authority_tf="M15")
    d2 = evaluate(obj, b, authority_tf="M15")
    assert obj.state == ObjectState.PARTIALLY_MITIGATED
    assert d1.changed and not d2.changed
    assert d1.source_bar == d2.source_bar


# --- Gate 6: timestamp exacto --------------------------------------------
def test_exact_timestamps():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    evaluate(obj, _bar(11, 1.1002, 1.1010, 1.1000, 1.1008), authority_tf="M15")  # touch
    evaluate(obj, _bar(13, 1.0996, 1.0998, 1.0990, 1.0990), authority_tf="M15")  # invalid
    assert obj.first_touch_bar == 11
    assert obj.invalidated_bar == 13
    assert obj.first_touch_time == _ts(11)
    assert obj.invalidated_time == _ts(13)


# --- Gate 7: precedencia INVALIDATED > MITIGATED --------------------------
def test_precedence_invalidated_over_mitigated():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    # Misma vela: low cruza far_side (1.0995) Y close queda debajo => INVALIDATED.
    dec = evaluate(obj, _bar(11, 1.0996, 1.0998, 1.0990, 1.0990), authority_tf="M15")
    assert obj.state == ObjectState.INVALIDATED
    assert dec.reason == "INVALIDATED_FAR_SIDE_CLOSE"


# --- Gate 8 + PIT tradable_time: replay pequeño real ----------------------
def test_small_replay_sequence_and_pit_tradable():
    # FVG nace en bar 10. Antes de tradable_time (bar 9) no debe transicionar.
    obj = _fvg_bull(10, 1.0995, 1.1005)
    pre = evaluate(obj, _bar(9, 1.0996, 1.1008, 1.0994, 1.1000), authority_tf="M15")
    assert pre.changed is False and obj.state == ObjectState.ACTIVE

    seq = []
    bars = [
        _bar(11, 1.1002, 1.1010, 1.1000, 1.1008),  # partial
        _bar(13, 1.0996, 1.0998, 1.0990, 1.0990),  # invalidated
    ]
    for b in bars:
        d = evaluate(obj, b, authority_tf="M15")
        seq.append((d.source_bar, d.previous_state, d.new_state, d.reason))
    assert seq == [
        (11, "ACTIVE", "PARTIALLY_MITIGATED", "PARTIAL_PENETRATION"),
        (13, "PARTIALLY_MITIGATED", "INVALIDATED", "INVALIDATED_FAR_SIDE_CLOSE"),
    ]
    assert obj.state == ObjectState.INVALIDATED


def test_partial_not_terminal_and_ce_touched_is_evidence():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    # Vela que penetra solo hasta el 50% (low llega a 1.1000, mitad = 1.1000).
    evaluate(obj, _bar(11, 1.1003, 1.1006, 1.1000, 1.1004), authority_tf="M15")
    assert obj.state == ObjectState.PARTIALLY_MITIGATED
    assert obj.meta.get("CE_TOUCHED") is True
    assert not obj.is_terminal


# === Correcciones de la auditoría NEEDS REVISION (Codex 2026-08-28) =========

def test_constructor_rejects_authority_tf_not_equal_origin():
    with pytest.raises(ValueError):
        MarketObject(
            id="OB_H4_45", symbol="EURUSD", type=ObjectType.ORDER_BLOCK, origin_tf="H4",
            authority_tf="M15", role=Role.POI, direction=1, zone_high=1.1005, zone_low=1.0995,
            creation_time=_ts(10), state=ObjectState.ACTIVE, bar_index=10, bar_time=_ts(10),
            candidate_bar=9, candidate_time=_ts(9), confirmation_bar=10, confirmation_time=_ts(10),
            tradable_bar=10, tradable_time=_ts(10),
        )


def test_evaluate_rejects_lower_tf_authority():
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    assert ob_h4.authority_tf == "H4"
    m15_bar = _bar(11, 1.0996, 1.0998, 1.0990, 1.0990)
    with pytest.raises(ValueError):
        evaluate(ob_h4, m15_bar, authority_tf="M15")
    assert ob_h4.state == ObjectState.ACTIVE
    assert ob_h4.first_touch_bar is None


def test_observe_lower_tf_does_not_alter_official_decision():
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    observe_lower_tf(ob_h4, _bar(11, 1.0996, 1.0998, 1.0990, 1.0994), observed_tf="M15")
    observe_lower_tf(ob_h4, _bar(12, 1.0997, 1.0999, 1.0991, 1.0995), observed_tf="M15")
    assert ob_h4.state == ObjectState.ACTIVE
    assert ob_h4.first_touch_bar is None
    assert ob_h4.touch_count == 0
    obs = ob_h4.meta.get("observations", {}).get("M15", [])
    assert len(obs) == 2
    assert all("penetration" in o for o in obs)


def test_double_evaluation_idempotent_no_side_effects():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    b = _bar(11, 1.1002, 1.1010, 1.1000, 1.1008)
    d1 = evaluate(obj, b, authority_tf="M15")
    d2 = evaluate(obj, b, authority_tf="M15")
    assert obj.state == ObjectState.PARTIALLY_MITIGATED
    assert d1.changed and not d2.changed
    assert obj.touch_count == 1
    assert len(obj.meta.get("_seen_events", set())) == 1


def test_different_tf_bar_indices_not_cross_compared():
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    m15_bar = _bar(440, 1.0996, 1.0998, 1.0990, 1.0994)
    observe_lower_tf(ob_h4, m15_bar, observed_tf="M15")
    assert ob_h4.first_touch_bar is None
    assert ob_h4.meta["observations"]["M15"][0]["bar"] == 440


def test_observe_then_evaluate_authority_separate_tracking():
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    observe_lower_tf(ob_h4, _bar(11, 1.0996, 1.0998, 1.0990, 1.0994), observed_tf="M15")
    h4_bar = _bar(12, 1.0996, 1.0998, 1.0990, 1.0990)
    dec = evaluate(ob_h4, h4_bar, authority_tf="H4")
    assert ob_h4.state == ObjectState.INVALIDATED
    assert dec.reason == "INVALIDATED_FAR_SIDE_CLOSE"
    assert ob_h4.first_touch_bar == 12
