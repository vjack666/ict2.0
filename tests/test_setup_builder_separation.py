"""Tests de la SEPARACION object_state vs setup_eligibility (SDD §13.3).

Verifican que ``engine.setup_builder.build_setup`` compone un Setup SIN mutar
``object_state`` de ningun MarketObject referenciado y que ``SetupEligibility``
es una propiedad del Setup, independiente del ``object_state`` de los objetos.

Invariantes verificados:
(a) componer un setup NO cambia el state de POI / context / refinement.
(b) ``SetupEligibility`` es independiente de ``ObjectState``: se calcula como
    snapshot en build_setup y NO se escribe en ningun MarketObject (ni en
    POI.meta como ``used_by_setup``).

NO importa backtest/. NO toca lifecycle.py ni market_state.py.
"""

from __future__ import annotations

import pytest

from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from engine.setup_builder import (
    Setup,
    SetupEligibility,
    build_setup,
    REASON_POI_INVALIDATED,
    REASON_HTF_CONTEXT_CHANGED,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_mo(role: Role, origin_tf: str = "H4", mo_type: ObjectType = ObjectType.FVG,
             **kw) -> MarketObject:
    return MarketObject(
        symbol="EURUSD",
        type=mo_type,
        origin_tf=origin_tf,
        role=role,
        direction=1,
        zone_high=1.1000,
        zone_low=1.0950,
        **kw,
    )


# --------------------------------------------------------------------------- #
# (a) componer setup NO cambia object_state de POI / context / refinement
# --------------------------------------------------------------------------- #
def test_build_setup_preserves_poi_state():
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.ACTIVE
    before = poi.state

    s = build_setup(symbol="EURUSD", direction=1, poi=poi)

    assert poi.state is before is ObjectState.ACTIVE
    # el Setup NO escribio usado_by_setup en el meta del POI
    assert "used_by_setup" not in poi.meta


def test_build_setup_preserves_context_and_refinement_state():
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1", mo_type=ObjectType.BOS)
    ctx.state = ObjectState.ACTIVE
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.ACTIVE
    ref = _make_mo(Role.REFINEMENT, origin_tf="H1")
    ref.state = ObjectState.ACTIVE

    before = (ctx.state, poi.state, ref.state)
    s = build_setup(symbol="EURUSD", direction=1, context_htf=ctx, poi=poi, refinement=ref)
    after = (ctx.state, poi.state, ref.state)

    assert after == before
    assert "used_by_setup" not in ctx.meta
    assert "used_by_setup" not in poi.meta
    assert "used_by_setup" not in ref.meta


def test_build_setup_does_not_mutate_poi_even_when_terminal():
    # Si el POI ya esta INVALIDATED, build_setup debe DEJARLO asi (no "revivirlo").
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.INVALIDATED

    s = build_setup(symbol="EURUSD", direction=1, poi=poi)

    assert poi.state is ObjectState.INVALIDATED
    assert s.eligibility is SetupEligibility.BLOCKED
    assert s.reason == REASON_POI_INVALIDATED


def test_build_setup_does_not_call_transition_to_or_reassign_state():
    # Caso exhaustivo: multiples objetos en distintos estados; build_setup no
    # debe alterar NINGUNO (ni POI, ni context, ni refinement, ni confirmation).
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1", mo_type=ObjectType.BOS)
    ctx.state = ObjectState.ACTIVE
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.PARTIALLY_MITIGATED
    ref = _make_mo(Role.REFINEMENT, origin_tf="H1")
    ref.state = ObjectState.ACTIVE
    conf = _make_mo(Role.REFINEMENT, origin_tf="M15", mo_type=ObjectType.CHOCH)
    conf.state = ObjectState.CREATED

    snapshot = {id(o): o.state for o in (ctx, poi, ref, conf)}
    s = build_setup(symbol="EURUSD", direction=1, context_htf=ctx, poi=poi,
                    refinement=ref, confirmation=conf)

    for o in (ctx, poi, ref, conf):
        assert o.state is snapshot[id(o)], f"build_setup muto state de {o.id}"


# --------------------------------------------------------------------------- #
# (b) SetupEligibility es INDEPENDIENTE de ObjectState
# --------------------------------------------------------------------------- #
def test_eligibility_blocked_when_htf_context_changed_even_if_objects_active():
    # Todos los objetos ACTIVE, pero la senal HTF dice contexto cambiado.
    # El setup queda BLOCKED => la elegibilidad NO es un espejo de object_state.
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1", mo_type=ObjectType.BOS)
    ctx.state = ObjectState.ACTIVE
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.ACTIVE
    ref = _make_mo(Role.REFINEMENT, origin_tf="H1")
    ref.state = ObjectState.ACTIVE

    s = build_setup(symbol="EURUSD", direction=1, context_htf=ctx, poi=poi,
                    refinement=ref, htf_context_valid=False)

    # objetos siguen ACTIVE...
    assert poi.state is ObjectState.ACTIVE
    assert ctx.state is ObjectState.ACTIVE
    # ...pero el Setup es BLOCKED por razon de contexto HTF.
    assert s.eligibility is SetupEligibility.BLOCKED
    assert s.reason == REASON_HTF_CONTEXT_CHANGED


def test_eligibility_is_snapshot_not_live_linked_to_object_state():
    # build_setup congela la elegibilidad en el instante de la composicion.
    # Mutar el POI DESPUES no debe cambiar s.eligibility (prueba de independencia).
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.ACTIVE

    s = build_setup(symbol="EURUSD", direction=1, poi=poi)
    assert s.eligibility is SetupEligibility.ELIGIBLE

    # ahora el POI "muere" (en el mundo real, otra capa lo transitiona)
    poi.state = ObjectState.INVALIDATED
    # la elegibilidad del setup ya compuesto NO cambia: es propiedad del Setup.
    assert s.eligibility is SetupEligibility.ELIGIBLE
    assert s.reason == ""


def test_eligibility_lives_on_setup_not_on_market_object():
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1", mo_type=ObjectType.BOS)
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.ACTIVE

    s = build_setup(symbol="EURUSD", direction=1, context_htf=ctx, poi=poi,
                    htf_context_valid=False)

    # el MarketObject NO tiene (ni debe tener) atributo de elegibilidad.
    assert not hasattr(poi, "eligibility")
    assert not hasattr(ctx, "eligibility")
    # la elegibilidad vive exclusivamente en el Setup.
    assert s.eligibility is SetupEligibility.BLOCKED
    assert isinstance(s.eligibility, SetupEligibility)


def test_build_setup_default_eligible_when_all_active_and_context_valid():
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.ACTIVE
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1", mo_type=ObjectType.BOS)
    ctx.state = ObjectState.ACTIVE

    s = build_setup(symbol="EURUSD", direction=-1, context_htf=ctx, poi=poi)
    assert s.eligibility is SetupEligibility.ELIGIBLE
    assert s.reason == ""
    assert poi.state is ObjectState.ACTIVE
    assert ctx.state is ObjectState.ACTIVE


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
