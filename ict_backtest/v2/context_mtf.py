"""ict_backtest/v2/context_mtf.py — Thin wrapper que CONSUME el motor.

La logica top-down (snapshot_tf, build_context_stack, top_down_allows_trade,
dealing_range_pd) es la lectura del trader humano y vive en el MOTOR
(engine/plan.py, permanente). El backtest (desechable) la importa de aqui para
demostrar la tesis. No se duplica logica: este modulo solo re-exporta.
"""

from __future__ import annotations

from engine.plan import (  # noqa: F401 — el motor es la fuente
    build_context_stack,
    dealing_range_pd,
    snapshot_tf,
    top_down_allows_trade,
)

__all__ = [
    "build_context_stack",
    "top_down_allows_trade",
    "snapshot_tf",
    "dealing_range_pd",
]
