"""engine/dealing_range.py — Dealing Range / Premium-Discount anclado al HTF.

Salda la "Deuda 1" de la lectura HTF: tras definir el sesgo (engine/bias),
el trader mide DÓNDE está el precio dentro del rango vigente (dealing range)
para operar sólo en la mitad correcta (descuento si alcista, premium si bajista).

Contrato:
  ENT: velas cerradas (high/low/close) + HtfBias.
  SAL: zona premium/discount/OTE por vela y resumen del estado actual.
  CRIT: geometría pura (rolling max/min de high/low). SIN indicadores
        (no ATR, no medias). El motor no importa ict_backtest/ ni detectors/.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"

# Retrocesos OTE clásicos (Fibonacci geométrico sobre el rango, no indicador).
OTE_MIN_RETRACE = 0.62
OTE_MAX_RETRACE = 0.79

_EPS = 1e-9


@dataclass(frozen=True)
class DealingRangeConfig:
    """Parámetros del dealing range (AMBIG de ingeniería)."""

    lookback: int = 10
    ote_min_retrace: float = OTE_MIN_RETRACE
    ote_max_retrace: float = OTE_MAX_RETRACE


def compute_dealing_range(
    frame: pd.DataFrame,
    lookback: int = 10,
    config: DealingRangeConfig | None = None,
) -> pd.DataFrame:
    """Marca cada vela con su zona dentro del dealing range vigente.

    Columnas añadidas: range_high, range_low, zone_mid, ote_long_min/max,
    ote_short_min/max, premium_discount_zone, premium_distance.
    """
    if config is None:
        config = DealingRangeConfig(lookback=lookback)

    data = frame.copy()

    # Rango vigente: máximo/mínimo rodante (geometría pura, sin look-ahead).
    range_high = data["high"].rolling(config.lookback, min_periods=1).max()
    range_low = data["low"].rolling(config.lookback, min_periods=1).min()
    span = range_high - range_low

    data["range_high"] = range_high
    data["range_low"] = range_low
    # Alias compatibles con detectors/zones.py
    data["zone_high"] = range_high
    data["zone_low"] = range_low
    data["zone_mid"] = (range_high + range_low) / 2.0

    data["ote_long_min"] = range_low + config.ote_min_retrace * span
    data["ote_long_max"] = range_low + config.ote_max_retrace * span
    data["ote_short_min"] = range_high - config.ote_max_retrace * span
    data["ote_short_max"] = range_high - config.ote_min_retrace * span

    close = data["close"]
    zone_mid = data["zone_mid"]

    is_discount = close < zone_mid
    is_premium = close >= zone_mid
    # OTE_LONG se busca en descuento; OTE_SHORT en premium.
    in_ote_long = (close >= data["ote_short_min"]) & (close <= data["ote_short_max"])
    in_ote_short = (close >= data["ote_long_min"]) & (close <= data["ote_long_max"])

    data["premium_discount_zone"] = np.select(
        [
            in_ote_long & is_discount,
            in_ote_short & is_premium,
            is_discount,
            is_premium,
        ],
        ["OTE_LONG", "OTE_SHORT", "DISCOUNT", "PREMIUM"],
        default="OTE_NONE",
    )

    # Distancia normalizada al mid: + hacia premium, - hacia descuento.
    data["premium_distance"] = np.where(
        is_premium,
        (close - zone_mid) / (data["zone_high"] - zone_mid + _EPS),
        -(zone_mid - close) / (zone_mid - data["zone_low"] + _EPS),
    )

    return data


def _is_favorable(zone: str, direction: str) -> bool:
    """Sólo se opera en la mitad del rango que acompaña al sesgo HTF."""
    if direction == BULLISH:
        return zone in ("DISCOUNT", "OTE_LONG")
    if direction == BEARISH:
        return zone in ("PREMIUM", "OTE_SHORT")
    return False


def dealing_range_htf(
    frame: pd.DataFrame,
    htf_bias,
    lookback: int = 10,
) -> dict:
    """Estado actual del precio respecto al dealing range, filtrado por sesgo HTF."""
    if frame is None or len(frame) == 0:
        return {
            "zone": "OTE_NONE",
            "distance": 0.0,
            "bias": getattr(htf_bias, "direction", NEUTRAL),
            "is_favorable": False,
        }

    marked = compute_dealing_range(frame, lookback=lookback)
    last = marked.iloc[-1]

    zone = str(last["premium_discount_zone"])
    distance = float(last["premium_distance"])
    direction = getattr(htf_bias, "direction", NEUTRAL) or NEUTRAL

    return {
        "zone": zone,
        "distance": distance,
        "bias": direction,
        "is_favorable": _is_favorable(zone, direction),
    }
