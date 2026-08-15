"""detectors/liquidity_context.py — Fuente UNICA de liquidez y sweep (R3, libro 05).

Cierra el hueco de arquitectura "liquidez pinta != sweep filtra": antes habia
CUATRO definiciones de "sweep" dispersas (detectors/bos.py, signals/pipeline.py,
adapters/feature_enrichment_adapter.py, y los clusters de detectors/liquidity.py
para el mapa). El libro 05 (#3, #5) exige UNA definicion canonica de sweep
compartida por mapa, pipeline y backtest.

Definicion canonica (libro 05 §0 #3):
    sweep valido = rompe el nivel de liquidez Y cierra de vuelta adentro en la
    misma vela (sin look-ahead; niveles con .shift(1)).

    sweep_down = (low < prior_low(lookback))  & (close > prior_low)
    sweep_up   = (high > prior_high(lookback)) & (close < prior_high)

Los distintos timeframes usan distinto `lookback` (horizonte), pero la LOGICA es
una sola. Eso es legitimo en ICT; lo que no lo era eran definiciones con logica
distinta (rolling-max de 5 vs prior-extreme de 20 vs clusters). Ahora todos
llaman a canonical_sweep().

build_liquidity_context() reune en UN modulo tanto las zonas BSL/SSL para el
mapa (reusa detectors.liquidity.detect_liquidity) como el sweep canonico para la
senal, para que el mapa y la senal lean de la misma fuente.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# Lookback por defecto coherente con BosConfig.liquidity_lookback (backtest).
DEFAULT_SWEEP_LOOKBACK: int = 20


def canonical_sweep(
    df: pd.DataFrame, lookback: int = DEFAULT_SWEEP_LOOKBACK, min_periods: int | None = None
) -> pd.DataFrame:
    """Sweep de liquidez canonico (libro 05 §0 #3). Rompe y cierra adentro.

    Definicion unica compartida por backtest (detectors/bos.py) y pipeline
    (signals/pipeline.py). El parametro `lookback` es el horizonte del nivel
    previo (prior_high/prior_low); `min_periods` conserva elcomportamiento de
    cada llamador (backtest usa None, pipeline usaba 2). La LOGICA es una sola;
    lo unico que cambia es el horizonte y la ventana minima, no la regla.

    Devuelve df con columnas:
        liquidity_sweep_down, liquidity_sweep_up  (bool, sin look-ahead)
    """
    out = df.copy()
    prior_low = out["low"].rolling(lookback, min_periods=min_periods).min().shift(1)
    prior_high = out["high"].rolling(lookback, min_periods=min_periods).max().shift(1)
    out["liquidity_sweep_down"] = (out["low"] < prior_low) & (out["close"] > prior_low)
    out["liquidity_sweep_up"] = (out["high"] > prior_high) & (out["close"] < prior_high)
    return out


def build_liquidity_context(
    df: pd.DataFrame,
    sweep_lookback: int = DEFAULT_SWEEP_LOOKBACK,
    margin: float = 4.0,
    atr_period: int = 10,
    min_count: int = 3,
    visible: int = 2,
) -> pd.DataFrame:
    """Fuente unica de contexto de liquidez para mapa + senal.

    - sweep canonico (senal/backtest)
    - zonas BSL/SSL para pintar en el mapa (detectors.liquidity.detect_liquidity)

    Devuelve df con: liquidity_sweep_up/down + bsl_*/ssl_* (zonas visuales).
    """
    from detectors.liquidity import detect_liquidity

    out = canonical_sweep(df, lookback=sweep_lookback)
    zones = detect_liquidity(
        df, margin=margin, atr_period=atr_period, min_count=min_count, visible=visible
    )
    for col in ("bsl_price", "bsl_top", "bsl_bot", "ssl_price", "ssl_top", "ssl_bot"):
        if col in zones.columns:
            out[col] = zones[col]
    return out
