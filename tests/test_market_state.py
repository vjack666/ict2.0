"""Tests obligatorios del brief REV_AGENT1 — historial causal real en MarketState.

Cubre los 4 escenarios obligatorios del auditor:
  1) ACTIVE@T=10 e INVALIDATED@T=13 (replay causal, sin look-ahead).
  2) Round-trip FULL SAVE -> LOAD -> CONTINUE idéntico.
  3) El snapshot pasado NO cambia tras avanzar el motor (snapshot_at(10) sigue
     ACTIVE después de invalidar en 13).
  4) No se devuelven referencias vivas: mutar el objeto actual no cambia
     projection_at(10).
"""

from __future__ import annotations

from datetime import datetime, timezone

from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState

UTC = timezone.utc
T10 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
T11 = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
T13 = datetime(2026, 1, 1, 13, 0, tzinfo=UTC)
T20 = datetime(2026, 1, 1, 20, 0, tzinfo=UTC)


def _make_obj(obj_id: str, creation_time, state: ObjectState) -> MarketObject:
    return MarketObject(
        id=obj_id,
        symbol="XAUUSD",
        type=ObjectType.FVG,
        origin_tf="H1",
        authority_tf="H1",
        role=Role.REFINEMENT,
        direction=1,  # bull: far_side = zone_low
        zone_high=2000.0,
        zone_low=1990.0,
        creation_time=creation_time,
        state=state,
        bar_index=10,
    )


def _invalidate_bar(t: datetime, index: int) -> dict:
    # low <= zone_low(1990) y close < 1990 => INVALIDATED (far_side close beyond)
    return {"time": t, "index": index, "tf": "H1", "high": 1985.0, "low": 1980.0, "close": 1975.0}


def _neutral_bar(t: datetime, index: int) -> dict:
    return {"time": t, "index": index, "tf": "H1", "high": 1995.0, "low": 1992.0, "close": 1993.0}


# --- Escenario 1: ACTIVE@10, INVALIDATED@13 ---------------------------------
def test_active_at_10_invalidated_at_13():
    ms = MarketState()
    ms.ingest(_make_obj("o1", T10, ObjectState.ACTIVE))
    assert ms.state_at("o1", T10) == ObjectState.ACTIVE
    assert ms.state_at("o1", T11) == ObjectState.ACTIVE

    ms.advance_bar("o1", _invalidate_bar(T13, 13))
    assert ms.state_at("o1", T13) == ObjectState.INVALIDATED
    # El estado actual del motor también es INVALIDATED (coherencia).
    assert ms.authority_of("o1") == "H1"
    assert ms.all_objects()[0].state == ObjectState.INVALIDATED

    # snapshot_at refleja el estado histórico, no el actual hacia atrás.
    snap10 = ms.snapshot_at(T10)
    assert snap10["active_ids"] == ["o1"]
    assert "o1" not in snap10["dead_ids"]

    snap13 = ms.snapshot_at(T13)
    assert snap13["dead_ids"] == ["o1"]
    assert "o1" not in snap13["active_ids"]


# --- Escenario 3: snapshot pasado inmutable tras avanzar el motor -----------
def test_past_snapshot_unchanged_after_future_advance():
    ms = MarketState()
    ms.ingest(_make_obj("o1", T10, ObjectState.ACTIVE))
    snap_before = ms.snapshot_at(T10)
    assert snap_before["active_ids"] == ["o1"]

    ms.advance_bar("o1", _invalidate_bar(T13, 13))
    # Tras invalidar en 13, el snapshot en 10 sigue mostrando ACTIVE.
    snap_after = ms.snapshot_at(T10)
    assert snap_after["active_ids"] == ["o1"]
    assert snap_after["dead_ids"] == []
    assert ms.state_at("o1", T10) == ObjectState.ACTIVE
    assert ms.state_at("o1", T13) == ObjectState.INVALIDATED


# --- Escenario 4: sin referencias vivas -------------------------------------
def test_no_live_references_in_projection():
    ms = MarketState()
    ms.ingest(_make_obj("o1", T10, ObjectState.ACTIVE))
    ms.advance_bar("o1", _invalidate_bar(T13, 13))

    # Proyección en T10 es copia profunda con state histórico ACTIVE.
    proj = ms.projection_at(T10)["o1"]
    assert proj.state == ObjectState.ACTIVE
    assert proj is not ms.all_objects()[0]  # no es la misma instancia

    # Mutar el objeto ACTUAL no contamina la proyección YA DEVUELTA
    # (garantía anti-look-ahead: la proyección es una copia, no una ref viva).
    live = ms.all_objects()[0]
    live.state = ObjectState.CONSUMED
    live.touch_count = 999
    live.meta["hack"] = True

    assert proj.state == ObjectState.ACTIVE  # inmutable frente a mutación futura
    assert proj.touch_count != 999  # es una copia, no el objeto vivo
    assert "hack" not in proj.meta

    # Una NUEVA proyección en T10 también congela el state histórico (ACTIVE),
    # aunque el objeto vivo ahora esté en CONSUMED.
    proj2 = ms.projection_at(T10)["o1"]
    assert proj2.state == ObjectState.ACTIVE  # replay causal, no estado actual

    # Mutar la proyección devuelta no afecta al objeto vivo.
    proj2.state = ObjectState.EXPIRED
    proj2.meta["mut"] = 1
    assert live.state == ObjectState.CONSUMED
    assert "mut" not in live.meta

    # objects_existing_at también devuelve proyecciones (no vivas).
    existing = ms.objects_existing_at(T10)
    assert len(existing) == 1
    assert existing[0].state == ObjectState.ACTIVE
    assert existing[0] is not live


# --- Escenario 2: FULL replay SAVE -> LOAD -> CONTINUE idéntico --------------
def _build() -> MarketState:
    ms = MarketState()
    ms.ingest(_make_obj("o1", T10, ObjectState.ACTIVE))
    ms.advance_bar("o1", _invalidate_bar(T13, 13))
    return ms


def test_full_replay_save_load_continue_identical():
    ms = _build()
    snapshot_dict = ms.to_dict()

    # Reconstrucción íntegra (incluida la historia causal).
    ms2 = MarketState.from_dict(snapshot_dict)

    # Replay idéntico ANTES de continuar.
    for t in (T10, T11, T13):
        assert ms.state_at("o1", t) == ms2.state_at("o1", t)
    assert ms.snapshot_at(T10) == ms2.snapshot_at(T10)

    # CONTINUAR ambos con la MISMA secuencia de avances.
    ms.advance_bar("o1", _neutral_bar(T20, 20))  # terminal => sin cambio
    ms2.advance_bar("o1", _neutral_bar(T20, 20))

    # Tras continuar idénticamente, el estado completo es idéntico.
    assert ms.to_dict() == ms2.to_dict()
    assert ms.state_at("o1", T20) == ms2.state_at("o1", T20)
    assert ms.authority_of("o1") == ms2.authority_of("o1")


def test_history_records_transitions():
    ms = MarketState()
    ms.ingest(_make_obj("o1", T10, ObjectState.ACTIVE))
    hist = ms.history_of("o1")
    # Transición fundacional al nacer.
    assert len(hist) == 1
    assert hist[0].prev_state is None
    assert hist[0].new_state == ObjectState.ACTIVE

    ms.advance_bar("o1", _invalidate_bar(T13, 13))
    hist = ms.history_of("o1")
    assert len(hist) == 2
    second = hist[1]
    assert second.prev_state == ObjectState.ACTIVE
    assert second.new_state == ObjectState.INVALIDATED
    assert second.timestamp == T13
    assert second.bar_index == 13
    assert second.tf == "H1"


def test_observe_does_not_record_state_transition():
    ms = MarketState()
    ms.ingest(_make_obj("o1", T10, ObjectState.ACTIVE))
    # Observación LTF no cambia estado oficial => sin transición.
    ms.observe("o1", {"time": T11, "index": 11, "tf": "M15", "high": 1996.0, "low": 1994.0, "close": 1995.0}, observed_tf="M15")
    assert ms.history_of("o1") == [] or len(ms.history_of("o1")) == 1  # solo fundacional
    assert ms.all_objects()[0].state == ObjectState.ACTIVE
