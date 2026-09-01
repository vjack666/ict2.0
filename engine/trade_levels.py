"""Decision-owned trade levels.

These helpers express where the market thesis is invalidated and which
liquidity level is the structural target. They do not execute or score trades.
"""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd


# Maximum structural stop width measured in average candle ranges.
STRUCT_SL_MAX_RANGE = 6.0
STRUCT_SL_BUFFER_RANGE = 0.3


def _tp_liquidity(row: pd.Series, direction: int,
                  df: pd.DataFrame | None = None) -> dict:
    """Return internal and external liquidity targets for a decision."""
    out: dict = {"internal": None, "external": None}

    try:
        if direction == 1:
            bsl = float(row.get("bsl_price"))
            if pd.notna(bsl) and bsl > float(row["close"]):
                out["internal"] = bsl
        else:
            ssl = float(row.get("ssl_price"))
            if pd.notna(ssl) and ssl < float(row["close"]):
                out["internal"] = ssl
    except (TypeError, ValueError, KeyError):
        pass

    if df is not None and len(df):
        try:
            tcol = "time" if "time" in df.columns else None
            row_ts = pd.to_datetime(row.get("time"), utc=True, errors="coerce")
            if pd.notna(row_ts):
                if tcol is not None:
                    df_ts = pd.to_datetime(df[tcol], utc=True, errors="coerce")
                else:
                    df_ts = pd.to_datetime(df.index, utc=True, errors="coerce")
                row_day = row_ts.tz_convert("UTC").normalize() if row_ts.tz else row_ts.normalize()
                prev_mask = df_ts.dt.normalize() < row_day
                if prev_mask.any():
                    prev = df[prev_mask]
                    if direction == 1:
                        out["external"] = float(prev["high"].max())
                    else:
                        out["external"] = float(prev["low"].min())
        except (TypeError, ValueError, KeyError):
            pass

    return out


def calc_structural_sl(row: pd.Series, direction: int,
                       rng: float) -> float | None:
    """Calculate the structural invalidation level for a trade decision."""
    buf = STRUCT_SL_BUFFER_RANGE * rng

    def _lvl(col: str) -> float | None:
        v = row.get(col, np.nan)
        fv = cast(float, v)
        if pd.isna(fv) or fv <= 0:
            return None
        return float(fv)

    if direction == 1:
        sweep = _lvl("sweep_low")
        if sweep is not None:
            return sweep - buf
        swing = _lvl("swing_low")
        if swing is not None:
            return swing - buf
    else:
        sweep = _lvl("sweep_high")
        if sweep is not None:
            return sweep + buf
        swing = _lvl("swing_high")
        if swing is not None:
            return swing + buf
    return None


__all__ = [
    "STRUCT_SL_BUFFER_RANGE",
    "STRUCT_SL_MAX_RANGE",
    "_tp_liquidity",
    "calc_structural_sl",
]

