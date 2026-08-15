"""SMT Divergence detector (libro 24 / R3.5).

SMT Divergence = two correlated instruments (e.g. EURUSD vs GBPUSD) diverge
at swing points: one makes a higher high while the other makes a lower high
(or vice versa). The "lie" reveals institutional manipulation — the move that
breaks structure on one pair but NOT on its correlate is the trap.

CONTRACT (metadata only, no entry filtering — BONUS role):
  - smt_divergence(base_df, corr_df, lookback=40) -> dict with:
        divergence      : bool
        direction       : 'LONG' | 'SHORT' | None
        strength        : float (0..1)
        base_swing_high : float | None
        base_swing_low  : float | None
        corr_swing_high : float | None
        corr_swing_low  : float | None
  - flag_smt_divergence(signals, frames, ltf, corr_symbol, lookback=40)
        annotates ICTSignal with smt_divergence_active/direction/strength

Uses ONLY OHLC data (no indicators). Anti-lookahead: compares closed bars.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def _swing_highs(highs: np.ndarray, lookback: int) -> list[tuple[int, float]]:
    """Return list of (index, price) for local swing highs.
    A bar is a swing high if its high >= all highs in [i-lookback, i+lookback].
    Uses left-only window (no lookahead): only confirmed bars count.
    """
    swings: list[tuple[int, float]] = []
    n = len(highs)
    for i in range(lookback, n):
        window = highs[max(0, i - lookback): i + 1]
        if highs[i] == np.max(window) and not np.isnan(highs[i]):
            # Avoid consecutive duplicates (flat tops)
            if not swings or abs(swings[-1][1] - highs[i]) > 1e-12:
                swings.append((i, float(highs[i])))
    return swings


def _swing_lows(lows: np.ndarray, lookback: int) -> list[tuple[int, float]]:
    """Return list of (index, price) for local swing lows (left-only window)."""
    swings: list[tuple[int, float]] = []
    n = len(lows)
    for i in range(lookback, n):
        window = lows[max(0, i - lookback): i + 1]
        if lows[i] == np.min(window) and not np.isnan(lows[i]):
            if not swings or abs(swings[-1][1] - lows[i]) > 1e-12:
                swings.append((i, float(lows[i])))
    return swings


def _normalize(closes: np.ndarray) -> np.ndarray:
    """Normalize closes to [0, 1] range for cross-instrument comparison."""
    cmin = np.nanmin(closes)
    cmax = np.nanmax(closes)
    if cmax - cmin < 1e-12:
        return np.full_like(closes, 0.5, dtype=float)
    return (closes - cmin) / (cmax - cmin)


# ---------------------------------------------------------------------------
# Core divergence detection
# ---------------------------------------------------------------------------
def smt_divergence(
    base_df: pd.DataFrame,
    corr_df: pd.DataFrame,
    lookback: int = 40,
) -> dict:
    """Detect SMT divergence between two correlated instruments at the SAME TF.

    Compares the last 2 swing highs and last 2 swing lows of each instrument
    (normalized to [0,1] for cross-instrument comparison).

    Returns:
        divergence: True if instruments disagree on direction
        direction: 'LONG' if base makes lower low but correlate doesn't
                   (trap was bearish → real direction is LONG),
                   'SHORT' if base makes higher high but correlate doesn't
                   (trap was bullish → real direction is SHORT)
        strength: 0..1 based on magnitude of divergence
    """
    if base_df is None or corr_df is None or len(base_df) < lookback + 2 or len(corr_df) < lookback + 2:
        return {
            "divergence": False, "direction": None, "strength": 0.0,
            "base_swing_high": None, "base_swing_low": None,
            "corr_swing_high": None, "corr_swing_low": None,
        }

    base_h = base_df["high"].to_numpy(dtype=float)
    base_l = base_df["low"].to_numpy(dtype=float)
    corr_h = corr_df["high"].to_numpy(dtype=float)
    corr_l = corr_df["low"].to_numpy(dtype=float)

    bsh = _swing_highs(base_h, lookback)
    bsl = _swing_lows(base_l, lookback)
    csh = _swing_highs(corr_h, lookback)
    csl = _swing_lows(corr_l, lookback)

    # Need at least 2 swing points in each to compare direction
    if len(bsh) < 2 or len(bsl) < 2 or len(csh) < 2 or len(csl) < 2:
        return {
            "divergence": False, "direction": None, "strength": 0.0,
            "base_swing_high": bsh[-1][1] if bsh else None,
            "base_swing_low": bsl[-1][1] if bsl else None,
            "corr_swing_high": csh[-1][1] if csh else None,
            "corr_swing_low": csl[-1][1] if csl else None,
        }

    # Normalize each instrument independently for comparison
    all_highs = np.concatenate([base_h, corr_h])
    all_lows = np.concatenate([base_l, corr_l])
    hmin, hmax = float(np.nanmin(all_highs)), float(np.nanmax(all_highs))
    lmin, lmax = float(np.nanmin(all_lows)), float(np.nanmax(all_lows))
    hrange = hmax - hmin if hmax - hmin > 1e-12 else 1.0
    lrange = lmax - lmin if lmax - lmin > 1e-12 else 1.0

    # Compare last 2 swings: higher high or lower low?
    base_hh = bsh[-1][1] > bsh[-2][1]  # base made higher high
    corr_hh = csh[-1][1] > csh[-2][1]  # correlate made higher high
    base_ll = bsl[-1][1] < bsl[-2][1]  # base made lower low
    corr_ll = csl[-1][1] < csl[-2][1]  # correlate made lower low

    divergence = False
    direction = None
    strength = 0.0

    # SHORT divergence: base makes higher high but correlate doesn't
    # → the rally in base is the "lie" → real direction SHORT
    if base_hh and not corr_hh:
        divergence = True
        direction = "SHORT"
        # Strength from magnitude of HH difference (normalized)
        hh_diff = abs(bsh[-1][1] - bsh[-2][1]) / hrange
        strength = float(np.clip(hh_diff * 2.0, 0.0, 1.0))

    # LONG divergence: base makes lower low but correlate doesn't
    # → the sell-off in base is the "lie" → real direction LONG
    elif base_ll and not corr_ll:
        divergence = True
        direction = "LONG"
        ll_diff = abs(bsl[-1][1] - bsl[-2][1]) / lrange
        strength = float(np.clip(ll_diff * 2.0, 0.0, 1.0))

    return {
        "divergence": divergence,
        "direction": direction,
        "strength": strength,
        "base_swing_high": bsh[-1][1],
        "base_swing_low": bsl[-1][1],
        "corr_swing_high": csh[-1][1],
        "corr_swing_low": csl[-1][1],
    }


# ---------------------------------------------------------------------------
# Wiring: annotate ICTSignal with SMT metadata (no entry filtering)
# ---------------------------------------------------------------------------
def flag_smt_divergence(
    signals: list,
    frames: dict[str, pd.DataFrame],
    ltf: str = "M15",
    corr_symbol: str = "GBPUSD",
    lookback: int = 40,
) -> None:
    """Annotate each signal with smt_divergence_active/direction/strength.

    Reads the correlate dataframe from frames[ltf] (must already be loaded
    for corr_symbol). Compares at the same TF as the base instrument.

    No-op if corr_symbol data is not in frames.
    """
    corr_key = f"{corr_symbol}_{ltf}"
    # Try both "GBPUSD_M15" and just the df keyed by corr_symbol
    corr_df = frames.get(corr_key)
    if corr_df is None:
        corr_df = frames.get(corr_symbol)

    if corr_df is None or not signals:
        return

    base_symbol = None
    # Infer base symbol from first signal or from frames keys
    for key in frames:
        if key.endswith(f"_{ltf}") and key != corr_key:
            base_symbol = key.replace(f"_{ltf}", "")
            break

    if base_symbol is None:
        return

    base_key = f"{base_symbol}_{ltf}"
    base_df = frames.get(base_key)
    if base_df is None:
        return

    for sig in signals:
        entry_idx = getattr(sig, "entry_at", None)
        if entry_idx is None:
            continue

        # Window: lookback bars before entry (no lookahead)
        start = max(0, entry_idx - lookback)
        end = entry_idx + 1

        if end > len(base_df) or end > len(corr_df):
            continue

        window_base = base_df.iloc[start:end].copy()
        window_corr = corr_df.iloc[start:end].copy()

        result = smt_divergence(window_base, window_corr, lookback=min(lookback, len(window_base) - 2))

        # Annotate signal (ICTSignal has these fields declared in engine.py)
        if hasattr(sig, "smt_divergence_active"):
            sig.smt_divergence_active = result["divergence"]
        if hasattr(sig, "smt_divergence_direction"):
            sig.smt_divergence_direction = result["direction"]
        if hasattr(sig, "smt_divergence_strength"):
            sig.smt_divergence_strength = result["strength"]
