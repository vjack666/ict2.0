"""SHIM — la logica vive en engine.silver_bullet (Ley: motor unica fuente).

Re-export para no romper el dashboard/observador. El backtest ya importa
engine.silver_bullet.
"""
from engine.silver_bullet import (  # noqa: F401
    _SB_KILLZONES,
    _to_ts,
    is_silver_bullet,
    volume_confirm,
    flag_silver_bullet,
)
