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
from engine.setup_builder import SetupEligibility, build_setups_at

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


def _state() -> MarketState:
    ms = MarketState()
    ms.ingest(_ob_h4())
    ms.ingest(_fvg_m15())
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
