"""Tests de dominio y negativos de Episodes / Funnel causal v1.

No usa datos reales: construye MarketState y Setup sintéticos. Verifica:
- aceptación (ELIGIBLE -> ACCEPTED),
- mapeo de elegibilidad (SUPERSEDED/OUT_OF_CONTEXT/BLOCKED -> estados correctos),
- rechazos fail-closed (futuro, orden temporal, autoridad, lineage),
- idempotencia / deduplicación,
- que NO muta los objetos ni el MarketState de entrada,
- determinismo y checksum reproducible,
- integración real: build_episodes acepta candidatos de build_setups_at.

Contrato: docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md
SDD:       docs/planificacion/SDD_EPISODES_FUNNEL_V1.md
"""

from __future__ import annotations

from datetime import datetime

import pytest

from engine.market_object import MarketObject, ObjectType, Role, ObjectState
from engine.market_state import MarketState
from engine.setup_builder import Setup, SetupEligibility, build_setups_at
from engine import episodes as E


# --------------------------------------------------------------------------- #
# helpers de fixture (sintéticos, sin datos reales)
# --------------------------------------------------------------------------- #
def _mo(role, origin_tf="H4", mo_type=ObjectType.FVG, direction=1, related=None,
        parent=None, **kw) -> MarketObject:
    if "id" not in kw:
        kw["id"] = f"{role.value}_{origin_tf}_{direction}_{origin_tf}"
    kw.setdefault("zone_high", 1.1000)
    kw.setdefault("zone_low", 1.0950)
    return MarketObject(
        symbol="EURUSD",
        type=mo_type,
        origin_tf=origin_tf,
        role=role,
        direction=direction,
        related_objects=list(related or []),
        parent_object=parent,
        **kw,
    )


def _ctx(direction=1):
    return {"direction": direction, "aligned": True}


def _related_pair(poi_tf="H4", ltf_tf="M15", direction=1, t_poi=None, t_ref=None,
                  related=True):
    poi = _mo(Role.POI, origin_tf=poi_tf, mo_type=ObjectType.ORDER_BLOCK,
              direction=direction, creation_time=t_poi, candidate_time=t_poi)
    fvg = _mo(Role.REFINEMENT, origin_tf=ltf_tf, mo_type=ObjectType.FVG,
              direction=direction, creation_time=t_ref, candidate_time=t_ref)
    if related:
        poi.related_objects = [fvg.id]
        fvg.related_objects = [poi.id]
    return poi, fvg


def _build_ms(objects):
    ms = MarketState()
    for o in sorted(objects, key=lambda x: (x.origin_tf, x.creation_time or datetime.min)):
        ms.ingest(o)
    return ms


def _setup(poi, fvg, eligibility=SetupEligibility.ELIGIBLE, direction=1, **kw):
    return Setup(symbol="EURUSD", direction=direction, context_htf=None,
                 poi=poi, refinement=fvg, eligibility=eligibility, **kw)


def _run(setup, T, ctx=None, candidates=None):
    ctx = ctx or _ctx(setup.direction)
    cands = candidates if candidates is not None else {T: [setup]}
    ms = _build_ms([setup.poi, setup.refinement])
    return E.build_episodes(ms, [T], ctx, candidates=cands)


# --------------------------------------------------------------------------- #
# T3.1 aceptación / rechazo del Episode
# --------------------------------------------------------------------------- #
def test_eligible_setup_becomes_accepted():
    t = datetime(2024, 1, 2)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0), t_ref=datetime(2024, 1, 1, 1))
    art = _run(_setup(poi, fvg), t)
    assert art["aggregates"]["totals"]["episodes"] == 1
    ep = art["episodes"][0]
    assert ep["status"] == "ACCEPTED"
    assert ep["direction"] == 1
    assert ep["episode_id"].startswith("EP_") and len(ep["episode_id"]) == 27


def test_superseded_maps_to_superseded():
    t = datetime(2024, 1, 2)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0), t_ref=datetime(2024, 1, 1, 1))
    poi.state = ObjectState.INVALIDATED
    art = _run(_setup(poi, fvg, SetupEligibility.SUPERSEDED), t)
    assert art["aggregates"]["totals"]["episodes"] == 1
    assert art["episodes"][0]["status"] == "SUPERSEDED"


def test_blocked_maps_to_rejected_setup_blocked():
    t = datetime(2024, 1, 2)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0), t_ref=datetime(2024, 1, 1, 1))
    art = _run(_setup(poi, fvg, SetupEligibility.BLOCKED,
                       reason="contexto HTF no alineado"), t)
    assert art["aggregates"]["totals"]["episodes"] == 1
    ep = art["episodes"][0]
    assert ep["status"] == "REJECTED"
    assert ep["reason"] == "SETUP_BLOCKED"


def test_out_of_context_maps_to_rejected():
    t = datetime(2024, 1, 2)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0), t_ref=datetime(2024, 1, 1, 1))
    art = _run(_setup(poi, fvg, SetupEligibility.OUT_OF_CONTEXT), t)
    assert art["episodes"][0]["status"] == "REJECTED"
    assert art["episodes"][0]["reason"] == "OUT_OF_CONTEXT"


# --------------------------------------------------------------------------- #
# T3.2 negativos: futuro, autoridad, lineage, duplicados, mutación
# --------------------------------------------------------------------------- #
def test_future_data_rejected():
    # decision_time ANTES de que nazca el POI => projection_at lo excluye y no
    # hay candidato en T (no se inventa).
    t_decision = datetime(2024, 1, 1, 0)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 2, 0), t_ref=datetime(2024, 1, 2, 1))
    ms = _build_ms([poi, fvg])
    art = E.build_episodes(ms, [t_decision], _ctx(1))  # sin override: usa build_setups_at
    assert art["aggregates"]["totals"]["episodes"] == 0


def test_invalid_authority_rejected():
    t = datetime(2024, 1, 2)
    # En v1 el motor rechaza authority_tf != origin_tf al nacer; el funnel lo
    # valida como defensa ante objetos externos/cargados (ruta abnormal).
    poi = _mo(Role.POI, origin_tf="H4", mo_type=ObjectType.ORDER_BLOCK,
              direction=1, creation_time=datetime(2024, 1, 1, 0),
              candidate_time=datetime(2024, 1, 1, 0))
    poi.authority_tf = "M15"  # objeto "externo": autoridad != origen
    fvg = _mo(Role.REFINEMENT, origin_tf="M15", mo_type=ObjectType.FVG,
              direction=1, creation_time=datetime(2024, 1, 1, 1),
              candidate_time=datetime(2024, 1, 1, 1), related=[poi.id])
    poi.related_objects = [fvg.id]
    art = _run(_setup(poi, fvg), t)
    assert art["aggregates"]["totals"]["rejections"] == 1
    assert art["rejections"][0]["stage"] == "LINEAGE"
    assert art["rejections"][0]["reason"] == "INVALID_AUTHORITY"


def test_missing_lineage_rejected():
    t = datetime(2024, 1, 2)
    # POI y refinement NO relacionados -> rechazo en etapa LINEAGE (antes de EPISODE)
    poi = _mo(Role.POI, origin_tf="H4", mo_type=ObjectType.ORDER_BLOCK,
              direction=1, creation_time=datetime(2024, 1, 1, 0),
              candidate_time=datetime(2024, 1, 1, 0))
    fvg = _mo(Role.REFINEMENT, origin_tf="M15", mo_type=ObjectType.FVG,
              direction=1, creation_time=datetime(2024, 1, 1, 1),
              candidate_time=datetime(2024, 1, 1, 1))
    art = _run(_setup(poi, fvg), t)
    assert art["aggregates"]["totals"]["rejections"] == 1
    assert art["rejections"][0]["stage"] == "LINEAGE"
    assert art["rejections"][0]["reason"] == "MISSING_LINEAGE"


def test_temporal_order_rejected():
    t = datetime(2024, 1, 2)
    # refinement NACE después del decision_time -> available_time > T => FUTURE_DATA
    # (rechazo en etapa TEMPORAL, antes de EPISODE)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0),
                              t_ref=datetime(2024, 1, 3, 0))
    art = _run(_setup(poi, fvg), t)
    assert art["aggregates"]["totals"]["rejections"] == 1
    assert art["rejections"][0]["stage"] == "TEMPORAL"
    assert art["rejections"][0]["reason"] == "FUTURE_DATA"


def test_idempotent_deduplication():
    t = datetime(2024, 1, 2)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0), t_ref=datetime(2024, 1, 1, 1))
    s = _setup(poi, fvg)
    ms = _build_ms([poi, fvg])
    art = E.build_episodes(ms, [t, t], _ctx(1), candidates={t: [s, s]})  # mismo setup x2
    accepted = [e for e in art["episodes"] if e["status"] == "ACCEPTED"]
    assert len(accepted) == 1
    assert art["aggregates"]["totals"]["unique_episodes"] == 1
    # un rechazo por DUPLICATE_SETUP queda registrado
    assert any(r["reason"] == "DUPLICATE_SETUP" for r in art["rejections"])


def test_no_mutation_of_inputs():
    t = datetime(2024, 1, 2)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0), t_ref=datetime(2024, 1, 1, 1))
    poi_state_before = poi.state
    ms = _build_ms([poi, fvg])
    snap_before = ms.snapshot_at(t)["existing"]
    setup = _setup(poi, fvg)
    E.build_episodes(ms, [t], _ctx(1), candidates={t: [setup]})
    assert poi.state == poi_state_before
    assert ms.snapshot_at(t)["existing"] == snap_before


# --------------------------------------------------------------------------- #
# T3.3 integración real: build_episodes consume build_setups_at
# --------------------------------------------------------------------------- #
def test_integration_with_build_setups_at():
    """Cadena canónica OB+FVG+BOS+DISPLACEMENT vía build_setups_at real."""
    t_poi = datetime(2024, 1, 1, 0)
    t_ref = datetime(2024, 1, 1, 1)
    t_bos = datetime(2024, 1, 1, 2)
    t_disp = datetime(2024, 1, 1, 3)
    T = datetime(2024, 1, 1, 4)
    # OB H4 y FVG M15 con zonas solapadas, bar_index creciente y OB antes que FVG.
    poi = _mo(Role.POI, "H4", ObjectType.ORDER_BLOCK, 1,
              related=[f"fvg", "bos", "disp"], creation_time=t_poi,
              state=ObjectState.ACTIVE, bar_index=10, candidate_bar=10,
              zone_high=1.1050, zone_low=1.1000)
    fvg = _mo(Role.REFINEMENT, "M15", ObjectType.FVG, 1,
              related=[poi.id, "bos", "disp"], creation_time=t_ref,
              state=ObjectState.ACTIVE, bar_index=20, candidate_bar=20,
              zone_high=1.1020, zone_low=1.0980)
    fvg.parent_object = poi.id
    bos = _mo(Role.CONFIRMATION, "M15", ObjectType.BOS, 1,
              related=[poi.id, fvg.id], creation_time=t_bos,
              bar_index=30, candidate_bar=30)
    disp = _mo(Role.EXECUTION, "M15", ObjectType.DISPLACEMENT, 1,
               related=[fvg.id, poi.id], creation_time=t_disp,
               bar_index=40, candidate_bar=40)
    ms = _build_ms([poi, fvg, bos, disp])
    setups = build_setups_at(ms, T, _ctx(1))
    assert len(setups) >= 1, "build_setups_at debe componer el setup completo"
    assert setups[0].eligibility == SetupEligibility.ELIGIBLE
    art = E.build_episodes(ms, [T], _ctx(1))  # SIN override -> usa build_setups_at
    assert art["aggregates"]["totals"]["episodes"] == 1
    assert art["episodes"][0]["status"] == "ACCEPTED"


# --------------------------------------------------------------------------- #
# T3.5 determinismo / checksum reproducible
# --------------------------------------------------------------------------- #
def _fixture_artifact():
    t = datetime(2024, 1, 2)
    poi, fvg = _related_pair(t_poi=datetime(2024, 1, 1, 0), t_ref=datetime(2024, 1, 1, 1))
    s = _setup(poi, fvg)
    ms = _build_ms([poi, fvg])
    return E.build_episodes(ms, [t], _ctx(1), candidates={t: [s]})


def test_deterministic_checksum():
    a = _fixture_artifact()
    b = _fixture_artifact()
    assert a["checksum"] == b["checksum"]
    assert a["episodes"] == b["episodes"]
    assert a["aggregates"] == b["aggregates"]


def test_episode_id_stable():
    a = _fixture_artifact()
    b = _fixture_artifact()
    assert a["episodes"][0]["episode_id"] == b["episodes"][0]["episode_id"]
