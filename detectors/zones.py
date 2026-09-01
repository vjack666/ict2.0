from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ZoneConfig:
    swing_lookback: int = 10
    ote_min_retrace: float = 0.62
    ote_max_retrace: float = 0.79


def _swing_range(data: pd.DataFrame, lookback: int) -> pd.DataFrame:
    rolling_high = data["high"].rolling(lookback, min_periods=1)
    rolling_low = data["low"].rolling(lookback, min_periods=1)
    result = pd.DataFrame(index=data.index)
    result["range_high"] = rolling_high.max()
    result["range_low"] = rolling_low.min()
    return result


def compute_zones(frame: pd.DataFrame, config: ZoneConfig | None = None) -> pd.DataFrame:
    if config is None:
        config = ZoneConfig()

    data = frame.copy()
    ranges = _swing_range(data, config.swing_lookback)

    data["zone_high"] = ranges["range_high"]
    data["zone_low"] = ranges["range_low"]
    data["zone_mid"] = (ranges["range_high"] + ranges["range_low"]) / 2.0
    data["ote_long_min"] = ranges["range_low"] + config.ote_min_retrace * (ranges["range_high"] - ranges["range_low"])
    data["ote_long_max"] = ranges["range_low"] + config.ote_max_retrace * (ranges["range_high"] - ranges["range_low"])
    data["ote_short_min"] = ranges["range_high"] - config.ote_max_retrace * (ranges["range_high"] - ranges["range_low"])
    data["ote_short_max"] = ranges["range_high"] - config.ote_min_retrace * (ranges["range_high"] - ranges["range_low"])

    close = data["close"]
    condition_long_ote = (close >= data["ote_long_min"]) & (close <= data["ote_long_max"])
    condition_short_ote = (close >= data["ote_short_min"]) & (close <= data["ote_short_max"])
    condition_discount = close < data["zone_mid"]
    condition_premium = close >= data["zone_mid"]

    data["premium_discount_zone"] = np.select(
        [
            condition_long_ote & condition_discount,
            condition_short_ote & condition_premium,
            condition_discount,
            condition_premium,
        ],
        ["OTE_LONG", "OTE_SHORT", "DISCOUNT", "PREMIUM"],
        default="OTE_NONE",
    )

    data["premium_distance"] = np.where(
        close >= data["zone_mid"],
        (close - data["zone_mid"]) / (data["zone_high"] - data["zone_mid"] + 1e-9),
        -(data["zone_mid"] - close) / (data["zone_mid"] - data["zone_low"] + 1e-9),
    )

    return data
