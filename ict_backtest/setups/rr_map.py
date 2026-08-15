"""SHIM — la logica vive en engine.rr_by_setup (Ley: motor unica fuente).

Este archivo QUEDA solo como re-export para no romper el dashboard/observador
que importa ict_backtest.setups.rr_map. El backtest ya importa engine.rr_by_setup.
"""
from engine.rr_by_setup import (  # noqa: F401
    RR_BY_SETUP,
    rr_for,
    flag_rr,
    _setup_of,
)
