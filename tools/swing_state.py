"""Estado temporal de un evento de mercado (fresh/tested/mitigated/invalidated).

Rescate aislado de SMC-SYSTEMS/engine/market_object.py::ObjectState.
Adaptado a tools/ como helper puro (sin dataclass engine).

Cadena de vida de un BOS/CHOCH:
  CREATED -> ACTIVE -> MITIGATED (testeado pero no roto) -> INVALIDATED (roto en contra)
  (CONSUMED = ya usado por un setup, opcional)
"""
from __future__ import annotations

from enum import Enum


class ObjectState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"
    CONSUMED = "CONSUMED"


def next_state_on_test(level: float, break_price: float, direction: int) -> str:
    """Dado el nivel roto y el precio actual, decide si sigue ACTIVE o INVALIDATED.

    direction: 1 = el evento fue alcista (rompio al alza); -1 = bajista.
    Si el precio cruza el nivel en sentido contrario -> INVALIDATED.
    """
    if direction == 1 and break_price < level:
        return ObjectState.INVALIDATED.value
    if direction == -1 and break_price > level:
        return ObjectState.INVALIDATED.value
    return ObjectState.ACTIVE.value
