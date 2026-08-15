"""Backtest v2 — architecture boundary (Phase F0).

Pipeline: Strategy → TradingPlan → Orders → Simulator
See docs/plan/BACKTEST_V2_SPEC.md
"""

from ict_backtest.v2.contracts import (
    CoverageMode,
    EventLogRecord,
    Order,
    TradeExplanation,
    TradeResult,
    TradingPlan,
)
from ict_backtest.v2.coverage import CoverageReport, build_coverage_report, default_registry
from ict_backtest.v2.event_log import EventLog
from ict_backtest.v2.orchestrator import run_legacy_subset
from ict_backtest.v2.simulator import simulate_order

__all__ = [
    "CoverageMode",
    "CoverageReport",
    "EventLog",
    "EventLogRecord",
    "Order",
    "TradeExplanation",
    "TradeResult",
    "TradingPlan",
    "build_coverage_report",
    "default_registry",
    "run_legacy_subset",
    "simulate_order",
]
