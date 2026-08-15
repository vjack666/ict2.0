"""Legacy strategy adapter — wraps generate_sequence_signals as TradingPlan.

This is the F0 bridge: same H4→M15 decisions as today, packaged for v2 boundary.
Coverage mode is ALWAYS legacy_subset.
"""
from __future__ import annotations

from typing import Any

from ict_backtest.engine import ICTSignal
from ict_backtest.v2.contracts import (
    CoverageMode,
    Order,
    PlanState,
    TradeExplanation,
    TradingPlan,
)
from ict_backtest.v2.event_log import EventLog


def signals_to_plan(
    signals: list[ICTSignal],
    *,
    symbol: str,
    model_id: str = "sequence_legacy",
    max_hold_bars: int = 16,
    htf: str = "H4",
    ltf: str = "M15",
    event_log: EventLog | None = None,
) -> TradingPlan:
    """Convert ICTSignal list (already strategy-resolved) into one TradingPlan."""
    plan_id = f"plan-legacy-{symbol}"
    # IMPORTANT: do not use `event_log or EventLog()` — empty EventLog is falsy via __len__.
    log = event_log if event_log is not None else EventLog()

    log.append(
        "PlanFormed",
        plan_id=plan_id,
        tf=ltf,
        payload={
            "coverage_mode": CoverageMode.LEGACY_SUBSET.value,
            "htf": htf,
            "ltf": ltf,
            "n_signals": len(signals),
        },
    )

    orders: list[Order] = []
    for i, sig in enumerate(signals):
        oid = f"ord-{symbol}-{i:05d}"
        log.append(
            "OrderIntentEmitted",
            ts=str(sig.time),
            plan_id=plan_id,
            order_id=oid,
            tf=ltf,
            payload={
                "direction": sig.direction,
                "entry_ref": sig.entry,
                "sl": sig.stop_loss,
                "tp": sig.take_profit,
            },
        )
        orders.append(
            Order(
                order_id=oid,
                plan_id=plan_id,
                symbol=symbol,
                model_id=model_id,
                direction=int(sig.direction),
                signal_time=str(sig.time),
                stop_loss=float(sig.stop_loss),
                take_profit=float(sig.take_profit),
                max_hold_bars=max_hold_bars,
                entry_price_ref=float(sig.entry),
                entry_at=sig.entry_at,
                meta={
                    "sweep_at": sig.sweep_at,
                    "bos_at": sig.bos_at,
                    "legacy_signal": True,
                },
            )
        )

    state = PlanState.ENTRY_READY if orders else PlanState.NO_TRADE
    return TradingPlan(
        plan_id=plan_id,
        symbol=symbol,
        model_id=model_id,
        state=state,
        coverage_mode=CoverageMode.LEGACY_SUBSET,
        orders=orders,
        context={"note": "D1 not used in decision when htf!=D1 (legacy_subset)"},
        narrative={"htf": htf, "bias_source": "single_htf_trend"},
        zone=None,
        setup={"ltf": ltf, "engine": "run_sequence+generate_sequence_signals"},
        quality_score=None,
        invalidation_rules=["legacy_timers", "killzone_pre_filter"],
        explanation_template={
            "htf": htf,
            "ltf": ltf,
            "coverage": "legacy_subset",
        },
    )


def explanation_for_trade(
    plan: TradingPlan,
    order: Order,
    exit_reason: str,
    *,
    event_ids: list[int] | None = None,
) -> TradeExplanation:
    layers: dict[str, Any] = {
        "D1": plan.context.get("note", "not_in_decision"),
        "H4": plan.narrative,
        "H1": "missing (legacy_subset)",
        "M15": plan.setup,
        "exec": {
            "tf": plan.setup.get("ltf") if plan.setup else "?",
            "direction": order.direction,
            "entry_ref": order.entry_price_ref,
            "sl": order.stop_loss,
            "tp": order.take_profit,
        },
    }
    return TradeExplanation(
        trade_id=f"tr-{order.order_id}",
        plan_id=plan.plan_id,
        order_id=order.order_id,
        result=exit_reason,
        layers=layers,
        quality_score=plan.quality_score,
        event_ids=event_ids or [],
    )
