"""engine/liquidity_levels.py — Liquidez BSL/SSL anclada al sesgo HTF (Deuda 4).

Sin indicadores técnicos: SOLO geometría de mercado (high/low/close).
  BSL (Buy Side Liquidity) = máximos previos POR ENCIMA del precio actual.
  SSL (Sell Side Liquidity) = mínimos previos POR DEBAJO del precio actual.

El objetivo del día lo marca el sesgo HTF:
  BULLISH → objetivo BSL (barrer máximos arriba).
  BEARISH → objetivo SSL (barrer mínimos abajo).
  NEUTRAL → NONE.

Regla de oro: engine/ nunca importa ict_backtest/ ni usa ATR/EMA.

Volumen (MDS_VOLUMEN): en el SWEEP de BSL/SSL se ANOTA `sweep_volume_ratio`
(float o NaN). Es CONFIRMACION, nunca gate: no filtra ni cambia la geometria.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine._volume import volume_confirm

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _bias_direction(htf_bias) -> str:
    """Extrae la dirección del sesgo; acepta HtfBias o str."""
    if htf_bias is None:
        return NEUTRAL
    if isinstance(htf_bias, str):
        value = htf_bias
    else:
        value = getattr(htf_bias, "direction", NEUTRAL)
    value = (value or NEUTRAL).upper()
    return value if value in (BULLISH, BEARISH) else NEUTRAL


def detect_liquidity_htf(
    frame: pd.DataFrame,
    htf_bias,
    left: int = 3,
    margin_ticks: float = 0.0,
    volume_window: int | None = None,
) -> pd.DataFrame:
    """Marca niveles BSL/SSL relevantes por vela, sin look-ahead ni ATR.

    - bsl_level: máximo de las `left` velas previas si está por encima de
      close + margin_ticks; si no, NaN.
    - ssl_level: mínimo de las `left` velas previas si está por debajo de
      close - margin_ticks; si no, NaN.
    - target_liquidity: 'BSL' | 'SSL' | 'NONE' según el sesgo HTF.
    - sweep_volume_ratio: SOLO confirmación (float o NaN) en las velas que
      barren el BSL/SSL previo. NUNCA veta ni altera las columnas anteriores.
    """
    if left < 1:
        raise ValueError("left debe ser >= 1")
    for col in ("high", "low", "close"):
        if col not in frame.columns:
            raise KeyError(f"falta la columna requerida '{col}'")

    out = frame.copy()
    if out.empty:
        out["bsl_level"] = pd.Series(dtype="float64")
        out["ssl_level"] = pd.Series(dtype="float64")
        out["target_liquidity"] = pd.Series(dtype="object")
        out["sweep_volume_ratio"] = pd.Series(dtype="float64")
        return out

    close = out["close"].astype("float64")
    # shift(1): solo velas cerradas previas (sin look-ahead)
    prev_high = out["high"].astype("float64").rolling(left).max().shift(1)
    prev_low = out["low"].astype("float64").rolling(left).min().shift(1)

    margin = float(margin_ticks)
    bsl = prev_high.where(prev_high > close + margin, np.nan)
    ssl = prev_low.where(prev_low < close - margin, np.nan)

    direction = _bias_direction(htf_bias)
    target = {BULLISH: "BSL", BEARISH: "SSL"}.get(direction, "NONE")

    out["bsl_level"] = bsl
    out["ssl_level"] = ssl
    out["target_liquidity"] = target
    out["sweep_volume_ratio"] = _sweep_volume_ratio(
        out, bsl, ssl, 20 if volume_window is None else int(volume_window)
    )
    return out


def _sweep_volume_ratio(
    out: pd.DataFrame,
    bsl,
    ssl,
    window: int,
) -> pd.Series:
    """Ratio de volumen en las velas que BARREN el BSL/SSL previo (no gate).

    Todo NaN si no hay columna 'volume' (regresión cero).
    """
    ratios = pd.Series(np.nan, index=out.index, dtype="float64")
    if "volume" not in out.columns:
        return ratios
    high = out["high"].astype("float64").to_numpy()
    low = out["low"].astype("float64").to_numpy()
    bsl_prev = bsl.shift(1).to_numpy()
    ssl_prev = ssl.shift(1).to_numpy()
    for i in range(len(out)):
        swept_bsl = np.isfinite(bsl_prev[i]) and high[i] > bsl_prev[i]
        swept_ssl = np.isfinite(ssl_prev[i]) and low[i] < ssl_prev[i]
        if swept_bsl or swept_ssl:
            r = volume_confirm(out, i, window)
            if r is not None:
                ratios.iat[i] = float(r)
    return ratios


def nearest_liquidity_target(
    frame: pd.DataFrame,
    htf_bias,
    left: int = 3,
) -> dict:
    """Devuelve el objetivo de liquidez más cercano al último close.

    {'side': 'BSL'|'SSL'|'NONE', 'level': float|None, 'distance': float}
    """
    empty = {"side": "NONE", "level": None, "distance": float("nan")}
    if frame is None or len(frame) == 0:
        return empty

    marked = detect_liquidity_htf(frame, htf_bias, left=left)
    side = str(marked["target_liquidity"].iloc[-1])
    if side == "NONE":
        return empty

    col = "bsl_level" if side == "BSL" else "ssl_level"
    close = float(marked["close"].astype("float64").iloc[-1])

    # Nivel vigente: el último marcado; si no hay, el extremo previo más cercano
    series = marked[col].dropna()
    if series.empty:
        return {"side": side, "level": None, "distance": float("nan")}

    # de todos los niveles vistos, el más cercano al close en la dirección válida
    values = series.astype("float64").to_numpy()
    if side == "BSL":
        valid = values[values > close]
        level = float(valid.min()) if valid.size else float(values.max())
    else:
        valid = values[values < close]
        level = float(valid.max()) if valid.size else float(values.min())

    return {"side": side, "level": level, "distance": abs(level - close)}


__all__ = ["detect_liquidity_htf", "nearest_liquidity_target"]
