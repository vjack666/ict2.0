"""Integración de build_setups_at (SDD §13.5) — Setup Builder.

Harness determinista: un MarketState sintético con un OB H4 ACTIVE y un
FVG M15 ACTIVE que lo refina (parent_object apuntando al OB). Valida:

  * 1 setup ELIGIBLE cuando el contexto HTF es bullish.
  * 1 setup BLOCKED cuando el contexto HTF NO es bullish.
  * 0 setups cuando el FVG no refina al OB (falta contención MTF).
  * 0 setups cuando el OB no está ACTIVE.
  * El compositor NO muta object_state ni POI.meta (contrato de solo lectura).
"""

from __future__ import annotations

from datetime import datetime, timezone

from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState
from engine.setup_builder import Setup, SetupEligibility, build_setups_at

UTC = timezone.utc


def _ts(minutes: int) -> datetime:
    return datetime(2026, 1, 1, 0, 0, tzinfo=UTC) + __import__("datetime").timedelta(minutes=minutes)


def _ob_h4() -> MarketObject:
    """OB H4 bullish, ACTIVE, candidato de POI."""
    return MarketObject(
        id="OB_H4_1", symbol="EURUSD", type=ObjectType.ORDER_BLOCK,
        origin_tf="H4", role=Role.POI, direction=1,
        zone_low=1.1000, zone_high=1.1050,
        creation_time=_ts(0), state=ObjectState.ACTIVE,
        bar_index=101, bar_time=_ts(101),
        candidate_bar=100, candidate_time=_ts(100),
        confirmation_bar=101, confirmation_time=_ts(101),
        tradable_bar=101, tradable_time=_ts(101),
    )


def _fvg_m15(refines: str | None = "OB_H4_1") -> MarketObject:
    """FVG M15 bullish, ACTIVE, que refina (por parent_object) al OB H4.

    Su zona [1.1020, 1.1040] se solapa con el OB H4 [1.1000, 1.1050] y cumple
    el orden causal estricto: ob_anchor(100) < fvg_confirm(115), lag 15.
    """
    return MarketObject(
        id="FVG_M15_1", symbol="EURUSD", type=ObjectType.FVG,
        origin_tf="M15", role=Role.REFINEMENT, direction=1,
        zone_low=1.1020, zone_high=1.1040,
        creation_time=_ts(10), state=ObjectState.ACTIVE,
        bar_index=115, bar_time=_ts(115),
        candidate_bar=110, candidate_time=_ts(110),
        confirmation_bar=115, confirmation_time=_ts(115),
        tradable_bar=115, tradable_time=_ts(115),
        parent_object=refines,
    )


def _ctx_d1() -> MarketObject:
    """Contexto HTF (D1 bullish) que se entrega vía ctx, no en el MarketState."""
    return MarketObject(
        id="CTX_D1_1", symbol="EURUSD", type=ObjectType.ORDER_BLOCK,
        origin_tf="D1", role=Role.CONTEXT, direction=1,
        zone_low=1.0900, zone_high=1.0950,
        creation_time=_ts(0), state=ObjectState.ACTIVE,
        bar_index=1, bar_time=_ts(1),
        candidate_bar=0, candidate_time=_ts(0),
        confirmation_bar=1, confirmation_time=_ts(1),
        tradable_bar=1, tradable_time=_ts(1),
    )


def _bos_h4(refines: str = "OB_H4_1") -> MarketObject:
    """BOS (ObjectType.BOS) bullish, ACTIVE, confirmation canónica del setup.

    Relacionado con el OB HTF vía ``related_objects`` (linaje inmutable de
    nacimiento) para que ``_find_confirmation`` lo recupere del snapshot.
    """
    return MarketObject(
        id="BOS_H4_1", symbol="EURUSD", type=ObjectType.BOS,
        origin_tf="H4", role=Role.CONFIRMATION, direction=1,
        zone_low=1.1050, zone_high=1.1100,
        creation_time=_ts(20), state=ObjectState.ACTIVE,
        bar_index=120, bar_time=_ts(120),
        candidate_bar=118, candidate_time=_ts(118),
        confirmation_bar=120, confirmation_time=_ts(120),
        tradable_bar=120, tradable_time=_ts(120),
        related_objects=[refines],
    )


def _disp_m15(refines: str = "FVG_M15_1", ob: str = "OB_H4_1") -> MarketObject:
    """DISPLACEMENT (ObjectType.DISPLACEMENT) bullish, trigger canónico del setup.

    Relacionado con el FVG LTF y el OB HTF.
    """
    return MarketObject(
        id="DISP_M15_1", symbol="EURUSD", type=ObjectType.DISPLACEMENT,
        origin_tf="M15", role=Role.TRIGGER, direction=1,
        zone_low=1.1040, zone_high=1.1080,
        creation_time=_ts(30), state=ObjectState.ACTIVE,
        bar_index=125, bar_time=_ts(125),
        related_objects=[refines, ob],
    )


def _state(direction: int = 1) -> MarketState:
    """MarketState sintético COMPLETO (contexto + POI + refinement + confirmation + trigger)."""
    ms = MarketState()
    ob = _ob_h4(); ob.direction = direction
    fvg = _fvg_m15(); fvg.direction = direction
    bos = _bos_h4(); bos.direction = direction
    disp = _disp_m15(); disp.direction = direction
    for o in (ob, fvg, bos, disp):
        ms.ingest(o)
    return ms


def _t() -> datetime:
    # Punto en T posterior a la creación de ambos objetos (snapshot causal).
    return _ts(1000)


# --- Casos principales (requeridos por el brief) ------------------------------

def test_eligible_when_htf_context_is_bullish():
    ms = _state()
    ctx = {"htf_bias": "bullish", "context_htf": _ctx_d1()}
    setups = build_setups_at(ms, _t(), ctx)

    assert len(setups) == 1
    s = setups[0]
    assert s.eligibility is SetupEligibility.ELIGIBLE
    assert s.poi is not None and s.poi.id == "OB_H4_1"
    assert s.refinement is not None and s.refinement.id == "FVG_M15_1"
    assert s.direction == 1
    assert s.context_htf is not None and s.context_htf.id == "CTX_D1_1"
    assert s.meta["relation"] == "FVG_OB_CAUSAL"
    assert s.meta["causal_order"] == "OB_BEFORE_FVG"
    assert s.meta["poi_tf"] == "H4"
    assert s.meta["refinement_tf"] == "M15"


def test_blocked_when_htf_context_not_bullish():
    ms = _state()
    ctx = {"htf_bias": "bearish", "context_htf": _ctx_d1()}
    setups = build_setups_at(ms, _t(), ctx)

    assert len(setups) == 1
    s = setups[0]
    # Mismos componentes, pero elegibilidad bloqueada por contexto HTF.
    assert s.poi is not None and s.poi.id == "OB_H4_1"
    assert s.refinement is not None and s.refinement.id == "FVG_M15_1"
    assert s.eligibility is SetupEligibility.BLOCKED
    assert "not bullish" in s.reason


def test_blocked_when_htf_bias_is_neutral():
    ms = _state()
    ctx = {"htf_bias": "neutral"}
    setups = build_setups_at(ms, _t(), ctx)

    assert len(setups) == 1
    assert setups[0].eligibility is SetupEligibility.BLOCKED


# --- Cobertura de la compuerta MTF y del filtro ACTIVE ------------------------

def test_no_setup_when_fvg_does_not_refine_ob():
    ms = MarketState()
    ms.ingest(_ob_h4())
    # FVG con parent_object=None -> no hay contención MTF con el OB H4.
    ms.ingest(_fvg_m15(refines=None))
    ctx = {"htf_bias": "bullish"}

    setups = build_setups_at(ms, _t(), ctx)
    # La relación geométrica existe, pero falla la compuerta ltf_contains/htf_refines.
    assert setups == []


def test_no_setup_when_ob_not_active():
    ob = _ob_h4()
    ob.state = ObjectState.MITIGATED  # no ACTIVE -> excluido del conjunto activo
    ms = MarketState()
    ms.ingest(ob)
    ms.ingest(_fvg_m15())
    ctx = {"htf_bias": "bullish"}

    setups = build_setups_at(ms, _t(), ctx)
    assert setups == []


# --- Invariante de solo lectura (auditoría) -----------------------------------

def test_composer_does_not_mutate_objects():
    ms = _state()
    ob = ms.all_objects()[0]
    fvg = ms.all_objects()[1]
    ob_state_before = ob.state
    fvg_state_before = fvg.state
    ob_meta_before = dict(ob.meta)

    ctx = {"htf_bias": "bullish", "context_htf": _ctx_d1()}
    build_setups_at(ms, _t(), ctx)

    # Ni object_state ni POI.meta deben cambiar (la linaje la fija el caller).
    assert ob.state == ob_state_before
    assert fvg.state == fvg_state_before
    assert ob.meta == ob_meta_before
    assert "used_by_setup" not in ob.meta


# --- Tests OBLIGATORIOS del brief (Codex H2+H3) ------------------------------ #


def test_complete_bullish_setup_is_eligible():
    """Setup COMPLETO (context+poi+refinement+confirmation+trigger) bajo ctx bullish."""
    ms = _state(direction=1)
    ctx = {"htf_bias": "bullish", "context_htf": _ctx_d1()}
    setups = build_setups_at(ms, _t(), ctx)

    assert len(setups) == 1
    s = setups[0]
    assert s.direction == 1
    assert s.context_htf is not None and s.context_htf.id == "CTX_D1_1"
    assert s.poi is not None and s.poi.id == "OB_H4_1"
    assert s.refinement is not None and s.refinement.id == "FVG_M15_1"
    assert s.confirmation is not None and s.confirmation.id == "BOS_H4_1"
    assert s.trigger is not None and s.trigger.id == "DISP_M15_1"
    assert s.eligibility is SetupEligibility.ELIGIBLE


def test_bearish_setup_blocked_under_bullish_context():
    """H3: setup bearish bajo sesgo bullish => BLOCKED (direction vs htf_bias)."""
    ms = _state(direction=-1)
    ctx = {"htf_bias": "bullish", "context_htf": _ctx_d1()}
    setups = build_setups_at(ms, _t(), ctx)

    assert len(setups) == 1
    s = setups[0]
    assert s.direction == -1
    assert s.eligibility is SetupEligibility.BLOCKED
    assert "not bullish" in s.reason


def test_context_changed_after_T_does_not_alter_prior_snapshot():
    """El ctx cambiado DESPUES de T no afecta el snapshot histórico en T (projection_at)."""
    ms = _state(direction=1)
    t = _ts(1000)
    s_bull = build_setups_at(ms, t, {"htf_bias": "bullish", "context_htf": _ctx_d1()})
    s_bear = build_setups_at(ms, t, {"htf_bias": "bearish", "context_htf": _ctx_d1()})

    # Mismo snapshot histórico en T para ambos (projection_at es determinista).
    assert s_bull[0].poi.id == s_bear[0].poi.id
    assert s_bull[0].eligibility is SetupEligibility.ELIGIBLE
    assert s_bear[0].eligibility is SetupEligibility.BLOCKED


def test_object_invalidated_after_T_available_in_prior_snapshot():
    """Objeto INVALIDATED despues de T sigue DISPONIBLE en snapshot previo (projection_at)."""
    ms = _state(direction=1)
    t_early = _ts(1000)
    t_late = _ts(3000)

    ob = ms.all_objects()[0]  # OB_H4_1
    ob.transition_to(ObjectState.INVALIDATED)
    ms._record_transition(
        ob.id, t_late, ob.bar_index, ob.authority_tf,
        ObjectState.ACTIVE, ObjectState.INVALIDATED,
    )

    proj_early = ms.projection_at(t_early)
    proj_late = ms.projection_at(t_late)
    assert proj_early["OB_H4_1"].state == ObjectState.ACTIVE
    assert proj_late["OB_H4_1"].state == ObjectState.INVALIDATED

    # build en t_early conserva el OB ACTIVE del snapshot previo => ELIGIBLE.
    setups = build_setups_at(ms, t_early, {"htf_bias": "bullish", "context_htf": _ctx_d1()})
    assert setups and setups[0].eligibility is SetupEligibility.ELIGIBLE


def test_setup_without_confirmation_is_blocked():
    """H2: setup sin confirmation (BOS) => BLOCKED bajo require_complete."""
    ms = MarketState()
    ob = _ob_h4(); ob.direction = 1
    fvg = _fvg_m15(); fvg.direction = 1
    disp = _disp_m15(); disp.direction = 1
    for o in (ob, fvg, disp):
        ms.ingest(o)  # SIN BOS -> falta confirmation
    ctx = {"htf_bias": "bullish", "context_htf": _ctx_d1()}
    setups = build_setups_at(ms, _t(), ctx)

    assert len(setups) == 1
    s = setups[0]
    assert s.confirmation is None
    assert s.eligibility is SetupEligibility.BLOCKED
    assert "confirmation" in s.reason


def test_setup_without_trigger_is_blocked():
    """H2: setup sin trigger (DISPLACEMENT) => BLOCKED bajo require_complete."""
    ms = MarketState()
    ob = _ob_h4(); ob.direction = 1
    fvg = _fvg_m15(); fvg.direction = 1
    bos = _bos_h4(); bos.direction = 1
    for o in (ob, fvg, bos):
        ms.ingest(o)  # SIN DISPLACEMENT -> falta trigger
    ctx = {"htf_bias": "bullish", "context_htf": _ctx_d1()}
    setups = build_setups_at(ms, _t(), ctx)

    assert len(setups) == 1
    s = setups[0]
    assert s.trigger is None
    assert s.eligibility is SetupEligibility.BLOCKED
    assert "trigger" in s.reason


def test_setup_full_roundtrip_save_restore():
    """FULL vs SAVE -> RESTORE -> CONTINUE idéntico (round-trip del Setup)."""
    ms = _state(direction=1)
    setups = build_setups_at(ms, _t(), {"htf_bias": "bullish", "context_htf": _ctx_d1()})
    s = setups[0]

    d = s.to_dict()
    s2 = Setup.from_dict(d)

    # Serialización estable: el dict redondeado es idéntico.
    assert s2.to_dict() == d
    assert s2.eligibility is s.eligibility
    assert s2.direction == s.direction
    assert s2.symbol == s.symbol
    assert s2.confirmation is not None and s2.confirmation.id == s.confirmation.id
    assert s2.trigger is not None and s2.trigger.id == s.trigger.id
    assert s2.context_htf is not None and s2.context_htf.id == s.context_htf.id
