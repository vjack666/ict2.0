"""ict_backtest/dealing_range.py — SHIM.

La lógica EQ / premium-discount (book 21 / PO3) vive en ``engine.dealing_range_eq``
(capa permanente del motor). Este módulo solo reexporta el namespace completo.
Cero lógica duplicada.

Ley arquitectónica AGENTS.md §18: el backtest NO contiene lógica de decisión
propia; el motor (engine/) es la única fuente.
"""

import sys as _sys

import engine.dealing_range_eq as _engine_dealing_range_eq

_this = _sys.modules[__name__]
for _name, _val in vars(_engine_dealing_range_eq).items():
    if not _name.startswith("__"):
        setattr(_this, _name, _val)

del _engine_dealing_range_eq, _sys, _this, _name, _val
