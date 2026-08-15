"""ict_backtest — ICT engine package.

R7: trade decisions come only from ``canonical.evaluate_signals`` (sequence).
``engine/`` holds decision contracts and structural levels; ``simulator.py``
holds historical fills and trade outcomes.
``rules.py`` remains pure checklists for UI display — not a second signal motor.
"""

from ict_backtest.structure import classify_structure, classify_multi_tf, momentum_direction
from ict_backtest.rules import evaluate, checklist_intradia, checklist_scalping, killzone_en
from engine.signal import ICTSignal
from ict_backtest.simulator import ICTTrade, simulate_trade
from ict_backtest.canonical import (
    CANONICAL_ENGINE,
    evaluate_signals,
    latest_plan,
    R7_DOCUMENTED_DEBT,
)

__all__ = [
    "classify_structure", "classify_multi_tf", "momentum_direction",
    "evaluate", "checklist_intradia", "checklist_scalping", "killzone_en",
    "ICTSignal", "ICTTrade", "simulate_trade",
    "CANONICAL_ENGINE", "evaluate_signals", "latest_plan", "R7_DOCUMENTED_DEBT",
]
