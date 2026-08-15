"""ict_backtest/plan_fsm.py — SHIM.

La FSM de plan multi-TF vive en ``engine.plan_fsm`` (capa permanente del
motor). Este módulo solo reexporta el namespace completo. Cero lógica
duplicada.

Ley arquitectónica AGENTS.md §18: el backtest NO contiene lógica de decisión
propia; el motor (engine/) es la única fuente.
"""

import sys as _sys

import engine.plan_fsm as _engine_plan_fsm

_this = _sys.modules[__name__]
for _name, _val in vars(_engine_plan_fsm).items():
    if not _name.startswith("__"):
        setattr(_this, _name, _val)

del _engine_plan_fsm, _sys, _this, _name, _val
