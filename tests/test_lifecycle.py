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


def _bar(idx: int, o: float, h: float, l: float, c: float, tf: str = "M15") -> dict:
    return {"__index__": idx, "time": _ts(idx), "tf": tf, "open": o, "high": h, "low": l, "close": c}


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
    h4_bar = _bar(12, 1.0996, 1.0998, 1.0990, 1.0990, tf="H4")
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
    h4_bar = _bar(12, 1.0996, 1.0998, 1.0990, 1.0990, tf="H4")
    dec = evaluate(ob_h4, h4_bar, authority_tf="H4")
    assert ob_h4.state == ObjectState.INVALIDATED
    assert dec.reason == "INVALIDATED_FAR_SIDE_CLOSE"
    assert ob_h4.first_touch_bar == 12


# === Garantías de CERTIFICACIÓN (RUN CONTINUO + anti-falsificación TF) =====

def test_evaluate_rejects_bar_from_wrong_tf_m15_disguised_as_h4():
    # Auditoría continuación, garantía 1: "M15 disfrazado de H4".
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    assert ob_h4.authority_tf == "H4"
    m15_bar = _bar(12, 1.0996, 1.0998, 1.0990, 1.0990, tf="M15")
    with pytest.raises(ValueError):
        evaluate(ob_h4, m15_bar, authority_tf="H4")
    assert ob_h4.state == ObjectState.ACTIVE


def test_evaluate_requires_identity_fail_closed():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    bad = {"__index__": -1, "time": None, "tf": "M15", "open": 1.1002, "high": 1.1008,
           "low": 1.1000, "close": 1.1006}
    with pytest.raises(ValueError):
        evaluate(obj, bad, authority_tf="M15")
    assert obj.state == ObjectState.ACTIVE


def test_observe_requires_identity_fail_closed():
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    bad = {"__index__": -1, "time": None, "tf": "M15", "open": 1.0996, "high": 1.0998,
           "low": 1.0990, "close": 1.0994}
    with pytest.raises(ValueError):
        observe_lower_tf(ob_h4, bad, observed_tf="M15")
    assert "M15" not in ob_h4.meta.get("observations", {})


def test_distinct_bars_with_null_time_not_collapsed():
    obj = _fvg_bull(10, 1.0995, 1.1005)
    b1 = {"__index__": 11, "time": None, "tf": "M15", "open": 1, "high": 1, "low": 1, "close": 1}
    b2 = {"__index__": 12, "time": None, "tf": "M15", "open": 1, "high": 1, "low": 1, "close": 1}
    for b in (b1, b2):
        with pytest.raises(ValueError):
            evaluate(obj, b, authority_tf="M15")


def test_round_trip_json_preserves_full_identity_and_lifecycle():
    import json
    obj = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    obj.observation_tf = "M15"
    obj.execution_tf = "M5"
    observe_lower_tf(obj, _bar(11, 1.0996, 1.0998, 1.0990, 1.0994, tf="M15"), observed_tf="M15")
    observe_lower_tf(obj, _bar(12, 1.0997, 1.0999, 1.0991, 1.0995, tf="M15"), observed_tf="M15")
    evaluate(obj, _bar(13, 1.1000, 1.1002, 1.0996, 1.0999, tf="H4"), authority_tf="H4")
    evaluate(obj, _bar(14, 1.1000, 1.1002, 1.0990, 1.0988, tf="H4"), authority_tf="H4")

    blob = json.dumps(obj.to_dict())
    obj2 = MarketObject.from_dict(json.loads(blob))
    assert obj2.authority_tf == "H4"
    assert obj2.lifecycle_tf == "H4"
    assert obj2.observation_tf == "M15"
    assert obj2.execution_tf == "M5"
    assert obj2.state == ObjectState.INVALIDATED
    assert obj2.first_touch_bar == 13
    assert obj2.touch_count == 2
    assert obj2.meta.get("CE_TOUCHED") is True
    assert len(obj2.meta["observations"]["M15"]) == 2
    assert isinstance(obj2.meta.get("_seen_events"), set)
    dec = evaluate(obj2, _bar(14, 1.1000, 1.1002, 1.0990, 1.0988, tf="H4"), authority_tf="H4")
    assert not dec.changed
    assert obj2.touch_count == 2


def test_full_vs_save_restore_continue_identical():
    import json
    bars_full = [
        _bar(10, 1.1000, 1.1005, 1.0995, 1.1002, tf="M15"),
        _bar(11, 1.1002, 1.1010, 1.1000, 1.1008, tf="M15"),
        _bar(12, 1.1008, 1.1012, 1.0990, 1.0995, tf="M15"),
        _bar(13, 1.0995, 1.0998, 1.0990, 1.0988, tf="M15"),
    ]
    obj_full = _fvg_bull(10, 1.0995, 1.1005)
    for b in bars_full[1:]:
        evaluate(obj_full, b, authority_tf="M15")

    obj_split = _fvg_bull(10, 1.0995, 1.1005)
    for b in bars_full[1:3]:
        evaluate(obj_split, b, authority_tf="M15")
    obj_cont = MarketObject.from_dict(json.loads(json.dumps(obj_split.to_dict())))
    evaluate(obj_cont, bars_full[3], authority_tf="M15")

    assert obj_cont.state == obj_full.state == ObjectState.INVALIDATED
    assert obj_cont.touch_count == obj_full.touch_count
    assert obj_cont.first_touch_bar == obj_full.first_touch_bar
    assert obj_cont.invalidated_bar == obj_full.invalidated_bar


# === Corrección temporal LTF/HTF (Codex H4) — frontera PIT por timestamp =====

def test_evaluate_requires_tf_present_fail_closed():
    # Falta tf en la barra => ValueError (no se asume M15 por defecto).
    obj = _fvg_bull(10, 1.0995, 1.1005)
    bad = {"__index__": 11, "time": _ts(11), "open": 1.1002, "high": 1.1010,
           "low": 1.1000, "close": 1.1008}  # sin clave "tf"
    with pytest.raises(ValueError):
        evaluate(obj, bad, authority_tf="M15")
    assert obj.state == ObjectState.ACTIVE
    assert obj.first_touch_bar is None


def test_observe_lower_tf_rejects_wrong_tf_h4_disguised_as_m15():
    # H4 disfrazado de M15 en observe_lower_tf => ValueError.
    # Un objeto H4 no puede registrarse como observación M15.
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    h4_bar = _bar(11, 1.0996, 1.0998, 1.0990, 1.0994, tf="H4")
    with pytest.raises(ValueError):
        observe_lower_tf(ob_h4, h4_bar, observed_tf="M15")
    assert "M15" not in ob_h4.meta.get("observations", {})
    assert ob_h4.state == ObjectState.ACTIVE


def test_observe_rejects_missing_tf_fail_closed():
    # Falta tf en la barra observada => ValueError.
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    bad = {"__index__": 11, "time": _ts(11), "open": 1.0996, "high": 1.0998,
           "low": 1.0990, "close": 1.0994}  # sin clave "tf"
    with pytest.raises(ValueError):
        observe_lower_tf(ob_h4, bad, observed_tf="M15")
    assert "M15" not in ob_h4.meta.get("observations", {})


def test_m15_later_by_timestamp_smaller_index_not_before_tradable():
    # M15 posterior por timestamp PERO con índice menor que el objeto H4
    # (índice H4 = 10) debe observarse correctamente (NO BEFORE_TRADABLE).
    # Esto cierra el defecto cross-TF: la frontera PIT se decide por timestamp.
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")  # tradable_bar=10, tradable_time=_ts(10)
    m15_bar = {"__index__": 5, "time": _ts(20), "tf": "M15",
               "open": 1.0996, "high": 1.0998, "low": 1.0990, "close": 1.0994}
    dec = observe_lower_tf(ob_h4, m15_bar, observed_tf="M15")
    assert dec.reason != "BEFORE_TRADABLE"
    assert dec.changed is False  # observación no muta estado oficial
    obs = ob_h4.meta["observations"]["M15"]
    assert len(obs) == 1
    assert obs[0]["bar"] == 5  # índice M15 preservado, no descartado


def test_double_observation_same_bar_idempotent():
    # Doble observación de la misma vela => sin duplicación.
    ob_h4 = _ob_bull(10, 1.0995, 1.1005, origin_tf="H4")
    b = _bar(11, 1.0996, 1.0998, 1.0990, 1.0994, tf="M15")
    d1 = observe_lower_tf(ob_h4, b, observed_tf="M15")
    d2 = observe_lower_tf(ob_h4, b, observed_tf="M15")
    assert d1.changed is False and d2.changed is False
    assert len(ob_h4.meta["observations"]["M15"]) == 1
    assert len(ob_h4.meta.get("_seen_events", set())) >= 1
