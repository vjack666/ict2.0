from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@dataclass
class AnalysisResult:
    agent_name: str = ""
    bias: str = "NEUTRAL"
    confidence: float = 0.0
    detected_events: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    invalidation_conditions: list[str] = field(default_factory=list)


@runtime_checkable
class AgentProtocol(Protocol):
    name: str

    def analyze(self, context: pd.DataFrame, index: int) -> AnalysisResult:
        ...
