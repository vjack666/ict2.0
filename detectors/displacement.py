from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DisplacementConfig:
    # Múltiplo del RANGO promedio (high-low) que el cuerpo debe superar para
    # contar como displacement. Migrado de body_atr_multiple (ATR) a rango puro
    # (Fase 1): mismo valor inicial (1.5) para medir impacto en Fase 2.
    body_range_multiple: float = 1.5
    wick_threshold: float = 0.4
    range_period: int = 14


def _avg_candle_range(frame: pd.DataFrame, period: int) -> pd.Series:
    """Rango promedio de la vela = media móvil de (high - low).

    MATEMÁTICA PURA del gráfico, SIN INDICADORES (migración ATR -> rango,
    Fase 1). Es la misma métrica que ict_backtest._util.avg_candle_range.
    """
    candle_range = (frame["high"] - frame["low"]).clip(lower=0.0)
    return candle_range.rolling(period).mean()


def detect_displacement(
    frame: pd.DataFrame,
    config: DisplacementConfig | None = None,
) -> pd.DataFrame:
    if config is None:
        config = DisplacementConfig()

    data = frame.copy()
    # Rango promedio de contexto (NO ATR). No se escribe en la columna "atr"
    # (contrato de volatilidad del sistema) para no pisarla.
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

    data["displacement_bullish"] = bullish_body & large_body & small_wick
    data["displacement_bearish"] = bearish_body & large_body & small_wick

    data["displacement_magnitude"] = np.where(
        data["displacement_bullish"] | data["displacement_bearish"],
        body / rng,
        0.0,
    )

    return data
