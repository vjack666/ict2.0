"""SHIM — la logica vive en engine.turtle_soup (Ley: motor unica fuente).

Re-export para no romper el dashboard/observador. El backtest ya importa
engine.turtle_soup.
"""
from engine.turtle_soup import (  # noqa: F401
    _coerce_ts,
    _prev_day_ohlc,
    _sweep_broke,
    _has_reversal,
    _volume_on_sweep,
    is_turtle_soup,
    flag_turtle_soup,
)
