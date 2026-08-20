"""Tipos runtime de la capa Wyckoff especializada.

Los tipos son inmutables, serializables y no representan órdenes ni señales.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class WyckoffPhase(str, Enum):
    ACCUMULATION = "ACCUMULATION"
    MARKUP = "MARKUP"
    DISTRIBUTION = "DISTRIBUTION"
    MARKDOWN = "MARKDOWN"
    RANGE_UNCLASSIFIED = "RANGE_UNCLASSIFIED"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class WyckoffPhaseState(str, Enum):
    PRO_TREND = "PRO_TREND"
    COUNTERTREND = "COUNTERTREND"
    TRANSITION = "TRANSITION"
    NEUTRAL = "NEUTRAL"


class WyckoffEventType(str, Enum):
    SPRING = "SPRING"
    UPTHRUST = "UPTHRUST"
    UTAD = "UTAD"
    SOS = "SOS"
    SOW = "SOW"
    LPS = "LPS"
    LPSY = "LPSY"
    TEST = "TEST"
    FAILED_TEST = "FAILED_TEST"
    RANGE_BREAK = "RANGE_BREAK"
    EFFORT_RESULT_DIVERGENCE = "EFFORT_RESULT_DIVERGENCE"


class VolumeMode(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    RELATIVE_ONLY = "RELATIVE_ONLY"


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    if hasattr(value, "item"):
        try:
            return _safe(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


@dataclass(frozen=True)
class WyckoffEvent:
    event_id: str
    event_type: WyckoffEventType
    tf: str
    event_time: Any
    source_ref: str
    evidence_refs: tuple[str, ...] = ()
    confirmation_status: str = "OBSERVED"
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "tf": self.tf,
            "event_time": _safe(self.event_time),
            "source_ref": self.source_ref,
            "evidence_refs": list(self.evidence_refs),
            "confirmation_status": self.confirmation_status,
            "detail": _safe(self.detail),
        }


@dataclass(frozen=True)
class WyckoffSnapshot:
    phase: WyckoffPhase = WyckoffPhase.UNKNOWN
    phase_state: WyckoffPhaseState = WyckoffPhaseState.NEUTRAL
    authority_tf: str = ""
    range_ref: Mapping[str, Any] = field(default_factory=dict)
    events: tuple[WyckoffEvent, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    effort_result: Mapping[str, Any] = field(default_factory=dict)
    volume_mode: VolumeMode = VolumeMode.UNAVAILABLE
    ict_alignment: str = "UNRESOLVED"
    conflict: bool = False
    explanation: str = ""
    layers: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    decision_time: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "phase_state": self.phase_state.value,
            "authority_tf": self.authority_tf,
            "range_ref": _safe(self.range_ref),
            "events": [event.to_dict() for event in self.events],
            "evidence_refs": list(self.evidence_refs),
            "effort_result": _safe(self.effort_result),
            "volume_mode": self.volume_mode.value,
            "ict_alignment": self.ict_alignment,
            "conflict": bool(self.conflict),
            "explanation": self.explanation,
            "layers": _safe(self.layers),
            "decision_time": _safe(self.decision_time),
            "policy": "WYCKOFF_CONTEXT_ONLY_NOT_ENTRY",
        }


__all__ = [
    "WyckoffEvent",
    "WyckoffEventType",
    "WyckoffPhase",
    "WyckoffPhaseState",
    "WyckoffSnapshot",
    "VolumeMode",
]
