"""ict_backtest/market_structure.py — SHIM.

La implementación canónica de BOS/CHOCH (ICT/SMC, event-driven, confirm_bars)
vive en ``engine.market_structure`` (capa permanente del motor). Este módulo
solo reexporta el namespace completo para no romper a los ~20 importadores
(backtest, scripts, tests). Cero lógica duplicada.

Ley arquitectónica AGENTS.md §18: el backtest NO contiene lógica de decisión
propia; el motor (engine/) es la única fuente.
"""

import sys as _sys

import engine.market_structure as _engine_market_structure

# Replica el namespace completo (públicos y privados) para regresión cero.
_this = _sys.modules[__name__]
for _name, _val in vars(_engine_market_structure).items():
    if not _name.startswith("__"):
        setattr(_this, _name, _val)

del _engine_market_structure, _sys, _this, _name, _val
