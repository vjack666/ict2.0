"""T3 — Configuración única del backtest del sesgo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class SesgoConfig:
    symbol_default: str = "EURUSD"
    m15_step_minutes: int = 15
    m15_k_future: int = 48
    aggregation: Dict[str, int] = None  # type: ignore[assignment]
    warmup: Dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "aggregation", {"H1": 4, "H4": 16, "D1": 96})
        object.__setattr__(self, "warmup", {"D1": 20, "H4": 60, "H1": 100})

    def aggregation_buckets(self) -> Tuple[str, ...]:
        return tuple(self.aggregation.keys())

    def warmup_for(self, timeframe: str) -> int:
        return self.warmup[timeframe]

    def aggregation_ratio(self, timeframe: str) -> int:
        return self.aggregation[timeframe]
