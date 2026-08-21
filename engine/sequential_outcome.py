"""Outcome geometry for sequential-chain experiments (R-multiples).

Pure bar-by-bar path resolution on OHLC arrays:
- NO indicators (EMA/RSI/ATR forbidden by experiment contract).
- NO entries/PnL emission: this module only resolves levels into outcomes
  when the caller supplies them.

Structural stop (docs/ict/14_STOP_LOSS_ESTRUCTURAL.md):
- long  = min(sweep wick low, broken-swing low) - buffer
- short = max(sweep wick high, broken-swing high) + buffer

Structural target (v1 sanctioned fallback, measured projection):
- long  = range_high + (range_high - range_low)
- short = range_low - (range_high - range_low)

Intrabar tie (SL and TP touched in the same bar) resolves pessimistically
to SL. Horizon cap yields outcome "open" (excluded from win-rate).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OutcomeConfig:
    horizon_bars: int = 200
    sl_buffer: float = 0.0001  # small fixed buffer (1 pip on EURUSD)
    tie_policy: str = "pessimistic"  # SL+TP same bar -> SL


@dataclass(frozen=True)
class TradeLevels:
    """Entry plus structural SL/TP for one directional trade."""

    direction: int  # +1 long, -1 short
    entry: float
    sl: float
    tp: float

    def is_valid(self) -> bool:
        if not all(np.isfinite([self.entry, self.sl, self.tp])):
            return False
        if self.direction == 1:
            return self.sl < self.entry < self.tp
        if self.direction == -1:
            return self.tp < self.entry < self.sl
        return False

    @property
    def risk(self) -> float:
        return abs(self.entry - self.sl)


def structural_stop(
    direction: int,
    *,
    sweep_extreme: float | None,
    broken_swing: float | None,
    buffer: float,
) -> float | None:
    """Structural invalidation level; None when no structural anchor exists.

    sweep_extreme: wick extreme of the liquidity-sweep candle (long -> its low,
    short -> its high). broken_swing: most recent confirmed swing opposite the
    entry narrative (long -> swing low, short -> swing high). Both optional;
    at least one must be present. Never falls back to ATR.
    """
    candidates = [x for x in (sweep_extreme, broken_swing) if x is not None and np.isfinite(x)]
    if not candidates:
        return None
    if direction == 1:
        return float(min(candidates)) - float(buffer)
    if direction == -1:
        return float(max(candidates)) + float(buffer)
    return None


def measured_projection_tp(direction: int, range_high: float, range_low: float) -> float | None:
    """v1 fallback target: sequence-range extreme extended by the range height."""
    height = float(range_high) - float(range_low)
    if not np.isfinite(height) or height <= 0:
        return None
    if direction == 1:
        return float(range_high) + height
    if direction == -1:
        return float(range_low) - height
    return None


def resolve_outcome(
    high: np.ndarray,
    low: np.ndarray,
    entry_bar: int,
    levels: TradeLevels,
    cfg: OutcomeConfig | None = None,
) -> dict[str, object]:
    """Path-dependent scan after the entry bar (entry fills at its close).

    Returns {"outcome": "TP"|"SL"|"OPEN", "exit_r": float|None,
    "exit_bar": int|None, "bars_held": int|None}. R is signed profit in
    units of |entry - sl| (loss = -1.0 exactly).
    """
    if cfg is None:
        cfg = OutcomeConfig()
    n = len(high)
    if not levels.is_valid():
        return {"outcome": "INVALID", "exit_r": None, "exit_bar": None, "bars_held": None}
    risk = levels.risk
    scan_end = min(n, entry_bar + 1 + int(cfg.horizon_bars))
    for b in range(entry_bar + 1, scan_end):
        if levels.direction == 1:
            sl_hit = low[b] <= levels.sl
            tp_hit = high[b] >= levels.tp
        else:
            sl_hit = high[b] >= levels.sl
            tp_hit = low[b] <= levels.tp
        if sl_hit and tp_hit:
            # pessimistic intrabar tie
            return {"outcome": "SL", "exit_r": -1.0, "exit_bar": b, "bars_held": b - entry_bar}
        if sl_hit:
            return {"outcome": "SL", "exit_r": -1.0, "exit_bar": b, "bars_held": b - entry_bar}
        if tp_hit:
            r = ((levels.tp - levels.entry) / risk) if levels.direction == 1 else (
                (levels.entry - levels.tp) / risk
            )
            return {"outcome": "TP", "exit_r": float(r), "exit_bar": b, "bars_held": b - entry_bar}
    return {"outcome": "OPEN", "exit_r": None, "exit_bar": None, "bars_held": None}


def wilson_interval(wins: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = z * np.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    return (float(max(0.0, center - half)), float(min(1.0, center + half)))


def bootstrap_clustered(
    trades: list[dict[str, object]],
    cluster_key: str,
    n_resamples: int = 2000,
    seed: int = 42,
) -> dict[str, object]:
    """Cluster bootstrap CIs for mean R and win-rate over closed trades.

    Resamples clusters (chain_id) with replacement; each resample statistic
    aggregates every trade belonging to the sampled clusters.
    """
    closed = [t for t in trades if t.get("exit_r") is not None]
    clusters: dict[str, list[float]] = {}
    for t in closed:
        clusters.setdefault(str(t.get(cluster_key)), []).append(float(t["exit_r"]))  # type: ignore[arg-type]
    keys = list(clusters.keys())
    if not keys or n_resamples <= 0:
        return {"n_closed": len(closed), "mean_r_ci": None, "win_rate_ci": None,
                "n_resamples": n_resamples, "seed": seed}
    rng = np.random.default_rng(seed)
    sums = np.array([np.sum(clusters[k]) for k in keys])
    counts = np.array([len(clusters[k]) for k in keys])
    wins = np.array([sum(1 for r in clusters[k] if r > 0) for k in keys])
    idx = rng.integers(0, len(keys), size=(int(n_resamples), len(keys)))
    mean_r = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    win_rate = wins[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return {
        "n_closed": len(closed),
        "mean_r_ci": [float(np.percentile(mean_r, 2.5)), float(np.percentile(mean_r, 97.5))],
        "win_rate_ci": [float(np.percentile(win_rate, 2.5)), float(np.percentile(win_rate, 97.5))],
        "n_resamples": int(n_resamples),
        "seed": int(seed),
        "n_clusters": len(keys),
    }
