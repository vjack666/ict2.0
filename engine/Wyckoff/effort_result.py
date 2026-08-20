"""Evidencia relativa de esfuerzo/resultado Wyckoff."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .types import VolumeMode


def measure_effort_result(frame: pd.DataFrame, *, lookback: int = 20) -> tuple[dict[str, Any], VolumeMode]:
    if frame is None or frame.empty or "tick_volume" not in frame.columns:
        return {"available": False, "reason": "tick_volume_unavailable"}, VolumeMode.UNAVAILABLE
    window = frame.tail(max(5, lookback))
    volumes = pd.to_numeric(window["tick_volume"], errors="coerce").dropna()
    if len(volumes) < 3:
        return {"available": False, "reason": "insufficient_tick_volume"}, VolumeMode.UNAVAILABLE
    ranges = (window["high"].astype(float) - window["low"].astype(float)).tail(len(volumes))
    baseline_volume = float(volumes.iloc[:-3].mean()) if len(volumes) > 3 else float(volumes.mean())
    baseline_range = float(ranges.iloc[:-3].mean()) if len(ranges) > 3 else float(ranges.mean())
    recent_volume = float(volumes.iloc[-3:].mean())
    recent_range = float(ranges.iloc[-3:].mean())
    volume_ratio = recent_volume / baseline_volume if baseline_volume > 0 else 1.0
    range_ratio = recent_range / baseline_range if baseline_range > 0 else 1.0
    divergence = bool(volume_ratio > 1.5 and range_ratio < 0.8)
    return {
        "available": True,
        "volume_ratio": round(volume_ratio, 6),
        "range_ratio": round(range_ratio, 6),
        "divergence": divergence,
        "interpretation": "effort_without_result" if divergence else "normal",
        "source_ref": f"WYCKOFF_EFFORT_{str(window['time'].iloc[-1]) if 'time' in window else 'UNKNOWN'}",
    }, VolumeMode.RELATIVE_ONLY


__all__ = ["measure_effort_result"]
