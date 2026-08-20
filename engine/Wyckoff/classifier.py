"""Clasificación explicable de la relación ICT ↔ Wyckoff."""
from __future__ import annotations

from typing import Iterable

from .types import WyckoffEvent, WyckoffEventType, WyckoffPhase, WyckoffPhaseState


def phase_direction(phase: WyckoffPhase) -> int:
    if phase in {WyckoffPhase.ACCUMULATION, WyckoffPhase.MARKUP}:
        return 1
    if phase in {WyckoffPhase.DISTRIBUTION, WyckoffPhase.MARKDOWN}:
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
    event_types = {event.event_type for event in events}
    has_transition_evidence = bool(
        event_types & {
            WyckoffEventType.SPRING,
            WyckoffEventType.UPTHRUST,
            WyckoffEventType.UTAD,
            WyckoffEventType.SOS,
            WyckoffEventType.SOW,
            WyckoffEventType.RANGE_BREAK,
        }
    )
    if phase is WyckoffPhase.TRANSITION:
        return WyckoffPhaseState.TRANSITION, "UNRESOLVED", False, "fase Wyckoff en transición; falta confirmación ICT"
    if wy_direction == 0 or ict_direction == 0:
        return WyckoffPhaseState.NEUTRAL, "UNRESOLVED", False, "sin dirección comparable entre ICT y Wyckoff"
    if wy_direction == ict_direction:
        return WyckoffPhaseState.PRO_TREND, "ALIGNED", False, "proceso Wyckoff y dirección ICT compatibles"
    if has_transition_evidence:
        return WyckoffPhaseState.COUNTERTREND, "CONFLICT", True, "Wyckoff opuesto al contexto ICT con evidencia inicial de transición"
    return WyckoffPhaseState.TRANSITION, "CONFLICT", True, "Wyckoff opuesto al contexto ICT sin confirmación suficiente"


__all__ = ["classify_alignment", "phase_direction"]
