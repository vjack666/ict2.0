"""Clasificación causal de fase/rango Wyckoff.

La función usa solamente el frame que recibe; el adaptador le entrega el
prefijo cerrado. ATR, si existe, no se usa como sesgo: solo se usa el rango
OHLC mediano para separar proceso lateral de expansión.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .types import WyckoffPhase


def _direction_label(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "UNKNOWN"
    for column in ("trend", "macro_direction", "structure_bias"):
        if column in frame.columns:
            value = str(frame.iloc[-1].get(column, "UNKNOWN")).upper()
            if value in {"BULLISH", "BEARISH"}:
                return value
    delta = float(frame["close"].iloc[-1]) - float(frame["close"].iloc[0])
    span = float(frame["high"].max()) - float(frame["low"].min())
    if span <= 0 or abs(delta) < span * 0.08:
        return "UNKNOWN"
    return "BULLISH" if delta > 0 else "BEARISH"


def classify_phase(frame: pd.DataFrame, *, lookback: int = 40) -> WyckoffPhase:
    """Clasifica fase sin leer barras posteriores al frame recibido."""
    if frame is None or frame.empty or len(frame) < 10:
        return WyckoffPhase.UNKNOWN
    window = frame.tail(max(10, lookback))
    high = float(window["high"].max())
    low = float(window["low"].min())
    span = high - low
    if span <= 0:
        return WyckoffPhase.RANGE_UNCLASSIFIED
    candle_ranges = (window["high"] - window["low"]).astype(float)
    typical_range = float(candle_ranges.median())
    direction = _direction_label(window)
    # Rango lateral: la geometría sigue siendo observación, no una señal.
    if typical_range > 0 and span <= typical_range * 12:
        if direction == "BEARISH":
            return WyckoffPhase.ACCUMULATION
        if direction == "BULLISH":
            return WyckoffPhase.DISTRIBUTION
        return WyckoffPhase.RANGE_UNCLASSIFIED
    if direction == "BULLISH":
        return WyckoffPhase.MARKUP
    if direction == "BEARISH":
        return WyckoffPhase.MARKDOWN
    return WyckoffPhase.TRANSITION


def build_range_ref(frame: pd.DataFrame, *, tf: str, decision_time: Any, lookback: int = 40) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {"tf": tf, "available": False, "authority_tf": tf}
    window = frame.tail(max(10, lookback))
    high = float(window["high"].max())
    low = float(window["low"].min())
    asof = pd.to_datetime(window["time"], utc=True, errors="coerce").max() if "time" in window else decision_time
    return {
        "tf": tf,
        "available": True,
        "high": high,
        "low": low,
        "mid": (high + low) / 2.0,
        "bar_count": int(len(window)),
        "asof_time": asof.isoformat() if not pd.isna(asof) else None,
        "source_ref": f"WYCKOFF_RANGE_{tf}_{asof.isoformat() if not pd.isna(asof) else 'UNKNOWN'}",
    }


__all__ = ["build_range_ref", "classify_phase"]
