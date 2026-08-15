"""Tipos para la medición de demostración del sesgo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ict_backtest.sesgo.motor_cable.cable_bias import SesgoVigente


@dataclass(frozen=True)
class SesgoRow:
    m15_index: int
    m15_timestamp: pd.Timestamp
    vigente: Optional[SesgoVigente]
    future_delta: Optional[float]
