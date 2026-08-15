"""ict_backtest/setups/ote.py — SHIM.

La implementación OTE (Optimal Trade Entry, 62-79% Fib retrace) vive en
``engine.ote`` (capa permanente del motor). Este módulo solo reexporta el
namespace completo. Cero lógica duplicada.

Ley arquitectónica AGENTS.md §18: el backtest NO contiene lógica de decisión
propia; el motor (engine/) es la única fuente.
"""

import sys as _sys

import engine.ote as _engine_ote

_this = _sys.modules[__name__]
for _name, _val in vars(_engine_ote).items():
    if not _name.startswith("__"):
        setattr(_this, _name, _val)

del _engine_ote, _sys, _this, _name, _val
