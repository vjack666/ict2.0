"""v2 Simulator — pure execution. NO ICT decision logic.

Wraps engine.simulate_trade. Spec §7.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from engine.signal import ICTSignal
from ict_backtest.simulator import simulate_trade
from ict_backtest.v2.contracts import Order, TradeResult
from ict_backtest.v2.event_log import EventLog


def simulate_order(
    order: Order,
    frame: pd.DataFrame,
    *,
    cost: dict[str, float] | None = None,
    event_log: EventLog | None = None,
) -> tuple[TradeResult | None, dict[str, Any]]:
    """Execute one Order on OHLC path. Does not read bos/fvg/sweep columns for decisions."""
    # IMPORTANT: empty EventLog is falsy via __len__; only replace if None.
    log = event_log if event_log is not None else EventLog()
    log.append(
        "OrderAccepted",
        ts=order.signal_time,
        plan_id=order.plan_id,
        order_id=order.order_id,
        payload={"direction": order.direction, "sl": order.stop_loss, "tp": order.take_profit},
    )

    # Bridge to existing pure path simulator (entry already strategy-resolved).
    sig = ICTSignal(
        symbol=order.symbol,
        time=order.signal_time,
        direction=order.direction,
        entry=order.entry_price_ref,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit,
        model=order.model_id,
        entry_at=order.entry_at,
        sweep_at=order.meta.get("sweep_at"),
        bos_at=order.meta.get("bos_at"),
    )

    trade, meta = simulate_trade(frame, sig, order.max_hold_bars, cost=cost)
    if trade is None:
        log.append(
            "TradeClosed",
            ts=order.signal_time,
            plan_id=order.plan_id,
            order_id=order.order_id,
            payload={"exit_reason": meta.get("exit_reason", "rejected")},
        )
        return None, meta

    trade_id = f"tr-{order.order_id}"
    reason = str(meta.get("exit_reason", "unknown"))
    kind_map = {
        "SL": "StopHit",
        "TP": "TargetHit",
        "hold_limit": "HoldExpired",
    }
    log.append(
        "EntryFilled",
        ts=trade.entry_time,
        plan_id=order.plan_id,
        order_id=order.order_id,
        trade_id=trade_id,
        payload={"entry_fill": trade.entry},
    )
    log.append(
        kind_map.get(reason, "TradeClosed"),
        ts=trade.exit_time,
        plan_id=order.plan_id,
        order_id=order.order_id,
        trade_id=trade_id,
        payload={"exit_reason": reason, "exit_fill": trade.exit},
    )
    if cost:
        log.append(
            "CostsApplied",
            ts=trade.exit_time,
            plan_id=order.plan_id,
            order_id=order.order_id,
            trade_id=trade_id,
            payload=dict(cost),
        )
    log.append(
        "TradeClosed",
        ts=trade.exit_time,
        plan_id=order.plan_id,
        order_id=order.order_id,
        trade_id=trade_id,
        payload={"pnl_r": trade.pnl_r, "exit_reason": reason},
    )

    result = TradeResult(
        trade_id=trade_id,
        order_id=order.order_id,
        plan_id=order.plan_id,
        symbol=order.symbol,
        direction=order.direction,
        entry_fill=trade.entry,
        exit_fill=trade.exit,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        pnl_r=trade.pnl_r,
        exit_reason=reason,
        hold_bars=int(meta.get("hold_bars", 0)),
        mfe_r=float(meta.get("mfe_r", 0.0)),
        mae_r=float(meta.get("mae_r", 0.0)),
        costs_breakdown=dict(cost) if cost else None,
    )
    return result, meta
