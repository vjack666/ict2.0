"""Tests de clasificacion de elegibilidad (engine/setup_builder.py, SDD §13.4).

Cubre las 4 ramas de ``classify_eligibility``:
- ELIGIBLE        : contexto HTF alineado + POI/refinement ACTIVE
- BLOCKED         : contexto HTF NO alineado con direction
- OUT_OF_CONTEXT  : falta el contexto HTF (ctx is None)
- SUPERSEDED      : POI INVALIDATED

El clasificador es PURO respecto a los MarketObjects: NO muta object_state.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from engine.setup_builder import Setup, SetupEligibility, classify_eligibility


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _make_mo(role: Role, origin_tf: str = "H4", direction: int = 1,
             state: ObjectState = ObjectState.ACTIVE,
             mo_type: ObjectType = ObjectType.FVG, **kw) -> MarketObject:
    return MarketObject(
        symbol="EURUSD",
        type=mo_type,
        origin_tf=origin_tf,
        role=role,
        direction=direction,
        zone_high=1.1000,
        zone_low=1.0950,
        state=state,
        **kw,
    )


def _make_htf_ctx(direction: int, aligned: bool | None = True) -> object:
    """Contexto HTF duck-typed (estilo HtfBias) con direction/aligned."""
    return SimpleNamespace(direction=direction, aligned=aligned)


# --------------------------------------------------------------------------- #
# rama ELIGIBLE
# --------------------------------------------------------------------------- #
def test_eligible_when_htf_aligned_and_poi_refinement_active():
    poi = _make_mo(Role.POI, origin_tf="H4", direction=1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, origin_tf="H1", direction=1, state=ObjectState.ACTIVE)
    ctx = _make_htf_ctx(direction=1, aligned=True)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref, context_htf=poi)

    result = classify_eligibility(s, ctx)

    assert result is SetupEligibility.ELIGIBLE
    assert s.eligibility is SetupEligibility.ELIGIBLE
    assert "alineado" in s.reason.lower()


def test_eligible_accepts_marketobject_ctx():
    """ctx tambien puede ser un MarketObject (role CONTEXT) con direction."""
    poi = _make_mo(Role.POI, origin_tf="H4", direction=-1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, origin_tf="H1", direction=-1, state=ObjectState.ACTIVE)
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1", direction=-1, state=ObjectState.ACTIVE,
                   mo_type=ObjectType.BOS)
    s = Setup(symbol="EURUSD", direction=-1, poi=poi, refinement=ref, context_htf=ctx)

    result = classify_eligibility(s, ctx)

    assert result is SetupEligibility.ELIGIBLE


def test_eligible_accepts_dict_ctx():
    """ctx tambien puede ser un dict {'direction', 'aligned'}."""
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    result = classify_eligibility(s, {"direction": 1, "aligned": True})

    assert result is SetupEligibility.ELIGIBLE


# --------------------------------------------------------------------------- #
# rama BLOCKED (contexto no alineado)
# --------------------------------------------------------------------------- #
def test_blocked_when_htf_not_aligned():
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    ctx = _make_htf_ctx(direction=-1, aligned=True)  # sesgo opuesto
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    result = classify_eligibility(s, ctx)

    assert result is SetupEligibility.BLOCKED
    assert s.eligibility is SetupEligibility.BLOCKED
    assert "no alineado" in s.reason.lower()


def test_blocked_when_htf_neutral_zero_direction():
    """Contexto con direction=0 (neutral) no alinea con un setup direccional."""
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    ctx = _make_htf_ctx(direction=0, aligned=False)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    assert classify_eligibility(s, ctx) is SetupEligibility.BLOCKED


def test_blocked_when_aligned_but_poi_not_active():
    """Contexto alineado pero POI no ACTIVE -> no elegible -> BLOCKED."""
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.CREATED)  # no ACTIVE
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    ctx = _make_htf_ctx(direction=1, aligned=True)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    result = classify_eligibility(s, ctx)

    assert result is SetupEligibility.BLOCKED
    assert "POI/refinement no ACTIVE" in s.reason


def test_blocked_when_aligned_but_refinement_missing():
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.ACTIVE)
    ctx = _make_htf_ctx(direction=1, aligned=True)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=None)  # sin refinement

    assert classify_eligibility(s, ctx) is SetupEligibility.BLOCKED


# --------------------------------------------------------------------------- #
# rama OUT_OF_CONTEXT (falta contexto)
# --------------------------------------------------------------------------- #
def test_out_of_context_when_ctx_none():
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    result = classify_eligibility(s, None)

    assert result is SetupEligibility.OUT_OF_CONTEXT
    assert s.eligibility is SetupEligibility.OUT_OF_CONTEXT
    assert "ausente" in s.reason.lower()


def test_out_of_context_takes_precedence_over_non_aligned():
    """Sin ctx, el fallo de alineacion no se evalua: OUT_OF_CONTEXT domina."""
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    assert classify_eligibility(s, None) is SetupEligibility.OUT_OF_CONTEXT


# --------------------------------------------------------------------------- #
# rama SUPERSEDED (POI INVALIDATED)
# --------------------------------------------------------------------------- #
def test_superseded_when_poi_invalidated():
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.INVALIDATED)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    ctx = _make_htf_ctx(direction=1, aligned=True)  # incluso alineado
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    result = classify_eligibility(s, ctx)

    assert result is SetupEligibility.SUPERSEDED
    assert s.eligibility is SetupEligibility.SUPERSEDED
    assert "INVALIDATED" in s.reason


def test_superseded_dominates_out_of_context():
    """POI INVALIDATED gana incluso si no hay contexto."""
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.INVALIDATED)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    assert classify_eligibility(s, None) is SetupEligibility.SUPERSEDED


# --------------------------------------------------------------------------- #
# INVARIANTE: el clasificador NO muta object_state de los MarketObjects
# --------------------------------------------------------------------------- #
def test_classifier_does_not_mutate_market_objects():
    poi = _make_mo(Role.POI, direction=1, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    ctx = _make_htf_ctx(direction=1, aligned=True)
    s = Setup(symbol="EURUSD", direction=1, poi=poi, refinement=ref)

    classify_eligibility(s, ctx)

    # los objetos referenciados conservan su estado original
    assert poi.state is ObjectState.ACTIVE
    assert ref.state is ObjectState.ACTIVE
    # y el POI invalidado:
    poi2 = _make_mo(Role.POI, direction=1, state=ObjectState.INVALIDATED)
    ref2 = _make_mo(Role.REFINEMENT, direction=1, state=ObjectState.ACTIVE)
    s2 = Setup(symbol="EURUSD", direction=1, poi=poi2, refinement=ref2)
    classify_eligibility(s2, ctx)
    assert poi2.state is ObjectState.INVALIDATED


# --- Tests OBLIGATORIOS del brief (H2+H3) via classify_eligibility ---------- #
def _make_complete_setup(direction: int, *, with_confirmation: bool = True,
                         with_trigger: bool = True) -> Setup:
    """Setup COMPLETO con POI/refinement/confirmation/trigger de la misma direccion."""
    poi = _make_mo(Role.POI, origin_tf="H4", direction=direction, state=ObjectState.ACTIVE)
    ref = _make_mo(Role.REFINEMENT, origin_tf="H1", direction=direction, state=ObjectState.ACTIVE)
    conf = (
        _make_mo(Role.CONFIRMATION, origin_tf="H4", direction=direction,
                 state=ObjectState.ACTIVE, mo_type=ObjectType.BOS)
        if with_confirmation else None
    )
    trig = (
        _make_mo(Role.TRIGGER, origin_tf="M15", direction=direction,
                 state=ObjectState.ACTIVE, mo_type=ObjectType.DISPLACEMENT)
        if with_trigger else None
    )
    return Setup(symbol="EURUSD", direction=direction, poi=poi, refinement=ref,
                 confirmation=conf, trigger=trig)


def test_complete_setup_eligible_when_bias_aligned():
    """Setup completo (confirmation+trigger) bajo sesgo coincidente => ELIGIBLE."""
    s = _make_complete_setup(direction=1)
    result = classify_eligibility(s, {"htf_bias": "bullish"}, require_complete=True)
    assert result is SetupEligibility.ELIGIBLE
    assert s.eligibility is SetupEligibility.ELIGIBLE


def test_bearish_setup_blocked_under_bullish_bias():
    """H3: setup bearish bajo sesgo bullish => BLOCKED (direction vs htf_bias)."""
    s = _make_complete_setup(direction=-1)
    result = classify_eligibility(s, {"htf_bias": "bullish"}, require_complete=True)
    assert result is SetupEligibility.BLOCKED
    assert "not bullish" in s.reason


def test_setup_blocked_when_confirmation_missing():
    """H2: falta confirmation (BOS) => BLOCKED bajo require_complete."""
    s = _make_complete_setup(direction=1, with_confirmation=False)
    result = classify_eligibility(s, {"htf_bias": "bullish"}, require_complete=True)
    assert result is SetupEligibility.BLOCKED
    assert "confirmation" in s.reason


def test_setup_blocked_when_trigger_missing():
    """H2: falta trigger (DISPLACEMENT) => BLOCKED bajo require_complete."""
    s = _make_complete_setup(direction=1, with_trigger=False)
    result = classify_eligibility(s, {"htf_bias": "bullish"}, require_complete=True)
    assert result is SetupEligibility.BLOCKED
    assert "trigger" in s.reason


def test_complete_check_skipped_when_not_required():
    """Sin require_complete, un setup sin confirmation/trigger NO se bloquea por eso."""
    s = _make_complete_setup(direction=1, with_confirmation=False, with_trigger=False)
    result = classify_eligibility(s, {"htf_bias": "bullish"})
    assert result is SetupEligibility.ELIGIBLE


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
