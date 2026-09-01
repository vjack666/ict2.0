"""Auditor point-in-time y look-ahead."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class TemporalViolation:
    record_id: str
    code: str
    message: str


def audit_events(events: Iterable[dict[str, Any]]) -> list[TemporalViolation]:
    violations: list[TemporalViolation] = []
    for event in events:
        rid = str(event.get("id", "<unknown>"))
        candidate = event.get("candidate_time")
        confirmation = event.get("confirmation_time")
        tradable = event.get("tradable_time")
        observation = event.get("observation_time")
        parent_time = event.get("parent_time")
        checks = (
            (candidate, confirmation, "TEMPORAL_ORDER", "candidate_time > confirmation_time"),
            (confirmation, tradable, "TEMPORAL_ORDER", "confirmation_time > tradable_time"),
            (tradable, observation, "LOOK_AHEAD", "tradable_time > observation_time"),
            (parent_time, observation, "LOOK_AHEAD", "parent_time > observation_time"),
        )
        for left, right, code, message in checks:
            if left is not None and right is not None and left > right:
                violations.append(TemporalViolation(rid, code, message))
    return violations


def prefix_violations(events: Iterable[dict[str, Any]], prefix_observation: Any) -> list[str]:
    violations: list[str] = []
    for event in events:
        rid = str(event.get("id", "<unknown>"))
        observation = event.get("observation_time")
        tradable = event.get("tradable_time")
        if observation is not None and observation <= prefix_observation and tradable is not None and tradable > prefix_observation:
            violations.append(rid)
    return violations
