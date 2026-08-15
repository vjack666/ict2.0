"""v2 contracts — Strategy / TradingPlan / Order / Simulator boundary.

No ICT decision logic here. Spec: BACKTEST_V2_SPEC.md §4, §8.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CoverageMode(str, Enum):
    LEGACY_SUBSET = "legacy_subset"
    V2_FULL = "v2_full"
    V2_PARTIAL = "v2_partial"


class PlanState(str, Enum):
    NO_TRADE = "NO_TRADE"
    CONTEXT_OK = "CONTEXT_OK"
    ZONE_ARMED = "ZONE_ARMED"
    SETUP_LIVE = "SETUP_LIVE"
    STRUCTURE_OK = "STRUCTURE_OK"
    ENTRY_READY = "ENTRY_READY"
    IN_TRADE = "IN_TRADE"
    CLOSED = "CLOSED"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"


@dataclass
class Order:
    """Broker-ready intent. Simulator must not interpret meta for decisions."""

    order_id: str
    plan_id: str
    symbol: str
    model_id: str
    direction: int  # +1 / -1
    signal_time: str
    stop_loss: float
    take_profit: float
    max_hold_bars: int
    entry_price_ref: float  # strategy-resolved fill reference (already next_open etc.)
    entry_at: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TradeResult:
    trade_id: str
    order_id: str
    plan_id: str
    symbol: str
    direction: int
    entry_fill: float
    exit_fill: float
    entry_time: str
    exit_time: str
    pnl_r: float
    exit_reason: str
    hold_bars: int
    mfe_r: float = 0.0
    mae_r: float = 0.0
    costs_breakdown: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventLogRecord:
    ts: str
    seq: int
    kind: str
    plan_id: str | None = None
    order_id: str | None = None
    trade_id: str | None = None
    tf: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TradeExplanation:
    """Human-readable why-this-trade (Strategy builds; Simulator only exit)."""

    trade_id: str
    plan_id: str
    order_id: str
    result: str
    layers: dict[str, Any] = field(default_factory=dict)
    quality_score: float | None = None
    event_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_human(self) -> str:
        lines = [f"Trade {self.trade_id}  Result: {self.result}"]
        for layer, info in self.layers.items():
            lines.append(f"  {layer}: {info}")
        if self.quality_score is not None:
            lines.append(f"  quality_score: {self.quality_score}")
        return "\n".join(lines)


@dataclass
class TradingPlan:
    """Full decision package at evaluation time (not just an order)."""

    plan_id: str
    symbol: str
    model_id: str
    state: PlanState
    coverage_mode: CoverageMode
    orders: list[Order] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    narrative: dict[str, Any] = field(default_factory=dict)
    zone: dict[str, Any] | None = None
    setup: dict[str, Any] | None = None
    quality_score: float | None = None
    invalidation_rules: list[str] = field(default_factory=list)
    event_seq_ids: list[int] = field(default_factory=list)
    explanation_template: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["coverage_mode"] = self.coverage_mode.value
        return d
