from __future__ import annotations

import numpy as np
import pandas as pd


def detect_fvg(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().reset_index(drop=True)
    data["fvg_bullish"] = False
    data["fvg_bearish"] = False

    if len(data) < 3:
        return data

    prev2_high = data["high"].shift(2)
    prev2_low = data["low"].shift(2)

    data["fvg_bullish"] = data["low"] > prev2_high
    data["fvg_bearish"] = data["high"] < prev2_low

    data["fvg_size"] = np.where(
        data["fvg_bullish"],
        (data["low"] - prev2_high).clip(lower=0),
        np.where(
            data["fvg_bearish"],
            (prev2_low - data["high"]).clip(lower=0),
            0.0,
        ),
    )

    data["fvg_mid"] = pd.NA
    bullish_mid = (data["low"] + prev2_high) / 2.0
    bearish_mid = (data["high"] + prev2_low) / 2.0
    data.loc[data["fvg_bullish"], "fvg_mid"] = bullish_mid[data["fvg_bullish"]]
    data.loc[data["fvg_bearish"], "fvg_mid"] = bearish_mid[data["fvg_bearish"]]

    data["fvg_fill_status"] = _track_fvg_fill(data)

    # --- Fase B1 (SPEC §3/§4): etiquetas de tipo y jerarquía (metadatos) ---
    # FVG es tier T2 por defecto (libro 21 §2). El cruce con OB (BPR -> T1)
    # se resuelve en data_feed tras tener ambos detectores. Aquí solo etiquetamos.
    data["pd_type"] = np.where(
        data["fvg_bullish"] | data["fvg_bearish"], "FVG", "NONE"
    )
    data["pd_tier"] = np.where(
        data["fvg_bullish"] | data["fvg_bearish"], "T2", "NONE"
    )
    return data


def _track_fvg_fill(data: pd.DataFrame) -> pd.Series:
    n = len(data)
    # Use a plain list to avoid pandas 3.x Arrow string array assignment issues
    status_list: list[str] = ["none"] * n
    active_bull_top: float | None = None
    active_bull_bot: float | None = None
    active_bear_top: float | None = None
    active_bear_bot: float | None = None
    bull_unfilled = False
    bear_unfilled = False

    for i in range(2, n):
        row = data.iloc[i]
        prev2_high = data.iloc[i - 2]["high"]
        prev2_low = data.iloc[i - 2]["low"]

        if row["fvg_bullish"]:
            active_bull_top = float(prev2_high)
            active_bull_bot = float(row["low"])
            bull_unfilled = True

        if row["fvg_bearish"]:
            active_bear_top = float(row["high"])
            active_bear_bot = float(prev2_low)
            bear_unfilled = True

        if bull_unfilled and active_bull_top is not None and float(row["low"]) <= active_bull_top:
            bull_unfilled = False

        if bear_unfilled and active_bear_bot is not None and float(row["high"]) >= active_bear_bot:
            bear_unfilled = False

        if bull_unfilled:
            status_list[i] = "bullish_unfilled"
        elif bear_unfilled:
            status_list[i] = "bearish_unfilled"
        elif row["fvg_bullish"] or row["fvg_bearish"]:
            status_list[i] = "just_created"
        else:
            status_list[i] = "none"

    return pd.Series(status_list, index=data.index, name="fvg_fill_status")
