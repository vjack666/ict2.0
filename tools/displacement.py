"""Displacement (geometria pura, SIN ATR) — rescate aislado de SMC-SYSTEMS.

Fuente: SMC-SYSTEMS/detectors/displacement.py (migrado de ATR a rango puro).
Motor nuevo ICT SYSTEM lo usa via tools/ (aislado, sin engine/).

Metrica MATEMATICA PURA del grafico:
  avg_range = media_movil(high - low, period=14)   # rango promedio de contexto
  body      = |close - open|
  body_ratio= body / candle_range
  displacement = (cierre>apertura) & (body > avg_range * 1.5) & (mecha < 40%)

No usa ATR (true range) por defecto; si se quiere, cambiar _avg_candle_range
a true range. Ambos son matematica, no senal.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DisplacementConfig:
    body_range_multiple: float = 1.5
    wick_threshold: float = 0.4
    range_period: int = 14


def _avg_candle_range(frame: pd.DataFrame, period: int) -> pd.Series:
    """Rango promedio de la vela = media movil de (high - low). Geometria pura."""
    candle_range = (frame["high"] - frame["low"]).clip(lower=0.0)
    return candle_range.rolling(period).mean()


def detect_displacement(
    frame: pd.DataFrame,
    config: DisplacementConfig | None = None,
) -> pd.DataFrame:
    if config is None:
        config = DisplacementConfig()

    data = frame.copy()
    avg_range = _avg_candle_range(data, config.range_period)

    body = (data["close"] - data["open"]).abs()
    candle_range = (data["high"] - data["low"]).replace(0, pd.NA)
    body_ratio = (body / candle_range).fillna(0.0)
    wick_ratio = 1.0 - body_ratio

    bullish_body = data["close"] > data["open"]
    bearish_body = data["close"] < data["open"]
    rng = avg_range.fillna(1e-9)

    large_body = body > rng * config.body_range_multiple
    small_wick = wick_ratio < config.wick_threshold

    data["displacement_bullish"] = (bullish_body & large_body & small_wick).astype(bool)
    data["displacement_bearish"] = (bearish_body & large_body & small_wick).astype(bool)

    data["displacement_magnitude"] = np.where(
        data["displacement_bullish"] | data["displacement_bearish"],
        body / rng,
        0.0,
    )

    return data
