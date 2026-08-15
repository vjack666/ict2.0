"""ict_backtest/state_machine.py — Fase A (R10.C): máquina de estados semántica.

Transiciona `ObjectState` de cada MarketObject por EVENTO del mercado.
NO por conteo de velas: `apply` no lee `bar_index` ni resta índices.

El enum ObjectState YA EXISTE en market_object.py; este módulo es el motor
que aplica las transiciones, no las redefine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ict_backtest.market_object import MarketObject, ObjectState


@dataclass
class MarketEvent:
    """Evento de mercado que dispara una transición de estado.

    Solo lleva (tipo, objetivo). NUNCA lleva nº de velas ni ventana.
    """

    type: str
    target: MarketObject
    context: Any | None = None


# Tabla de transiciones permitidas por evento (sin timers).
_TRANSITIONS: dict[str, dict[ObjectState, ObjectState]] = {
    "StructureBroken": {
        ObjectState.CREATED: ObjectState.ACTIVE,
    },
    "SwingBroken": {
        ObjectState.ACTIVE: ObjectState.INVALIDATED,
        ObjectState.MITIGATED: ObjectState.INVALIDATED,
    },
    "ReturnToZone": {
        ObjectState.ACTIVE: ObjectState.MITIGATED,
    },
    "Consumed": {
        ObjectState.ACTIVE: ObjectState.CONSUMED,
        ObjectState.MITIGATED: ObjectState.CONSUMED,
    },
    "LiquidityTaken": {
        ObjectState.ACTIVE: ObjectState.MITIGATED,
    },
}


class StateMachine:
    """Aplica transiciones de estado por evento sobre MarketObject."""

    def apply(self, event: MarketEvent) -> None:
        """Transiciona `event.target.state` según `event.type`.

        Decisión POR EVENTO, no por tiempo. No accede a bar_index.
        """
        table = _TRANSITIONS.get(event.type)
        if table is None:
            return
        new_state = table.get(event.target.state)
        if new_state is not None:
            event.target.state = new_state
