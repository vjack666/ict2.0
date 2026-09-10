"""Clasificación explicable de la relación ICT ↔ Wyckoff."""
from __future__ import annotations

from typing import Iterable

from .types import WyckoffEvent, WyckoffEventType, WyckoffPhase, WyckoffPhaseState


_EVENT_DIRECTIONS = {
    WyckoffEventType.SPRING: 1,
    WyckoffEventType.SOS: 1,
    WyckoffEventType.UPTHRUST: -1,
    WyckoffEventType.UTAD: -1,
    WyckoffEventType.SOW: -1,
}


def phase_direction(phase: WyckoffPhase) -> int:
    if phase in {WyckoffPhase.ACCUMULATION, WyckoffPhase.MARKUP}:
        return 1
    if phase in {WyckoffPhase.DISTRIBUTION, WyckoffPhase.MARKDOWN}:
        return -1
    return 0


def _event_direction(event: WyckoffEvent) -> int:
    """Return the directional implication of a causal transition event."""
    direction = _EVENT_DIRECTIONS.get(event.event_type)
    if direction is not None:
        return direction
    if event.event_type is not WyckoffEventType.RANGE_BREAK:
        return 0
    raw = event.detail.get("direction", event.detail.get("break_direction", ""))
    if isinstance(raw, (int, float)):
        return 1 if raw > 0 else -1 if raw < 0 else 0
    label = str(raw).upper()
    if label in {"BULLISH", "UP", "UPSIDE", "ABOVE_RESISTANCE"}:
        return 1
    if label in {"BEARISH", "DOWN", "DOWNSIDE", "BELOW_SUPPORT"}:
        return -1
    return 0


def classify_alignment(
    phase: WyckoffPhase,
    ict_direction: int,
    events: Iterable[WyckoffEvent] = (),
) -> tuple[WyckoffPhaseState, str, bool, str]:
    """Devuelve phase_state, alignment, conflict y explicación.

    El resultado nunca cambia ``ict_direction`` ni emite un veto.
    """
    wy_direction = phase_direction(phase)
    if phase is WyckoffPhase.TRANSITION:
        return WyckoffPhaseState.TRANSITION, "UNRESOLVED", False, "fase Wyckoff en transición; falta confirmación ICT"
    if wy_direction == 0 or ict_direction == 0:
        return WyckoffPhaseState.NEUTRAL, "UNRESOLVED", False, "sin dirección comparable entre ICT y Wyckoff"
    if wy_direction == ict_direction:
        return WyckoffPhaseState.PRO_TREND, "ALIGNED", False, "proceso Wyckoff y dirección ICT compatibles"
    if any(_event_direction(event) == wy_direction for event in events):
        return WyckoffPhaseState.COUNTERTREND, "CONFLICT", True, "Wyckoff opuesto al contexto ICT con evidencia de transición compatible"
    return WyckoffPhaseState.TRANSITION, "CONFLICT", True, "Wyckoff opuesto al contexto ICT sin confirmación suficiente"


__all__ = ["classify_alignment", "phase_direction"]
