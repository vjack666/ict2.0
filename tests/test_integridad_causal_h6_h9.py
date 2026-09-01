"""Fase de TESIS H6-H9 — Integridad causal de MarketState / Lifecycle / Setup Builder.

Objetivo (OE-09): cada regla del contrato tiene al menos una prueba adversarial
que intenta ROMPERLA. Donde la regla ya estaba cerrada en código previo
(H6/H8/H9), el test DEMUESTRA que el caso adversarial queda bloqueado. Donde
había hueco real (H7, OE-07), el test lo cierra y lo convierte en regresión.

Gates binarios: PASS / FAIL. No se aprueba por conteo de tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from engine.lifecycle import evaluate, observe_lower_tf
from engine.market_object import MarketObject, ObjectState, ObjectType
from engine.market_state import MarketState
from engine.relations import relate_fvg_ob
from engine.setup_builder import build_setups_at, classify_eligibility, Setup


UTC = timezone.utc


def _ob(origin_tf="H4", anchor=10, confirm=11, tradable=11, direction=1, state=ObjectState.ACTIVE):
    return MarketObject(
        id=f"OB_{origin_tf}_{anchor}",
        type=ObjectType.ORDER_BLOCK,
        state=state,
        direction=direction,
        origin_tf=origin_tf,
        authority_tf=origin_tf,
        bar_index=anchor,
        candidate_bar=anchor,
        confirmation_bar=confirm,
        tradable_bar=tradable,
        creation_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=anchor),
        candidate_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=anchor),
        confirmation_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=confirm),
        zone_high=1.1050,
        zone_low=1.1000,
    )


def _fvg(origin_tf="M15", anchor=20, confirm=21, direction=1, state=ObjectState.ACTIVE):
    return MarketObject(
        id=f"FVG_{origin_tf}_{anchor}",
        type=ObjectType.FVG,
        state=state,
        direction=direction,
        origin_tf=origin_tf,
        authority_tf=origin_tf,
        bar_index=anchor,
        candidate_bar=anchor,
        confirmation_bar=confirm,
        tradable_bar=confirm,
        creation_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=anchor),
        candidate_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=anchor),
        confirmation_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=confirm),
        zone_high=1.1040,
        zone_low=1.1010,
    )


def _bos(origin_tf="M15", bar=5, direction=1):
    return MarketObject(
        id=f"BOS_{origin_tf}_{bar}",
        type=ObjectType.BOS,
        state=ObjectState.ACTIVE,
        direction=direction,
        origin_tf=origin_tf,
        authority_tf=origin_tf,
        bar_index=bar,
        candidate_bar=bar,
        confirmation_bar=bar,
        tradable_bar=bar,
        creation_time=datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + timedelta(hours=bar),
        zone_high=1.1060,
        zone_low=1.1030,
    )


# ===================== OE-02 / H6 =====================
def test_H6_bos_anterior_al_poi_queda_rechazado():
    """OE-02: relación FVG↔OB rechaza OB que nace DESPUÉS del FVG en tiempo real.

    Caso adversarial cross-TF: FVG M15 confirmation en T+5h, OB H4 candidate en
    T+100h. El OB es posterior => la relación 'OB precede al FVG' es falsa.
    """
    ob = _ob(origin_tf="H4", anchor=101, confirm=102, tradable=102)
    fvg = _fvg(origin_tf="M15", anchor=5, confirm=6)
    rels = relate_fvg_ob([fvg], [ob], causal_mode="strict", max_bars_apart=9999)
    assert rels == [], "H6 roto: relacionó OB posterior al FVG (viaje al futuro)"


def test_H6_confirmation_anterior_al_poi_bloquea_setup():
    """OE-02: setup con confirmation (BOS) cuya confirmation_time es ANTERIOR al
    POI candidate_time => BLOCKED (orden causal violado, nunca pudo existir)."""
    ob = _ob(anchor=100, confirm=101, tradable=101)  # POI nace en T+100h
    fvg = _fvg(anchor=105, confirm=106)
    # BOS con confirmation_time ANTES que el POI (T+10h < T+100h)
    bos = _bos(bar=10)
    bos.confirmation_time = datetime(2026, 1, 1, 10, tzinfo=UTC)
    bos.candidate_time = datetime(2026, 1, 1, 10, tzinfo=UTC)
    setup = Setup(symbol="EURUSD", direction=1, context_htf=None, poi=ob, refinement=fvg, confirmation=bos, trigger=bos)
    elig = classify_eligibility(setup, _ctx(aligned=True, bias=1), require_complete=True)
    assert elig.value == "BLOCKED", f"H6 roto: setup con confirmation anterior al POI = {elig.value}"


def test_H6_trigger_anterior_al_refinement_bloqueado():
    """OE-02 (Tesis 1, ley congelada): trigger (DISPLACEMENT) debe ocurrir DESPUÉS
    de confirmation (BOS), que a su vez es >= refinement. Un trigger previo al
    refinement (y por tanto al confirmation) es causalmente imposible => BLOCKED."""
    base = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    ob = _ob(anchor=100, confirm=101, tradable=101)   # POI ~T+100h
    ob.candidate_time = base + timedelta(hours=100)
    ob.confirmation_time = base + timedelta(hours=101)
    fvg = _fvg(anchor=105, confirm=106)               # refinement ~T+105h
    fvg.candidate_time = base + timedelta(hours=105)
    fvg.confirmation_time = base + timedelta(hours=106)
    bos = _bos(bar=107)                               # confirmation T+107h
    bos.candidate_time = base + timedelta(hours=107)
    bos.confirmation_time = base + timedelta(hours=107)
    # trigger en T+10h: ANTES de POI/refinement/confirmation => imposible
    trig = _bos(bar=10)
    trig.candidate_time = base + timedelta(hours=10)
    trig.confirmation_time = base + timedelta(hours=10)
    setup = Setup(symbol="EURUSD", direction=1, context_htf=None, poi=ob, refinement=fvg, confirmation=bos, trigger=trig)
    elig = classify_eligibility(setup, _ctx(aligned=True, bias=1), require_complete=True)
    assert elig.value == "BLOCKED", f"H6 roto: trigger anterior a toda la cadena = {elig.value}"


def test_H6_confirmation_anterior_al_refinement_bloqueado():
    """OE-02 (Tesis 1): confirmation (BOS) debe ser >= refinement (FVG).
    confirmation previo al refinement es causalmente imposible => BLOCKED."""
    base = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    ob = _ob(anchor=100, confirm=101, tradable=101)
    ob.candidate_time = base + timedelta(hours=100)
    ob.confirmation_time = base + timedelta(hours=101)
    fvg = _fvg(anchor=105, confirm=106)               # refinement ~T+105h
    fvg.candidate_time = base + timedelta(hours=105)
    fvg.confirmation_time = base + timedelta(hours=106)
    # BOS en T+102h: entre POI(100) y refinement(105) -> confirmation < refinement
    bos = _bos(bar=102)
    bos.candidate_time = base + timedelta(hours=102)
    bos.confirmation_time = base + timedelta(hours=102)
    trig = _bos(bar=108)                              # trigger T+108h (posterior, ok)
    trig.candidate_time = base + timedelta(hours=108)
    trig.confirmation_time = base + timedelta(hours=108)
    setup = Setup(symbol="EURUSD", direction=1, context_htf=None, poi=ob, refinement=fvg, confirmation=bos, trigger=trig)
    elig = classify_eligibility(setup, _ctx(aligned=True, bias=1), require_complete=True)
    assert elig.value == "BLOCKED", f"H6 roto: confirmation anterior al refinement = {elig.value}"


def test_H6_trigger_anterior_al_confirmation_es_valido():
    """Enmienda H6 (preregistrada): BOS (confirmation) y displacement (trigger)
    son EVIDENCIAS HERMANAS del mismo POI. El displacement puede preceder al BOS
    (crea la estructura y deja el FVG); el setup es ELIGIBLE, no BLOCKED."""
    base = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    ob = _ob(anchor=100, confirm=101, tradable=101)
    ob.candidate_time = base + timedelta(hours=100)
    ob.confirmation_time = base + timedelta(hours=101)
    fvg = _fvg(anchor=105, confirm=106)
    fvg.candidate_time = base + timedelta(hours=105)
    fvg.confirmation_time = base + timedelta(hours=106)
    bos = _bos(bar=107)                               # confirmation T+107h
    bos.candidate_time = base + timedelta(hours=107)
    bos.confirmation_time = base + timedelta(hours=107)
    # trigger (displacement) en T+103h: ANTES del confirmation (BOS, T+107h)
    # pero DESPUÉS del refinement (FVG, T+105h). Evidencias hermanas => válido.
    trig = _bos(bar=103)
    trig.type = ObjectType.DISPLACEMENT
    trig.candidate_time = base + timedelta(hours=103)
    trig.confirmation_time = base + timedelta(hours=103)
    setup = Setup(symbol="EURUSD", direction=1, context_htf=None, poi=ob, refinement=fvg, confirmation=bos, trigger=trig)
    elig = classify_eligibility(setup, _ctx(aligned=True, bias=1), require_complete=True)
    assert elig.value == "ELIGIBLE", f"H6 enmienda rota: displacement previo al BOS debería ser ELIGIBLE = {elig.value}"


def test_H6_relacion_cross_tf_usa_tiempo_no_bar_index():
    """OE-07: OB H4 bar_index 10 pero tiempo T+1 no debe preceder FVG M15 tiempo T."""
    ob = _ob(origin_tf="H4", anchor=10, confirm=11)
    # FVG M15 con tiempo ANTERIOR al OB H4 (aunque su bar_index sea mayor)
    fvg = _fvg(origin_tf="M15", anchor=200, confirm=201)
    fvg.candidate_time = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)  # T0
    fvg.confirmation_time = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)  # T0+30m
    ob.candidate_time = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)  # T+1d (después)
    rels = relate_fvg_ob([fvg], [ob], causal_mode="strict", max_bars_apart=9999)
    assert rels == [], "OE-07 roto: comparó bar_index de relojes distintos"


# ===================== OE-03 / H7 =====================
def test_H7_vela_fuera_de_orden_rechazada_fail_closed():
    """OE-03: vela atrasada (index menor al visto) => ValueError OUT_OF_ORDER."""
    ob = _ob(anchor=10)
    ms = MarketState()
    ms.ingest(ob)
    bar1 = {"time": datetime(2026, 1, 1, 1, tzinfo=UTC), "__index__": 10, "tf": "H4", "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105}
    bar2_late = {"time": datetime(2026, 1, 1, 0, tzinfo=UTC), "__index__": 5, "tf": "H4", "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105}
    ms.advance_bar(ob.id, bar1)
    with pytest.raises(ValueError):
        ms.advance_bar(ob.id, bar2_late)
    assert len(ms.out_of_order_events()) == 1


def test_H7_mismo_tf_reloj_independiente_no_contamina_otro_tf():
    """OE-03: una M15 atrasada no invalida la historia H4 ya procesada."""
    ob_h4 = _ob(origin_tf="H4", anchor=10)
    ms = MarketState()
    ms.ingest(ob_h4)
    ms.advance_bar(ob_h4.id, {"time": datetime(2026, 1, 1, 4, tzinfo=UTC), "__index__": 10, "tf": "H4", "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105})
    # M15 atrasada llega después; no debe colapsar el reloj H4
    ms._update_last_seen("M15", datetime(2026, 1, 1, 0, tzinfo=UTC), 1)
    with pytest.raises(ValueError):
        ms.advance_bar(ob_h4.id, {"time": datetime(2026, 1, 1, 3, tzinfo=UTC), "__index__": 9, "tf": "H4", "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105})
    # y el reloj H4 sigue avanzable hacia adelante
    ms.advance_bar(ob_h4.id, {"time": datetime(2026, 1, 1, 5, tzinfo=UTC), "__index__": 11, "tf": "H4", "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105})


# ===================== OE-04 / H8 =====================
def test_H8_h4_no_puede_observar_h4():
    """OE-04: observe_lower_tf con observed_tf == origin_tf (H4) rechazado."""
    ob = _ob(origin_tf="H4")
    bar = {"time": datetime(2026, 1, 1, 1, tzinfo=UTC), "tf": "H4", "__index__": 10, "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105}
    with pytest.raises(ValueError):
        observe_lower_tf(ob, bar, observed_tf="H4")


def test_H8_d1_no_puede_observar_h4():
    """OE-04: una temporalidad SUPERIOR no observa una inferior (D1 -> H4)."""
    ob = _ob(origin_tf="H4")
    bar = {"time": datetime(2026, 1, 1, 1, tzinfo=UTC), "tf": "D1", "__index__": 1, "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105}
    with pytest.raises(ValueError):
        observe_lower_tf(ob, bar, observed_tf="D1")


def test_H8_m15_observa_correctamente_h4_sin_cambiar_estado():
    """OE-04: M15 puede observar H4 y NO muta el estado oficial."""
    ob = _ob(origin_tf="H4")
    ms = MarketState()
    ms.ingest(ob)
    bar_m15 = {"time": datetime(2026, 1, 1, 0, 30, tzinfo=UTC), "tf": "M15", "__index__": 2, "open": 1.1005, "high": 1.1010, "low": 1.0990, "close": 1.1005}
    ms.advance_bar(ob.id, bar_m15, observed_tf="M15")
    assert ob.state == ObjectState.ACTIVE, "H8 roto: observación LTF mutó estado oficial"


# ===================== OE-05 / H9 =====================
def _ctx(aligned=True, bias=1):
    return {"htf_bias": "bullish" if bias == 1 else "bearish", "aligned": aligned}


def test_H9_aligned_false_jamas_termina_eligible():
    """OE-05: aligned=False + bullish => NOT_ELIGIBLE (fail-closed)."""
    ob = _ob(anchor=10, state=ObjectState.ACTIVE)
    fvg = _fvg(anchor=20, state=ObjectState.ACTIVE)
    bos = _bos(bar=15)
    setup = Setup(symbol="EURUSD", direction=1, context_htf=None, poi=ob, refinement=fvg, confirmation=bos, trigger=bos)
    elig = classify_eligibility(setup, _ctx(aligned=False, bias=1), require_complete=True)
    assert elig.value != "ELIGIBLE", "H9 roto: aligned=False terminó ELIGIBLE"
    assert elig.value in ("BLOCKED", "OUT_OF_CONTEXT", "SUPERSEDED")


def test_H9_aligned_false_bearish_tambien_bloqueado():
    ob = _ob(direction=-1)
    fvg = _fvg(direction=-1)
    bos = _bos(bar=15, direction=-1)
    setup = Setup(symbol="EURUSD", direction=-1, context_htf=None, poi=ob, refinement=fvg, confirmation=bos, trigger=bos)
    elig = classify_eligibility(setup, _ctx(aligned=False, bias=-1), require_complete=True)
    assert elig.value != "ELIGIBLE"


def test_H9_ctx_incompleto_queda_out_of_context():
    ob = _ob()
    fvg = _fvg()
    bos = _bos(bar=15)
    setup = Setup(symbol="EURUSD", direction=1, context_htf=None, poi=ob, refinement=fvg, confirmation=bos, trigger=bos)
    elig = classify_eligibility(setup, None, require_complete=True)
    assert elig.value == "OUT_OF_CONTEXT"


# ===================== OE-06 Lifecycle terminal =====================
def test_OE06_objeto_terminal_no_resucita():
    ob = _ob(anchor=10, state=ObjectState.ACTIVE)
    ms = MarketState()
    ms.ingest(ob)
    # OB bullish zone 1.1000-1.1050; cierre MÁS ALLÁ del far_side (1.1000) => INVALIDATED
    invalidate_bar = {"time": datetime(2026, 1, 1, 2, tzinfo=UTC), "tf": "H4", "__index__": 12, "open": 1.101, "high": 1.102, "low": 1.099, "close": 1.099}
    ms.advance_bar(ob.id, invalidate_bar)
    assert ob.state == ObjectState.INVALIDATED
    # intentar revivirlo con vela posterior => sigue terminal, no resucita
    revive = {"time": datetime(2026, 1, 1, 3, tzinfo=UTC), "tf": "H4", "__index__": 13, "open": 1.101, "high": 1.102, "low": 1.100, "close": 1.101}
    ms.advance_bar(ob.id, revive)
    assert ob.state == ObjectState.INVALIDATED


# ===================== OE-08 FULL vs PREFIX =====================
def test_OE08_full_vs_prefix_identico_en_T():
    """OE-08: projection_at(T) idéntico usando universo completo o solo prefijo<=T."""
    ob = _ob(anchor=10)
    fvg = _fvg(anchor=20)
    ms = MarketState()
    ms.ingest(ob)
    ms.ingest(fvg)
    T = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    full = ms.projection_at(T)
    # prefijo: construimos otro MS solo con objetos nacidos <= T
    ms_prefix = MarketState()
    for o in (ob, fvg):
        if (o.creation_time is None) or (o.creation_time <= T):
            ms_prefix.ingest(o)
    prefix = ms_prefix.projection_at(T)
    assert set(full.keys()) == set(prefix.keys())


# ===================== OE-07 relación misma TF usa bar_index =====================
def test_OE07_misma_tf_orden_por_bar_index():
    ob = _ob(origin_tf="M15", anchor=10, confirm=11)
    fvg = _fvg(origin_tf="M15", anchor=20, confirm=21)
    rels = relate_fvg_ob([fvg], [ob], causal_mode="strict", max_bars_apart=50)
    assert len(rels) == 1, "OE-07 roto: misma TF debe ordenar por bar_index"


# ===================== OE-10 / RED TEAM: casos 14 y 18 =====================
def test_OE10_padre_htf_invalidado_hijo_ltf_sigue_existiendo():
    """Caso 14 adversarial: HTF invalidado no borra al hijo LTF (separacion de vidas)."""
    ob_h4 = _ob(origin_tf="H4", anchor=10)
    fvg_m15 = _fvg(origin_tf="M15", anchor=20)
    fvg_m15.parent_object = ob_h4.id
    ms = MarketState()
    ms.ingest(ob_h4)
    ms.ingest(fvg_m15)
    # invalidar el padre H4
    ms.advance_bar(ob_h4.id, {"time": datetime(2026, 1, 1, 2, tzinfo=UTC), "tf": "H4", "__index__": 12, "open": 1.101, "high": 1.102, "low": 1.099, "close": 1.099})
    assert ob_h4.state == ObjectState.INVALIDATED
    # el hijo LTF sigue existiendo en su propio estado (no lo mato por herencia)
    assert fvg_m15.state == ObjectState.ACTIVE


def test_OE10_determinismo_misma_ejecucion_idéntica():
    """Caso 18 adversarial: repetir la misma construcción da resultado idéntico."""
    ob = _ob(anchor=10)
    fvg = _fvg(anchor=20)
    bos = _bos(bar=15)
    ms = MarketState()
    ms.ingest(ob)
    ms.ingest(fvg)
    ms.ingest(bos)
    ctx = _ctx(aligned=True, bias=1)
    r1 = build_setups_at(ms, datetime(2026, 1, 5, tzinfo=UTC), ctx=ctx)
    r2 = build_setups_at(ms, datetime(2026, 1, 5, tzinfo=UTC), ctx=ctx)
    assert [s.eligibility.value for s in r1] == [s.eligibility.value for s in r2]
    assert len(r1) == len(r2)


# ===================== OE-05 / OE-11 — Equivalencia de persistencia H7 =====================
def test_OE11_save_load_conserva_reloj_out_of_order():
    """OE-05/OE-11 (Tesis 1): tras SAVE -> LOAD el MarketState debe conservar el
    reloj H7. Una vela fuera de orden rechazada por el ORIGINAL debe ser rechazada
    por el RESTAURADO (comportamiento equivalente, no solo to_dict igual)."""
    import json
    from engine.market_state import MarketState as _MS

    ob = _ob(anchor=10, confirm=10, tradable=10)
    ms = _MS()
    ms.ingest(ob)
    bar1 = {"time": datetime(2026, 1, 1, 1, tzinfo=UTC), "__index__": 10, "tf": "H4",
            "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105}
    bar_late = {"time": datetime(2026, 1, 1, 0, tzinfo=UTC), "__index__": 5, "tf": "H4",
                "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105}
    ms.advance_bar(ob.id, bar1)
    # original rechaza la vela atrasada
    with pytest.raises(ValueError):
        ms.advance_bar(ob.id, bar_late)
    assert len(ms.out_of_order_events()) == 1

    # SAVE -> LOAD
    restored = _MS.from_dict(json.loads(json.dumps(ms.to_dict())))
    # el restaurado debe conocer el último instante H4 visto (reloj conservado)
    assert restored.out_of_order_events(), "OE-11: el registro H7 no sobrevivió a SAVE/LOAD"
    # y debe volver a rechazar la misma vela atrasada
    with pytest.raises(ValueError):
        restored.advance_bar(ob.id, bar_late)
    assert len(restored.out_of_order_events()) == 2
