"""ict_backtest/plan_fsm.py — Fase 1 (Arquitectura de Plan).

FSM CENTRAL de plan multi-TF, basada en eventos. REDUCER PURO:
(state, event) -> new_state. Sin timers, sin bar_index, sin acoplar TF.

Reutiliza el patron de `state_machine.py` (MarketEvent/StateMachine):
aquel transiciona el estado de UN MarketObject por evento; este
transiciona el estado del PLAN por evento de nivel superior. Mismo
espíritu, dos niveles distintos.

Contrato (docs/plan/ARQUITECTURA_TEMPORALIDADES.md + ROADMAP_CAPACIDADES.md):
- PlanFSM NO altera el conteo de senales de run_sequence (no invasion).
- Emisores por TF son funciones PURAS que reciben SOLO sus MarketObjects
  y devuelven un PlanEvent. NUNCA consultan frames de otro TF.
- El loop driver (fuera de este modulo) orquesta: junta barras cerradas
  <= t, llama cada emisor con sus objetos, alimenta eventos a PlanFSM en
  orden causal (D1->H4->H1->M15...).
- CONTEXT_OK requiere D1 Y H4 (ambos crean el plan; BACKTEST_V2_SPEC 2.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from engine.market_object import MarketObject


class PlanVerdict(Enum):
    """Decision de una capa de temporalidad."""

    CONTEXT_OK = "CONTEXT_OK"
    CONTEXT_INVALID = "CONTEXT_INVALID"
    ZONE_ARMED = "ZONE_ARMED"
    ZONE_INVALID = "ZONE_INVALID"
    SETUP_LIVE = "SETUP_LIVE"
    STRUCTURE_OK = "STRUCTURE_OK"
    ENTRY_READY = "ENTRY_READY"
    IN_TRADE = "IN_TRADE"


class PlanState(Enum):
    """Estado del plan global."""

    NO_TRADE = "NO_TRADE"
    CONTEXT_OK = "CONTEXT_OK"
    ZONE_ARMED = "ZONE_ARMED"
    SETUP_LIVE = "SETUP_LIVE"
    STRUCTURE_OK = "STRUCTURE_OK"
    ENTRY_READY = "ENTRY_READY"
    IN_TRADE = "IN_TRADE"
    CLOSED = "CLOSED"


@dataclass
class PlanEvent:
    """Evento de nivel de plan producido por un emisor de TF.

    Solo lleva (capa, veredicto, payload suelto). NUNCA nº de velas ni
    ventana (igual que MarketEvent en state_machine.py).
    """

    layer: str
    verdict: PlanVerdict
    payload: Any | None = None
    bar_index: int = 0
    time: Any | None = None


# Capas que deben confirmar CONTEXT_OK antes de salir de NO_TRADE.
_CONTEXT_LAYERS = ("D1", "H4")

# Tabla de transiciones: (estado, veredicto) -> nuevo estado (una vez
# alcanzado el contexto). Cualquier *_INVALID devuelve a NO_TRADE.
_TRANSITIONS: dict[tuple[PlanState, PlanVerdict], PlanState] = {
    (PlanState.CONTEXT_OK, PlanVerdict.ZONE_ARMED): PlanState.ZONE_ARMED,
    (PlanState.ZONE_ARMED, PlanVerdict.ZONE_ARMED): PlanState.ZONE_ARMED,
    (PlanState.ZONE_ARMED, PlanVerdict.SETUP_LIVE): PlanState.SETUP_LIVE,
    (PlanState.ZONE_ARMED, PlanVerdict.STRUCTURE_OK): PlanState.STRUCTURE_OK,
    (PlanState.SETUP_LIVE, PlanVerdict.STRUCTURE_OK): PlanState.STRUCTURE_OK,
    (PlanState.STRUCTURE_OK, PlanVerdict.ENTRY_READY): PlanState.ENTRY_READY,
    (PlanState.ENTRY_READY, PlanVerdict.ENTRY_READY): PlanState.ENTRY_READY,
    (PlanState.ENTRY_READY, PlanVerdict.IN_TRADE): PlanState.IN_TRADE,
}


class PlanFSM:
    """Reductor puro de estado de plan. Transiciona por evento."""

    def __init__(self, state: PlanState = PlanState.NO_TRADE) -> None:
        self.state = state
        self._context_layers: set[str] = set()

    def transition(self, event: PlanEvent) -> PlanState:
        """Aplica un PlanEvent y devuelve el nuevo estado.

        Decision POR EVENTO, no por tiempo. No accede a bar_index.
        - CONTEXT_OK de D1/H4 se acumula; al completar ambos, sale de
          NO_TRADE a CONTEXT_OK (el plan nace arriba, D1+H4).
        - Cualquier veredicto INVALID reinicia a NO_TRADE y borra el
          contexto acumulado.
        """
        if event.verdict in (PlanVerdict.CONTEXT_INVALID, PlanVerdict.ZONE_INVALID):
            self.reset()
            return self.state
        if event.verdict is PlanVerdict.CONTEXT_OK and event.layer in _CONTEXT_LAYERS:
            self._context_layers.add(event.layer)
            if self.state is PlanState.NO_TRADE and self._context_layers >= set(_CONTEXT_LAYERS):
                self.state = PlanState.CONTEXT_OK
            return self.state
        new_state = _TRANSITIONS.get((self.state, event.verdict))
        if new_state is not None:
            self.state = new_state
        return self.state

    def reset(self) -> None:
        self.state = PlanState.NO_TRADE
        self._context_layers = set()


def _objs_before(objs_by_tf: dict[str, list[MarketObject]], tf: str, t) -> list[MarketObject]:
    """Objetos de un TF ya cerrados en t (anti look-ahead cross-TF real).

    Filtra por ``bar_time`` (timestamp), porque HTF y LTF tienen bar_index
    distintos. Fallback a bar_index si el objeto no trae bar_time.
    """
    out: list[MarketObject] = []
    for o in objs_by_tf.get(tf, []) or []:
        ot = getattr(o, "bar_time", None)
        oi = getattr(o, "bar_index", None)
        if ot is not None and t is not None:
            import pandas as pd
            try:
                if pd.to_datetime(ot) <= pd.to_datetime(t):
                    out.append(o)
                continue
            except (TypeError, ValueError):
                pass
        if oi is not None and isinstance(t, int):
            if oi <= t:
                out.append(o)
    return out
