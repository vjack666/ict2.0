"""Premium/Discount EQ50%. SIN indicadores, SIN OTE/Fibonacci (ICT_RULEBOOK §9)."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
BULLISH, BEARISH, NEUTRAL = "BULLISH", "BEARISH", "NEUTRAL"
_EQ_BAND, _EPS = 0.12, 1e-9
@dataclass(frozen=True)
class DealingRangeConfig:
    lookback: int = 10
    eq_band: float = _EQ_BAND
def compute_dealing_range(frame, lookback=10, config=None):
    if config is None:
        config = DealingRangeConfig(lookback=lookback)
    data = frame.copy()
    rh = data["high"].rolling(config.lookback, min_periods=1).max()
    rl = data["low"].rolling(config.lookback, min_periods=1).min()
    span = (rh - rl).clip(lower=_EPS)
    data["range_high"] = rh
    data["range_low"] = rl
    data["zone_high"] = rh
    data["zone_low"] = rl
    data["zone_mid"] = (rh + rl) / 2.0
    c, m = data["close"], data["zone_mid"]
    band = span * float(config.eq_band)
    in_eq = (c - m).abs() <= band
    data["premium_discount_zone"] = np.select(
        [in_eq, (~in_eq) & (c < m), (~in_eq) & (c >= m)],
        ["EQ", "DISCOUNT", "PREMIUM"],
        default="EQ",
    )
    data["premium_distance"] = np.where(
        c >= m,
        (c - m) / (data["zone_high"] - m + _EPS),
        -(m - c) / (m - data["zone_low"] + _EPS),
    )
    return data
def _is_favorable(zone, direction):
    return (direction == BULLISH and zone == "DISCOUNT") or (direction == BEARISH and zone == "PREMIUM")
def dealing_range_htf(frame, htf_bias, lookback=10):
    if frame is None or len(frame) == 0:
        return {"zone": "EQ", "distance": 0.0, "bias": getattr(htf_bias, "direction", NEUTRAL), "is_favorable": False}
    last = compute_dealing_range(frame, lookback=lookback).iloc[-1]
    z = str(last["premium_discount_zone"])
    d = getattr(htf_bias, "direction", NEUTRAL) or NEUTRAL
    return {"zone": z, "distance": float(last["premium_distance"]), "bias": d, "is_favorable": _is_favorable(z, d)}
