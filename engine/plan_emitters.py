"""ict_backtest/plan_emitters.py — Fase 1: emisores por TF (D1/H4/H1).

Funciones PURAS que reciben SOLO los MarketObjects de su propio TF y
devuelven un PlanEvent. NUNCA consultan frames de otro TF (regla de
desacoplamiento de ARQUITECTURA_TEMPORALIDADES.md).

El loop driver (run_backtest) orquesta: pasa a cada emisor los objetos
de su TF y alimenta los eventos a PlanFSM en orden causal. Los emisores
no saben de la existencia de los otros TF.
"""

from __future__ import annotations

from typing import Sequence, Any


def _field(sig: Any, name: str, default: Any = None) -> Any:
    """Lee un campo de la señal sea dict O ICTSignal (dataclass).

    Los emisores y el gate deben aceptar AMBOS: run_sequence produce
    ICTSignal (objetos), los tests/demos producen dicts. getattr funciona
    para dataclasses; para dicts usamos .get.
    """
    if isinstance(sig, dict):
        return sig.get(name, default)
    return getattr(sig, name, default)


from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.plan_fsm import PlanEvent, PlanVerdict


def _bar_index_of(objs: Sequence[MarketObject]) -> int:
    idxs = [o.bar_index for o in objs if o.bar_index is not None]
    return max(idxs) if idxs else 0


def emit_d1(objs: Sequence[MarketObject]) -> PlanEvent:
    """Contexto macro (D1). CONTEXT_OK si hay estructura de contexto."""
    if not objs:
        return PlanEvent("D1", PlanVerdict.CONTEXT_INVALID, bar_index=0)
    return PlanEvent("D1", PlanVerdict.CONTEXT_OK, bar_index=_bar_index_of(objs))


def emit_h4(objs: Sequence[MarketObject]) -> PlanEvent:
    """Bias intradia (H4). CONTEXT_OK si hay BOS/CHOCH activo."""
    if not objs:
        return PlanEvent("H4", PlanVerdict.CONTEXT_INVALID, bar_index=0)
    hay_bias = any(
        o.type in (ObjectType.BOS, ObjectType.CHOCH)
        and o.state in (ObjectState.ACTIVE, ObjectState.CREATED)
        for o in objs
    )
    if not hay_bias:
        return PlanEvent("H4", PlanVerdict.CONTEXT_INVALID, bar_index=_bar_index_of(objs))
    return PlanEvent("H4", PlanVerdict.CONTEXT_OK, bar_index=_bar_index_of(objs))


def emit_h1(objs: Sequence[MarketObject]) -> PlanEvent:
    """Validacion POI (H1). ZONE_ARMED si hay POI (OB/FVG) en H1."""
    if not objs:
        return PlanEvent("H1", PlanVerdict.ZONE_INVALID, bar_index=0)
    hay_poi = any(
        o.role is Role.POI
        and o.type in (ObjectType.ORDER_BLOCK, ObjectType.FVG)
        and o.state in (ObjectState.ACTIVE, ObjectState.CREATED)
        for o in objs
    )
    if not hay_poi:
        return PlanEvent("H1", PlanVerdict.ZONE_INVALID, bar_index=_bar_index_of(objs))
    return PlanEvent("H1", PlanVerdict.ZONE_ARMED, bar_index=_bar_index_of(objs))


# Fases internas de run_sequence que definen el nivel de setup alcanzado.
_PHASE_STRUCTURE_OK = "ENTRY"
_PHASE_SETUP_LIVE = "BOS_DONE"


def emit_m15(signals: Sequence[dict]) -> PlanEvent | None:
    """Setup ICT (M15). Envuelve la salida de run_sequence / ICTSignal.

    Contrato dual (sin romper tests legacy ni el loop real):
    - Si la senal trae ``phase_log`` (API de prueba aislada), usa esa fase.
    - Si es ``ICTSignal`` real (campos ``entry_at``/``bos_at``, SIN
      ``phase_log``), infiere el veredicto: ENTRY alcanzado (entry_at
      presente) => STRUCTURE_OK; solo BOS (bos_at, sin entry) => SETUP_LIVE.
      Esto es coherente con la secuencia canonica sweep->displace->BOS->entry.

    El emisor NO sabe de H4/H1: solo decide sobre la salida de su TF.
    Acepta dict O ICTSignal (usa _field).
    """
    if not signals:
        return None
    # API legacy: phase_log explicito
    fases = [f for s in signals for f in _field(s, "phase_log", []) or []]
    if fases:
        if _PHASE_STRUCTURE_OK in fases:
            return PlanEvent("M15", PlanVerdict.STRUCTURE_OK, bar_index=0)
        if _PHASE_SETUP_LIVE in fases:
            return PlanEvent("M15", PlanVerdict.SETUP_LIVE, bar_index=0)
        return None
    # API real (ICTSignal): entry_at / bos_at dictan la fase alcanzada.
    hay_entry = any(_field(s, "entry_at") is not None for s in signals)
    hay_bos = any(_field(s, "bos_at") is not None for s in signals)
    if hay_entry:
        return PlanEvent("M15", PlanVerdict.STRUCTURE_OK, bar_index=0)
    if hay_bos:
        return PlanEvent("M15", PlanVerdict.SETUP_LIVE, bar_index=0)
    return None


def emit_m5(setup: dict, m5_confirm: dict) -> PlanEvent | None:
    """Ejecucion (M5). Decide SI entrar, NO la direccion del plan.

    Recibe el setup validado (direction) y la confirmacion de M5
    (direction + confirmed). M5 es exec TF: filtra + ejecuta, NO modifica
    el plan (matriz de autoridad). Regla de jerarquia: M5 NO puede
    invertir la direccion del plan; solo confirma en la MISMA direccion.

    - ENTRY_READY si m5_confirm.confirmed y misma direccion que el setup.
    - None si no hay confirmacion o direccion no coincide (el setup se
      descarta pero el plan sigue vivo en STRUCTURE_OK).
    """
    if not m5_confirm.get("confirmed"):
        return None
    if m5_confirm.get("direction") != _field(setup, "direction"):
        return None
    return PlanEvent("M5", PlanVerdict.ENTRY_READY, bar_index=0)


def emit_m1(setup: dict, m1_trigger: dict) -> PlanEvent | None:
    """Optimizacion/trigger fino (M1). Ultimo filtro de timing.

    El plan ya esta en ENTRY_READY (decision de M5). M1 confirma el
    trigger fino y dispara IN_TRADE. M1 es exec TF de SB fino: NO cambia
    la direccion ni el plan, solo el momento exacto de entrada (spread/
    SL/RR/timing). Si M1 no confirma -> None (el plan se queda en
    ENTRY_READY; la entrada espera o se descarta).

    Criterio de salida de Fase 4 (bench, no FSM): M1 debe demostrar
    mejora estadistica vs M5; si no, M1 no pasa. Eso se evalúa con
    backtest comparativo, no aquí.
    """
    if not m1_trigger.get("confirmed"):
        return None
    if m1_trigger.get("direction") != _field(setup, "direction"):
        return None
    return PlanEvent("M1", PlanVerdict.IN_TRADE, bar_index=0)
