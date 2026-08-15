from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class AlignConfig:
    """Calibración de alineación TF para FVG authority.

    lead/lag asimétricos (soft match):
      - H1: lead=2h, lag=1h
      - H4: lead=8h, lag=4h
      - D1: lead=2D, lag=1D
    """

    h1_lead: int = 2
    h1_lag: int = 1
    h4_lead: int = 8
    h4_lag: int = 4
    d1_lead: int = 2
    d1_lag: int = 1

    def window(self, tf: str) -> tuple[int, int]:
        key = str(tf).upper()
        if key == "H1":
            return self.h1_lead, self.h1_lag
        if key == "H4":
            return self.h4_lead, self.h4_lag
        if key == "D1":
            return self.d1_lead, self.d1_lag
        return 0, 0


@dataclass
class FvgAuthorityResult:
    tier: str = "NONE"  # S1|S2|S3|NONE
    supreme: bool = False
    narrative_ok: bool = False
    side_ok: bool = False
    displacement_ok: bool = False
    bpr_overlap: bool = False
    depth: float = 0.0
    reason: str = ""
    # P2: calidad extra, no gate
    dealing_side_ok: bool = False
    stack_ok: bool = False
    stack_count: int = 0


def _overlap_depth(fvg_lo: float, fvg_hi: float, ob_lo: float, ob_hi: float) -> tuple[bool, float]:
    if not (fvg_lo < fvg_hi and ob_lo < ob_hi):
        return False, 0.0
    lo = max(fvg_lo, ob_lo)
    hi = min(fvg_hi, ob_hi)
    if lo < hi:
        return True, (hi - lo) / (fvg_hi - fvg_lo)
    return False, 0.0


def _displacement_ok(frame, i: int, direction: int, lookback: int = 20, ratio_min: float = 1.5) -> bool:
    if i <= 0 or i >= len(frame):
        return False
    high = float(frame.loc[i, "high"])
    low = float(frame.loc[i, "low"])
    rng = high - low
    if rng <= 0:
        return False
    start = max(0, i - lookback)
    ranges = (frame.loc[start:i, "high"] - frame.loc[start:i, "low"]).clip(lower=1e-9)
    avg = float(ranges.mean())
    if avg <= 0:
        return False
    return (rng / avg) >= ratio_min


def _structure_aligned(frame, i: int, direction: int, lookback: int = 30) -> bool:
    if i <= 0 or i >= len(frame):
        return False
    start = max(0, i - lookback)
    sub = frame.loc[start:i]
    if direction == 1:
        return bool((sub.get("bos_dir", 0) == 1).any() or (sub.get("choch_dir", 0) == 1).any())
    if direction == -1:
        return bool((sub.get("bos_dir", 0) == -1).any() or (sub.get("choch_dir", 0) == -1).any())
    return False


def _dealing_side_ok(frame, i: int, direction: int, eq: Optional[float]) -> bool:
    if eq is None or i >= len(frame):
        return False
    try:
        z_high = float(frame.loc[i, "fvg_zone_high"])
        z_low = float(frame.loc[i, "fvg_zone_low"])
    except Exception:
        return False
    if not (z_low < z_high):
        return False
    fvg_mid = (z_high + z_low) / 2.0
    if direction == 1:
        return fvg_mid < eq
    if direction == -1:
        return fvg_mid > eq
    return False


def _dealing_side_ok_aligned(frame, i: int, direction: int, swing_high: Optional[float], swing_low: Optional[float]) -> bool:
    if swing_high is None or swing_low is None or swing_high <= swing_low:
        return False
    if i >= len(frame):
        return False
    try:
        z_high = float(frame.loc[i, "fvg_zone_high"])
        z_low = float(frame.loc[i, "fvg_zone_low"])
    except Exception:
        return False
    if not (z_low < z_high):
        return False
    try:
        from ict_backtest.dealing_range import classify_zone, zone_ok_for_direction
        zclass = classify_zone(z_high, z_low, float(swing_high), float(swing_low))
        return zone_ok_for_direction(zclass, direction)
    except Exception:
        return False


def _stack_count_same_dir(frame, i: int, direction: int, lookback: int = 32) -> tuple[int, bool]:
    if i <= 0 or i >= len(frame):
        return 0, False
    start = max(0, i - lookback)
    sub = frame.loc[start:i]
    bull = sub.get("fvg_bullish")
    bear = sub.get("fvg_bearish")
    if bull is None or bear is None:
        return 0, False
    mask = bull.fillna(False) if direction == 1 else bear.fillna(False)
    mask = mask.astype(bool)
    current = bool(mask.iloc[-1])
    count = int(mask.sum()) - (1 if current else 0)
    return max(0, count), count >= 2


def rank_fvg(
    frame,
    i: int,
    direction: int,
    *,
    active_ob_zone: Optional[tuple[float, float]] = None,
    dealing_eq: Optional[float] = None,
    swing_high: Optional[float] = None,
    swing_low: Optional[float] = None,
    displacement_ratio_min: float = 1.5,
    structure_lookback: int = 30,
    min_bpr_depth: float = 0.0,
) -> FvgAuthorityResult:
    if i < 0 or i >= len(frame):
        return FvgAuthorityResult(reason="invalid index")

    row = frame.loc[i]
    is_bull = bool(row.get("fvg_bullish", False))
    is_bear = bool(row.get("fvg_bearish", False))
    if not (is_bull or is_bear):
        return FvgAuthorityResult(reason="no fvg")

    if (is_bull and direction != 1) or (is_bear and direction != -1):
        return FvgAuthorityResult(reason="direction mismatch")

    z_high = row.get("fvg_zone_high")
    z_low = row.get("fvg_zone_low")
    if z_high is None or z_low is None or not (float(z_low) < float(z_high)):
        return FvgAuthorityResult(reason="invalid gap rectangle")

    result = FvgAuthorityResult(
        side_ok=_dealing_side_ok(frame, i, direction, dealing_eq),
        displacement_ok=_displacement_ok(frame, i, direction, ratio_min=displacement_ratio_min),
        narrative_ok=_structure_aligned(frame, i, direction, lookback=structure_lookback),
    )
    result.dealing_side_ok = _dealing_side_ok_aligned(frame, i, direction, swing_high, swing_low) or result.side_ok
    try:
        _stack_cnt, _stack_ok = _stack_count_same_dir(frame, i, direction)
        result.stack_count = _stack_cnt
        result.stack_ok = _stack_ok
    except Exception:
        pass

    if active_ob_zone is not None:
        ob_lo, ob_hi = active_ob_zone
        ok, depth = _overlap_depth(float(z_low), float(z_high), float(ob_lo), float(ob_hi))
        result.bpr_overlap = ok
        result.depth = depth
        if ok and depth >= min_bpr_depth:
            result.tier = "S1"
            result.supreme = True
            result.reason = f"BPR depth={depth:.2f}"
            return result

    if result.displacement_ok and result.narrative_ok:
        result.tier = "S2"
        result.reason = "displacement+narrative"
        return result

    result.tier = "S3"
    result.reason = "gap only"
    return result
