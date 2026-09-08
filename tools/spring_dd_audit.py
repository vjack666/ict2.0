"""Three-month Spring/Test DD calculator; research only, no MT5 order path."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    initial_balance: float = 5_000.0
    stop_percent: float = 0.03
    take_profit_usd: float = 60.0

    @property
    def stop_usd(self) -> float:
        return self.initial_balance * self.stop_percent


@dataclass(frozen=True)
class TradeOutcome:
    entry: float
    mfe_pips: float
    mae_pips: float
    pnl_usd: float


def classify_trade(entry: float, future_highs: list[float], future_lows: list[float],
                   *, lots: float = 0.10, pip_value_per_lot: float = 10.0,
                   risk: RiskConfig = RiskConfig()) -> TradeOutcome:
    """Apply TP/stop to a long Spring probe using conservative stop-first ties.

    This is a bounded research metric. It deliberately does not call MT5 or
    infer ICT probability. ``lots`` is the probe size; callers can model a
    ladder explicitly by calling this function per tranche.
    """
    if not future_highs or len(future_highs) != len(future_lows):
        raise ValueError("future bars are required")
    mfe = max(future_highs) - entry
    mae = entry - min(future_lows)
    tp_pips = risk.take_profit_usd / (lots * pip_value_per_lot)
    stop_pips = risk.stop_usd / (lots * pip_value_per_lot)
    mfe_pips = mfe / 0.0001
    mae_pips = mae / 0.0001
    if mae_pips >= stop_pips and mfe_pips >= tp_pips:
        pnl = -risk.stop_usd
    elif mae_pips >= stop_pips:
        pnl = -risk.stop_usd
    elif mfe_pips >= tp_pips:
        pnl = risk.take_profit_usd
    else:
        pnl = 0.0
    return TradeOutcome(entry, mfe / 0.0001, mae / 0.0001, pnl)


def summarize(outcomes: list[TradeOutcome], risk: RiskConfig = RiskConfig()) -> dict[str, float | int]:
    balance = risk.initial_balance
    peak = balance
    max_dd = 0.0
    for outcome in outcomes:
        balance += outcome.pnl_usd
        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)
    return {"trades": len(outcomes), "final_balance": round(balance, 2),
            "net_pnl": round(balance - risk.initial_balance, 2),
            "max_drawdown_usd": round(max_dd, 2),
            "max_drawdown_percent": round(max_dd / risk.initial_balance * 100, 4),
            "stop_usd": risk.stop_usd, "take_profit_usd": risk.take_profit_usd}


__all__ = ["RiskConfig", "TradeOutcome", "classify_trade", "summarize"]
