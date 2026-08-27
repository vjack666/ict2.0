"""Projection of the canonical Context State / AHF into a Setup State per candle.

FASE 4.1 (corrección de fidelidad al grafo): este módulo es un ADAPTER /
PROJECTION / EXPLANATION del estado AHF canónico. NO re-deriva la FSM de setup.

Camino correcto (grafo como mapa):

    AdaptiveHierarchicalFunnel.step(T)   # engine/ahf.py — AUTORIDAD
              ↓
         AHFSnapshot
              ↓
    setup_builder.py  SOLO ADAPTA
              ↓
        JSON / VISOR

El replay (backtest/replay.py) instancia el funnel una vez por run y serializa
cada AHFSnapshot en timeline[i]["ict"]["context"]; también pasa la lista de
ahf_snapshots a build_setup_state. Este módulo traduce AHFSnapshot -> Setup State
y nunca recalcula reglas AHF (no hay transiciones propias, no hay invalidacion=[]
por defecto).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backtest.schema import json_safe


# The canonical setup machine states (descriptive projection of AHFSnapshot.state).
SETUP_STATES = (
    "WAIT_D1",
    "D1_LOCKED",
    "WAIT_H4",
    "H4_LOCKED",
    "WAIT_H1",
    "WAIT_LTF",
    "SETUP_READY",
    "OUTCOME",
)


def _translate_snapshot(snap: Any, point: Mapping[str, Any], authority_tf: str) -> dict[str, Any]:
    """Translate a canonical AHFSnapshot into a Setup State projection.

    The AHF funnel is the single source of truth for state/active_tf/invalidation.
    We only rename/flatten fields for the viewer; we do NOT recompute logic.
    ``snap`` may be an AHFSnapshot dataclass or its .to_dict() mapping.
    """
    history = getattr(snap, "history", None)
    if hasattr(snap, "to_dict"):
        snap = snap.to_dict()
    if history is None and isinstance(snap, Mapping):
        history = snap.get("history") or []
    state = str(snap.get("state") or "WAIT_D1")
    active_tf = str(snap.get("active_tf") or "H1")
    confirmed = snap.get("confirmed_context") or {}
    last_event = str(snap.get("last_event") or "NOOP")
    invalidation_reason = snap.get("invalidation_reason")
    if not invalidation_reason and history:
        last = history[-1]
        invalidation_reason = (
            getattr(last, "invalidation_reason", None)
            if not isinstance(last, Mapping)
            else last.get("invalidation_reason")
        )

    # Present/ missing layers: which HTF context layers the AHF has locked.
    presentes = [tf for tf in ("D1", "H4", "H1") if tf in confirmed]
    faltantes = [tf for tf in ("D1", "H4", "H1") if tf not in confirmed]

    cadena = [tf for tf in ("D1", "H4", "H1", active_tf) if tf]
    # de-duplicate preserving order
    seen = set()
    cadena = [tf for tf in cadena if not (tf in seen or seen.add(tf))]

    invalidacion = [invalidation_reason] if invalidation_reason else []

    return {
        "id": f"SETUP_{int(point['index'])}",
        "decision_time": point["decision_time"],
        "authority_tf": authority_tf,
        "direction": None,
        "cadena_htf_ltf": cadena,
        "estado": state,
        "active_tf": active_tf,
        "condiciones_presentes": presentes,
        "condiciones_faltantes": faltantes,
        "invalidacion": invalidacion,
        "evidence_refs": [],
        "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
    }


def build_setup_state(
    timeline: list[dict[str, Any]],
    config: Any,
    ahf_snapshots: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Build a Setup State projection per visible candle.

    FASE 4.1: the Setup State is a pure translation of the canonical AHFSnapshot
    (produced by engine.ahf.AdaptiveHierarchicalFunnel). When ``ahf_snapshots`` is
    supplied (by the replay), we translate it directly. We never re-derive the FSM.

    If ``ahf_snapshots`` is absent, we fall back to whatever the timeline already
    carries under ``ict.context`` (status NOT_REQUESTED -> empty projection) and we
    DO NOT invent states.
    """
    authority_tf = config.authority_tf.upper()

    if ahf_snapshots is not None and len(ahf_snapshots) == len(timeline):
        return json_safe(
            [
                _translate_snapshot(snap, point, authority_tf)
                for snap, point in zip(ahf_snapshots, timeline)
            ]
        )

    # Schema 1.2 requires the canonical snapshot. A fallback state would be a
    # fabricated setup signal and would hide a broken AHF projection.
    out: list[dict[str, Any]] = []
    for point in timeline:
        ctx = point.get("ict", {}).get("context") or {}
        snap = ctx.get("ahf_snapshot") or ctx.get("snapshot")
        if not snap:
            raise ValueError(
                "canonical AHFSnapshot missing from timeline; refusing to fabricate Setup State"
            )
        out.append(_translate_snapshot(snap, point, authority_tf))
    return json_safe(out)


__all__ = ["SETUP_STATES", "build_setup_state"]
