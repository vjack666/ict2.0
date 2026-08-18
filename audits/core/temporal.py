"""Point-in-time audit helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class TemporalViolation:
    record_id: str
    code: str
    message: str


def audit_ordered_events(events: Iterable[dict[str, Any]]) -> list[TemporalViolation]:
    """Return violations where parent/candidate information appears after observation."""
    violations: list[TemporalViolation] = []
    for event in events:
        rid = str(event.get("id", "<unknown>"))
        candidate = event.get("candidate_time")
        confirmation = event.get("confirmation_time")
        tradable = event.get("tradable_time")
        observation = event.get("observation_time")
        if candidate is not None and confirmation is not None and candidate > confirmation:
            violations.append(TemporalViolation(rid, "TEMPORAL_ORDER", "candidate_time > confirmation_time"))
        if confirmation is not None and tradable is not None and confirmation > tradable:
            violations.append(TemporalViolation(rid, "TEMPORAL_ORDER", "confirmation_time > tradable_time"))
        if tradable is not None and observation is not None and tradable > observation:
            violations.append(TemporalViolation(rid, "LOOK_AHEAD", "tradable_time > observation_time"))
        parent_time = event.get("parent_time")
        if parent_time is not None and observation is not None and parent_time > observation:
            violations.append(TemporalViolation(rid, "LOOK_AHEAD", "parent_time > observation_time"))
    return violations


def prefix_invariant(full_events: list[dict[str, Any]], prefix_observation: Any) -> list[str]:
    """Detect events that claim availability after the requested prefix."""
    violations: list[str] = []
    for event in full_events:
        obs = event.get("observation_time")
        if obs is not None and obs <= prefix_observation:
            if event.get("tradable_time") is not None and event["tradable_time"] > prefix_observation:
                violations.append(str(event.get("id", "<unknown>")))
    return violations
