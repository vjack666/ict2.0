#!/usr/bin/env python3
"""Detector de displacement institucional para M15.

Detecta displacement como una barra con:
- Cuerpo grande (>= 60% del rango total)
- Ruptura clara de estructura previa (rompe mínimo 2 velas atrás)
- Dirección clara (bullish o bearish)
- Wicks reduzcidos (confirmando empuje institucional, no noise)

Esto es un proxy simplificado del displacement institucional descrito en la tesis ICT.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class DisplacementConfig:
    """Configuración para detección de displacement."""

    def __init__(
        self,
        min_body_to_range_ratio: float = 0.50,
        lookback_bars: int = 2,
        min_body_pips: float = 1.5,
    ) -> None:
        self.min_body_to_range_ratio = min_body_to_range_ratio
        self.lookback_bars = lookback_bars
        self.min_body_pips = min_body_pips


def detect_displacement(frame: pd.DataFrame, cfg: DisplacementConfig | None = None) -> pd.DataFrame:
    """Detectar displacement institucional en un DataFrame de velas M15.

    Args:
        frame: DataFrame con columnas time, open, high, low, close
        cfg: Configuración de detección

    Returns:
        DataFrame con una fila por displacement detectado, con columnas:
            - time: timestamp de la barra de displacement
            - displacement_bullish: bool
            - displacement_bearish: bool
            - body: tamaño del cuerpo
            - range: rango total de la barra
            - body_to_range_ratio: proporción cuerpo/rango
            - broke_high: alto que rompió
            - broke_low: bajo que rompió
    """
    if cfg is None:
        cfg = DisplacementConfig()

    if frame.empty or len(frame) < cfg.lookback_bars + 1:
        return pd.DataFrame()

    df = frame.copy()
    df["body"] = abs(df["close"] - df["open"])
    df["range"] = df["high"] - df["low"]
    df["body_to_range_ratio"] = df["body"] / df["range"].replace(0, pd.NA)

    results: list[dict[str, Any]] = []

    for i in range(cfg.lookback_bars, len(df)):
        row = df.iloc[i]
        prev_high = df.iloc[i - cfg.lookback_bars : i]["high"].max()
        prev_low = df.iloc[i - cfg.lookback_bars : i]["low"].min()

        body = row["body"]
        bar_range = row["range"]
        ratio = row["body_to_range_ratio"]

        if pd.isna(ratio) or ratio < cfg.min_body_to_range_ratio:
            continue

        if body < cfg.min_body_pips * 0.0001:
            continue

        is_bullish = row["close"] > prev_high and row["close"] > row["open"]
        is_bearish = row["close"] < prev_low and row["close"] < row["open"]

        if is_bullish or is_bearish:
            results.append(
                {
                    "time": row["time"],
                    "displacement_bullish": is_bullish,
                    "displacement_bearish": is_bearish,
                    "body": float(body),
                    "range": float(bar_range),
                    "body_to_range_ratio": float(ratio),
                    "broke_high": float(prev_high) if is_bullish else None,
                    "broke_low": float(prev_low) if is_bearish else None,
                }
            )

    return pd.DataFrame(results)
