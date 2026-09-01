"""Tests del modelo de datos del Setup Builder (engine/setup_builder.py).

Cubre UNICAMENTE el modelo (Setup / SetupEligibility) y su serializacion
to_dict/from_dict. NO valida logica de composicion (otros agentes).

Invariantes verificados:
- El Setup NO altera object_state de los MarketObjects referenciados.
- to_dict/from_dict es un round-trip JSON-safe fiel.
- La linea de linaje (used_by_setup) se lee de POI.meta, no del Setup.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from engine.setup_builder import Setup, SetupEligibility


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
# SetupEligibility
# --------------------------------------------------------------------------- #
def test_eligibility_members_and_str_values():
    assert SetupEligibility.ELIGIBLE.value == "ELIGIBLE"
    assert SetupEligibility.BLOCKED.value == "BLOCKED"
    assert SetupEligibility.OUT_OF_CONTEXT.value == "OUT_OF_CONTEXT"
    assert SetupEligibility.SUPERSEDED.value == "SUPERSEDED"
    # hereda de str -> serializa directo a JSON
    assert json.dumps({"e": SetupEligibility.ELIGIBLE}) == '{"e": "ELIGIBLE"}'


def test_eligibility_construct_from_value():
    assert SetupEligibility("BLOCKED") is SetupEligibility.BLOCKED


# --------------------------------------------------------------------------- #
# construccion / validacion
# --------------------------------------------------------------------------- #
def test_setup_defaults():
    s = Setup()
    assert isinstance(s.id, str) and len(s.id) > 0
    assert s.direction == 0
    assert s.eligibility is SetupEligibility.ELIGIBLE
    assert s.context_htf is None
    assert s.poi is None


def test_setup_direction_validation():
    Setup(direction=1)
    Setup(direction=-1)
    Setup(direction=0)
    with pytest.raises(ValueError):
        Setup(direction=2)
    with pytest.raises(ValueError):
        Setup(direction=-5)


def test_setup_eligibility_coercion_from_string():
    s = Setup(eligibility="BLOCKED")
    assert s.eligibility is SetupEligibility.BLOCKED


# --------------------------------------------------------------------------- #
# round-trip to_dict / from_dict
# --------------------------------------------------------------------------- #
def test_to_from_dict_roundtrip_full():
    poi = _make_mo(Role.POI, origin_tf="H4")
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1", mo_type=ObjectType.BOS)
    ref = _make_mo(Role.REFINEMENT, origin_tf="H1")
    conf = _make_mo(Role.REFINEMENT, origin_tf="M15", mo_type=ObjectType.CHOCH)
    trig = _make_mo(Role.EXECUTION, origin_tf="M5", mo_type=ObjectType.CANDLE)

    s = Setup(
        id="setup-1",
        symbol="EURUSD",
        direction=1,
        context_htf=ctx,
        poi=poi,
        refinement=ref,
        confirmation=conf,
        trigger=trig,
        eligibility=SetupEligibility.ELIGIBLE,
        reason="HTF BOS + FVG POI",
        created_at=datetime(2026, 8, 28, 12, 0, 0),
        meta={"score": 0.9, "flags": {"a", "b"}},  # set -> lista ordenada
    )

    d = s.to_dict()
    # elegibilidad serializa como valor string
    assert d["eligibility"] == "ELIGIBLE"
    assert d["direction"] == 1
    # meta normalizada: el set se serializa como lista ordenada
    assert d["meta"]["flags"] == ["a", "b"]
    # created_at serializa via isoformat
    assert d["created_at"] == "2026-08-28T12:00:00"
    # objetos anidados serializados
    assert isinstance(d["poi"], dict) and d["poi"]["role"] == "POI"

    # JSON-safe: debe poder volcarse a JSON y reconstruirse
    js = json.dumps(d)
    d2 = json.loads(js)
    s2 = Setup.from_dict(d2)

    assert s2.id == "setup-1"
    assert s2.symbol == "EURUSD"
    assert s2.direction == 1
    assert s2.eligibility is SetupEligibility.ELIGIBLE
    assert s2.reason == "HTF BOS + FVG POI"
    assert s2.created_at == "2026-08-28T12:00:00"  # sigue como string (sin parse)
    assert s2.meta["flags"] == ["a", "b"]

    # objetos anidados reconstruidos fielmente
    assert isinstance(s2.poi, MarketObject)
    assert s2.poi.role is Role.POI
    assert s2.poi.origin_tf == "H4"
    assert s2.context_htf.role is Role.CONTEXT
    assert s2.refinement.origin_tf == "H1"
    assert s2.confirmation.type is ObjectType.CHOCH
    assert s2.trigger.origin_tf == "M5"


def test_to_from_dict_with_none_objects():
    s = Setup(id="x", symbol="GBPUSD", direction=-1,
              eligibility=SetupEligibility.BLOCKED, reason="no context")
    d = s.to_dict()
    assert d["context_htf"] is None
    assert d["poi"] is None
    assert d["refinement"] is None
    assert d["confirmation"] is None
    assert d["trigger"] is None
    s2 = Setup.from_dict(d)
    assert s2.context_htf is None
    assert s2.poi is None
    assert s2.direction == -1
    assert s2.eligibility is SetupEligibility.BLOCKED


# --------------------------------------------------------------------------- #
# linaje: used_by_setup vive en POI.meta (solo lectura)
# --------------------------------------------------------------------------- #
def test_used_by_setup_reads_from_poi_meta():
    poi = _make_mo(Role.POI, origin_tf="H4")
    s = Setup(symbol="EURUSD", poi=poi)
    assert s.used_by_setup == []  # sin linaje -> lista vacia

    poi.meta["used_by_setup"] = ["setup-A", "setup-B"]
    assert s.used_by_setup == ["setup-A", "setup-B"]

    # no es el mismo objeto mutable (copia defensiva)
    lst = s.used_by_setup
    lst.append("setup-C")
    assert s.used_by_setup == ["setup-A", "setup-B"]


def test_used_by_setup_none_poi():
    s = Setup(symbol="XAUUSD")
    assert s.used_by_setup == []


# --------------------------------------------------------------------------- #
# INVARIANTE: el Setup NO muta object_state de los MarketObjects
# --------------------------------------------------------------------------- #
def test_setup_does_not_mutate_market_object_state():
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.state = ObjectState.ACTIVE
    ctx = _make_mo(Role.CONTEXT, origin_tf="D1")
    ctx.state = ObjectState.ACTIVE

    s = Setup(symbol="EURUSD", direction=1, poi=poi, context_htf=ctx)
    # operaciones de serializacion NO deben tocar el estado de los objetos
    d = s.to_dict()
    s2 = Setup.from_dict(d)

    assert poi.state is ObjectState.ACTIVE
    assert ctx.state is ObjectState.ACTIVE
    # y el objeto reconstruido tampoco muto el original
    assert poi.state is ObjectState.ACTIVE


def test_setup_does_not_mutate_poi_meta_on_read():
    poi = _make_mo(Role.POI, origin_tf="H4")
    poi.meta["used_by_setup"] = ["setup-1"]
    s = Setup(symbol="EURUSD", poi=poi)
    _ = s.used_by_setup
    # leer linaje no agrega el id del setup al meta del POI
    assert poi.meta["used_by_setup"] == ["setup-1"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
