"""ict_backtest/po3_motor.py — SHIM.

``compute_po3_complete`` / ``Po3MotorConfig`` viven en ``engine.po3`` (capa
permanente del motor). Este módulo solo reexporta el namespace completo.
Cero lógica duplicada.

Ley arquitectónica AGENTS.md §18: el backtest NO contiene lógica de decisión
propia; el motor (engine/) es la única fuente.
"""

import sys as _sys

import engine.po3 as _engine_po3

_this = _sys.modules[__name__]
for _name, _val in vars(_engine_po3).items():
    if not _name.startswith("__"):
        setattr(_this, _name, _val)

del _engine_po3, _sys, _this, _name, _val
