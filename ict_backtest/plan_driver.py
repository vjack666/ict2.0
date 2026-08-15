"""ict_backtest/plan_driver.py — SHIM.

El score/FSM de alineación multi-TF vive en ``engine.plan_driver`` (capa
permanente del motor). Este módulo solo reexporta el namespace completo.
Cero lógica duplicada.

Ley arquitectónica AGENTS.md §18: el backtest NO contiene lógica de decisión
propia; el motor (engine/) es la única fuente.
"""

import sys as _sys

import engine.plan_driver as _engine_plan_driver

_this = _sys.modules[__name__]
for _name, _val in vars(_engine_plan_driver).items():
    if not _name.startswith("__"):
        setattr(_this, _name, _val)

del _engine_plan_driver, _sys, _this, _name, _val
