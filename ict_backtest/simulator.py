"""Historical execution and trade simulation for the backtest layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from engine.signal import ICTSignal
from ict_backtest.diagnostics.context_builder import RawDiagnosticData


@dataclass
class ICTTrade:
    symbol: str
    entry_time: str
    exit_time: str
    direction: int
    entry: float
    exit: float
    pnl_r: float


def fill_entry_price(frame: pd.DataFrame, entry_at: int, fill_mode: str) -> float:
    """Resolve the historical fill price for a generated signal."""
    if fill_mode == "next_open":
        nxt = entry_at + 1
        if nxt >= len(frame):
            raise ValueError("fill next_open: no hay vela siguiente al entry_at")
        return float(frame.iloc[nxt]["open"])
    if fill_mode == "signal_close":
        return float(frame.iloc[entry_at]["close"])
    raise ValueError(f"fill_mode desconocido: {fill_mode!r} (use 'next_open'|'signal_close')")


def simulate_trade(frame: pd.DataFrame, signal: ICTSignal,
                   max_hold_bars: int,
                   cost: dict | None = None) -> tuple[ICTTrade | None, dict[str, Any]]:
    """Simulate one historical trade bar by bar until SL/TP/hold limit."""
    ref_price = float(signal.entry)
    pip = 0.01 if ref_price >= 10 else 0.0001

    spread = (cost or {}).get("spread_pips", 0.0) * pip
    comm = (cost or {}).get("commission_pips", 0.0) * pip
    slip = (cost or {}).get("slippage_pips", 0.0) * pip

    times = frame["time"].astype(str)
    matches = list(frame.index[times == signal.time])
    if len(matches) == 0:
        return None, {"exit_reason": "time_not_found", "mfe_r": 0.0,
                      "mae_r": 0.0, "hold_bars": 0}

    idx = int(matches[0])
    sl, tp = signal.stop_loss, signal.take_profit
    dirn = 1 if signal.direction == 1 else -1
    entry_fill = signal.entry + dirn * (slip + spread / 2.0)
    risk_real = abs(signal.entry - sl)
    min_risk = 1.0 * pip
    if risk_real <= min_risk:
        return None, {"exit_reason": "invalid_risk", "mfe_r": 0.0,
                      "mae_r": 0.0, "hold_bars": 0}
    risk = abs(entry_fill - sl)

    exit_idx, exit_price, exit_reason = idx, entry_fill, "hold_limit"
    mfe_r, mae_r = -1e9, 1e9

    for step in range(1, max_hold_bars + 1):
        j = idx + step
        if j >= len(frame):
            break
        row = frame.iloc[j]
        high, low = float(row["high"]), float(row["low"])

        if signal.direction == 1:
            step_mfe = (high - entry_fill) / risk
            step_mae = (low - entry_fill) / risk
            if low <= sl:
                exit_idx, exit_price, exit_reason = j, sl, "SL"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
            if high >= tp:
                exit_idx, exit_price, exit_reason = j, tp, "TP"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
        else:
            step_mfe = (entry_fill - low) / risk
            step_mae = (entry_fill - high) / risk
            if high >= sl:
                exit_idx, exit_price, exit_reason = j, sl, "SL"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
            if low <= tp:
                exit_idx, exit_price, exit_reason = j, tp, "TP"
                mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)
                break
        exit_idx, exit_price = j, float(row["close"])
        mfe_r, mae_r = max(mfe_r, step_mfe), min(mae_r, step_mae)

    pnl_price = (exit_price - entry_fill) if signal.direction == 1 else (entry_fill - exit_price)
    pnl_r = (pnl_price - comm) / risk
    trade = ICTTrade(
        symbol=signal.symbol, entry_time=signal.time,
        exit_time=str(frame.iloc[exit_idx]["time"]), direction=signal.direction,
        entry=entry_fill, exit=exit_price, pnl_r=float(pnl_r),
    )
    hold_bars = max(0, int(exit_idx - idx))
    if mfe_r < -1e8:
        mfe_r = 0.0
    if mae_r > 1e8:
        mae_r = 0.0
    return trade, {"exit_reason": exit_reason, "mfe_r": float(mfe_r),
                   "mae_r": float(mae_r), "hold_bars": hold_bars}


def simulate_trade_with_context(
    frame: pd.DataFrame, signal: ICTSignal, max_hold_bars: int,
    cost: dict | None = None, *, est_htf_fn=None, ltf_tf: str = "M15",
    backtest_id: str = "", market_stack: dict[str, Any] | None = None,
) -> tuple[ICTTrade | None, dict[str, Any], RawDiagnosticData | None]:
    """Simulate and emit raw diagnostic data without building a context."""
    trade, meta = simulate_trade(frame, signal, max_hold_bars, cost=cost)
    if trade is None:
        return None, meta, None

    row: dict[str, Any] = {}
    try:
        times = frame["time"].astype(str)
        matches = list(frame.index[times == signal.time])
        if matches:
            r = frame.iloc[int(matches[0])]
            row = {k: r.get(k) for k in ("atr", "atr_z", "sl_is_structural",
                                          "dist_entry_to_sl_r")}
    except (KeyError, ValueError, IndexError):
        row = {}

    htf_context: dict[str, Any] | None = None
    if est_htf_fn is not None:
        try:
            htf_context = est_htf_fn(int(getattr(signal, "entry_at", 0) or 0))
        except (TypeError, ValueError, KeyError):
            htf_context = None

    raw = RawDiagnosticData(
        signal=signal, trade=trade, meta=meta, row=row,
        htf_context=htf_context, backtest_id=backtest_id,
        market_stack=market_stack,
    )
    return trade, meta, raw


__all__ = [
    "ICTTrade",
    "fill_entry_price",
    "simulate_trade",
    "simulate_trade_with_context",
]

