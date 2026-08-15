"""Compatibility facade for the old ``ict_backtest.engine`` import path.

Decision contracts live in ``engine``. Historical execution lives in
``ict_backtest.simulator``. This module intentionally contains no logic.
"""

from engine.signal import ICTSignal
from engine.trade_levels import (
    STRUCT_SL_BUFFER_RANGE,
    STRUCT_SL_MAX_RANGE,
    _tp_liquidity,
    calc_structural_sl,
)
from ict_backtest.simulator import (
    ICTTrade,
    fill_entry_price,
    simulate_trade,
    simulate_trade_with_context,
)

__all__ = [
    "ICTSignal",
    "ICTTrade",
    "STRUCT_SL_BUFFER_RANGE",
    "STRUCT_SL_MAX_RANGE",
    "_tp_liquidity",
    "calc_structural_sl",
    "fill_entry_price",
    "simulate_trade",
    "simulate_trade_with_context",
]
