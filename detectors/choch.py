from __future__ import annotations

import pandas as pd


CHOCH_BULLISH = "CHOCH_BULLISH"
CHOCH_BEARISH = "CHOCH_BEARISH"


def detect_choch(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["choch_signal"] = "NONE"

    data["last_swing_high"] = data["high"].rolling(20, min_periods=5).max().shift(1)
    data["last_swing_low"] = data["low"].rolling(20, min_periods=5).min().shift(1)

    bearish_context = data["close"].rolling(20).mean() < data["close"].rolling(50).mean()
    bullish_context = data["close"].rolling(20).mean() > data["close"].rolling(50).mean()

    bullish_break = data["close"] > data["last_swing_high"]
    bearish_break = data["close"] < data["last_swing_low"]

    data.loc[bearish_context & bullish_break, "choch_signal"] = CHOCH_BULLISH
    data.loc[bullish_context & bearish_break, "choch_signal"] = CHOCH_BEARISH
    return data
