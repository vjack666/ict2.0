"""Small, provider-neutral models for mission planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RouteDecision:
    """The department and employee selected for a user request."""

    department_id: str
    department_name: str
    assigned_role: str
    agent_key: str
    task_kind: str
    reason: str
    required_controls: tuple[str, ...]
    required_reviews: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
