"""Nearest opposite swing liquidity for TP (thesis v30 — not ATR cluster mid)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def nearest_swing_tp(
    frame: pd.DataFrame,
    entry_at: int,
    direction: int,
    entry: float,
    *,
    lookback: int = 80,
) -> float | None:
    """First swing high above entry (long) or swing low below entry (short).

    Uses confirmed pivot (3 bars left/right) with pivot index < entry_at
    and still relevant (price beyond entry in trade direction).
    """
    if entry_at < 5 or entry_at >= len(frame):
        return None
    lo = max(0, entry_at - lookback)
    hi = entry_at  # exclusive: only past pivots
    high = frame["high"].to_numpy()
    low = frame["low"].to_numpy()
    left = 3
    candidates: list[float] = []
    for i in range(lo + left, hi - left):
        # Strict pivot: center strictly dominates neighbors (avoids plateaus).
        left_h = high[i - left : i]
        right_h = high[i + 1 : i + left + 1]
        left_l = low[i - left : i]
        right_l = low[i + 1 : i + left + 1]
        if direction > 0:
            if (
                high[i] > entry
                and high[i] > left_h.max()
                and high[i] > right_h.max()
            ):
                candidates.append(float(high[i]))
        else:
            if (
                low[i] < entry
                and low[i] < left_l.min()
                and low[i] < right_l.min()
            ):
                candidates.append(float(low[i]))
    if not candidates:
        return None
    # nearest = minimal distance beyond entry
    if direction > 0:
        return min(candidates)
    return max(candidates)  # short: nearest below = highest among those below entry


def apply_nearest_tp_to_signals(
    signals: list,
    frame: pd.DataFrame,
    *,
    min_rr: float = 3.0,
) -> list:
    """Rebuild take_profit on ICTSignal-like objects using nearest swing; drop if RR < min_rr."""
    out = []
    for s in signals:
        entry_at = getattr(s, "entry_at", None)
        if entry_at is None:
            out.append(s)
            continue
        entry = float(s.entry)
        sl = float(s.stop_loss)
        direction = int(s.direction)
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp_near = nearest_swing_tp(frame, int(entry_at), direction, entry)
        if tp_near is None:
            # fallback keep existing tp if RR ok
            tp = float(s.take_profit)
        else:
            tp = tp_near
        reward = abs(tp - entry)
        if reward / risk < min_rr - 1e-9:
            # force min RR level if nearest is too close
            if direction > 0:
                tp = entry + min_rr * risk
            else:
                tp = entry - min_rr * risk
        # mutate copy fields
        s.take_profit = tp
        out.append(s)
    return out
