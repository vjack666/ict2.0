"""Projection of the canonical Context State / AHF into a Setup State per candle.

This module is an ADAPTER / PROJECTION / EXPLANATION (FASE 4, SDD v1.2 §5). It is
NOT a second setup FSM and it does NOT recompute AHF rules. The project already
owns the setup machine inside Context State / AHF:

    WAIT_D1 -> D1_LOCKED -> WAIT_H4 -> H4_LOCKED -> WAIT_H1 -> WAIT_LTF -> SETUP_READY

This module only EXPOSES and EXPLAINS that canonical state by reading the fields
already present in ``timeline[i]["ict"]["context"]`` (the serialized
``engine.mtf_navigation.MarketState``). It never derives new decision logic.
"""

from __future__ import annotations

from typing import Any, Mapping

from backtest.schema import json_safe


# The canonical setup machine states (descriptive projection, not a new FSM).
SETUP_STATES = (
    "WAIT_D1",
    "D1_LOCKED",
    "WAIT_H4",
    "H4_LOCKED",
    "WAIT_H1",
    "WAIT_LTF",
    "SETUP_READY",
)


def _bias(layer: Mapping[str, Any] | None) -> str:
    if not layer:
        return "UNKNOWN"
    return str(layer.get("structure_bias") or "UNKNOWN")


def _has_zones(layer: Mapping[str, Any] | None) -> bool:
    if not layer:
        return False
    return bool(layer.get("zones"))


def _derive_setup(context: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the setup machine state from the canonical context (read-only).

    This is a descriptive projection: it reads ``structure_bias`` and ``zones``
    already computed by the canonical Context State / AHF engine. It does not
    recompute any AHF rule.
    """
    layers = context.get("layers") or {}
    d1 = layers.get("D1")
    h4 = layers.get("H4")
    h1 = layers.get("H1")
    exec_tf = str(context.get("exec_tf") or "")

    d1_bias = _bias(d1)
    h4_bias = _bias(h4)
    h1_bias = _bias(h1)

    presentes: list[str] = []
    faltantes: list[str] = []

    if d1_bias != "UNKNOWN":
        presentes.append("D1 context")
        state = "D1_LOCKED"
    else:
        faltantes.append("D1 context")
        state = "WAIT_D1"

    if state == "D1_LOCKED":
        if h4_bias != "UNKNOWN":
            presentes.append("H4 POI")
            state = "H4_LOCKED"
        else:
            faltantes.append("H4 POI")
            state = "WAIT_H4"

    if state == "H4_LOCKED":
        if h1_bias != "UNKNOWN":
            presentes.append("H1 process confirmation")
            state = "WAIT_LTF"
        else:
            faltantes.append("H1 process confirmation")
            state = "WAIT_H1"

    if state == "WAIT_LTF":
        # LTF confirmation is the execution layer (exec_tf) having actionable zones.
        exec_layer = layers.get(exec_tf)
        if _has_zones(exec_layer):
            presentes.append(f"{exec_tf} LTF confirmation")
            state = "SETUP_READY"
        else:
            faltantes.append(f"{exec_tf} LTF confirmation")

    active_tf = exec_tf or "M15"
    return {
        "estado": state,
        "active_tf": active_tf,
        "presentes": presentes,
        "faltantes": faltantes,
        "invalidacion": [],
    }


def build_setup_state(
    timeline: list[dict[str, Any]],
    config: Any,
) -> list[dict[str, Any]]:
    """Build a Setup State projection per visible candle.

    Returns a list of setups (one per timeline point), each exposing the canonical
    Context State / AHF machine state without recomputing AHF rules.
    """
    authority_tf = config.authority_tf.upper()
    setups: list[dict[str, Any]] = []
    for point in timeline:
        context = point.get("ict", {}).get("context") or {}
        derived = _derive_setup(context)
        setups.append(
            {
                "id": f"SETUP_{int(point['index'])}",
                "decision_time": point["decision_time"],
                "authority_tf": authority_tf,
                "direction": None,
                "cadena_htf_ltf": ["D1", "H4", "H1", derived["active_tf"]],
                "estado": derived["estado"],
                "active_tf": derived["active_tf"],
                "condiciones_presentes": derived["presentes"],
                "condiciones_faltantes": derived["faltantes"],
                "invalidacion": derived["invalidacion"],
                "evidence_refs": [],
                "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
            }
        )
    return json_safe(setups)


__all__ = ["SETUP_STATES", "build_setup_state"]
