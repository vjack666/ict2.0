"""ict_backtest/plan_attach.py — SHIM.

El loop driver nivel 2 (attach_alignment) vive en ``engine.plan_attach``
(capa permanente del motor). Este módulo solo reexporta el namespace completo.
Cero lógica duplicada.

Ley arquitectónica AGENTS.md §18: el backtest NO contiene lógica de decisión
propia; el motor (engine/) es la única fuente.
"""

import sys as _sys

import engine.plan_attach as _engine_plan_attach

_this = _sys.modules[__name__]
for _name, _val in vars(_engine_plan_attach).items():
    if not _name.startswith("__"):
        setattr(_this, _name, _val)

del _engine_plan_attach, _sys, _this, _name, _val
