"""F2 — Warm-up y disponibilidad del sesgo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from ict_backtest.sesgo.config import SesgoConfig


@dataclass(frozen=True)
class WarmupState:
    available: bool
    available_since: Optional[datetime]
    closed_counts: dict[str, int]


class WarmupTracker:
    """Registra disponibilidad del sesgo según warm-up por TF."""

    def __init__(self, config: SesgoConfig | None = None) -> None:
        self.config = config or SesgoConfig()
        self._counts: dict[str, int] = {tf: 0 for tf in self.config.warmup}
        self._available_since: Optional[datetime] = None

    def record_closure(self, timeframe: str, count: int = 1) -> WarmupState:
        if timeframe not in self._counts:
            raise ValueError(f"unexpected timeframe: {timeframe}")

        self._counts[timeframe] += count

        if not self._available_since and all(
            self._counts[tf] >= self.config.warmup_for(tf) for tf in self.config.warmup
        ):
            self._available_since = pd.Timestamp.utcnow().to_pydatetime()

        return self.state()

    def state(self) -> WarmupState:
        available = all(
            self._counts[tf] >= self.config.warmup_for(tf) for tf in self.config.warmup
        )
        return WarmupState(
            available=available,
            available_since=self._available_since,
            closed_counts=dict(self._counts),
        )
