"""Autoridad canónica de transición de estado para ``MarketObject``.

Este módulo es la ÚNICA pieza autorizada para transicionar FVG/OB desde su
nacimiento hasta un estado terminal. Los detectores (engine/detectors/*) solo
crean objetos en ``ACTIVE``; engine/relations los relaciona; engine/market_state
proyecta; setup_builder usa evidencia. Ninguno de ellos debe mutar ``state``.

Convención metodológica v1 (congelada por CEO/Metodología, 2026-08-28):

  * authority_tf = lifecycle_tf = origin_tf por defecto.
  * Solo se evalúa sobre velas YA CERRADAS del authority_tf, en o después de
    ``tradable_time``. Nunca se mira bar[t+1] (PIT / zero-lookahead).
  * FVG/OB PARTIAL: cualquier penetración real dentro de la zona.
  * FVG/OB CE 50%: se registra como evidencia ``CE_TOUCHED``; NO es terminal.
  * FVG/OB MITIGATED: el precio recorre la zona completa y alcanza el far_side
    (low/high de una vela ya cerrada cruza el far_side).
  * FVG/OB INVALIDATED: la vela de authority_tf CIERRA más allá del far_side.
  * Precedencia: fill completo + cierre más allá => INVALIDATED > MITIGATED.
  * EXPIRED: deshabilitado en v1 (N=None).
  * CONSUMED: deshabilitado en v1 (lo marca lineage de setup, no lifecycle).

La distinción física que importa para experimentos:
  MITIGATED  = el mercado recorrió completamente la zona.
  INVALIDATED = la estructura que justificaba la zona fue rota de forma confirmada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import pandas as pd

from engine.market_object import MarketObject, ObjectState, ObjectType


@dataclass(frozen=True)
class LifecycleDecision:
    """Resultado causal de evaluar una vela cerrada sobre un MarketObject."""

    previous_state: str
    new_state: str
    reason: str
    decision_time: Any
    source_bar: int
    penetration: float
    first_touch_bar: Optional[int]
    invalidated_bar: Optional[int]
    ce_touched: bool
    changed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "reason": self.reason,
            "decision_time": str(self.decision_time) if self.decision_time is not None else None,
            "source_bar": self.source_bar,
            "penetration": round(self.penetration, 6),
            "first_touch_bar": self.first_touch_bar,
            "invalidated_bar": self.invalidated_bar,
            "ce_touched": self.ce_touched,
            "changed": self.changed,
        }


# Far side por dirección: el lado opuesto al del desplazamiento que creó la zona.
#   bull (dir=1): zona es [first.high, third.low]; far_side = first.high (abajo).
#   bear (dir=-1): zona es [third.high, first.low]; far_side = first.low (arriba).
# El detector FVG ya guarda zone_low/zone_high con esa geometría; el far_side es
# zone_low para bull y zone_high para bear.
def _far_side(obj: MarketObject) -> float:
    return obj.zone_low if obj.direction >= 0 else obj.zone_high


def _near_side(obj: MarketObject) -> float:
    return obj.zone_high if obj.direction >= 0 else obj.zone_low


def _mid(obj: MarketObject) -> float:
    return 0.5 * (obj.zone_low + obj.zone_high)


def _bar_after_tradable(obj: MarketObject, bar_index: int, bar_time: Any) -> bool:
    """True si la vela evaluada ocurre en o después de tradable_time (PIT)."""
    if obj.tradable_bar is not None and bar_index < obj.tradable_bar:
        return False
    if obj.tradable_time is None or bar_time is None:
        return True

    tt = pd.to_datetime(obj.tradable_time, utc=True, errors="coerce")
    bt = pd.to_datetime(bar_time, utc=True, errors="coerce")
    if pd.isna(tt) or pd.isna(bt):
        return True
    return bt >= tt


def evaluate(
    market_object: MarketObject,
    closed_bar: Mapping[str, Any],
    *,
    authority_tf: Optional[str] = None,
    decision_time: Optional[Any] = None,
    allow_expired: bool = False,
    allow_consumed: bool = False,
) -> LifecycleDecision:
    """Evalúa una vela YA CERRADA y transiciona el objeto si corresponde.

    Reglas PIT:
      * No mira bar[t+1]. Solo estado(t-1) + vela cerrada(t) => estado(t).
      * Nada antes de ``tradable_time`` del objeto.
      * M15/H1 etc. solo observan; la autoridad es authority_tf (por defecto origin_tf).
        La protección de autoridad queda en el llamador (ver tests de autoridad MTF):
        si se pasa un authority_tf distinto a origin_tf, el objeto superior no debe
        ser invalidado por una vela subordinada. Aquí se asume que el llamador ya
        filtró el bar al authority_tf correcto.
    """
    obj = market_object
    if authority_tf is None:
        authority_tf = obj.origin_tf
    if decision_time is None:
        decision_time = closed_bar.get("time")

    bar_index = int(closed_bar.get("__index__", closed_bar.get("index", -1)))
    bar_time = closed_bar.get("time")
    low = float(closed_bar["low"])
    high = float(closed_bar["high"])
    close = float(closed_bar["close"])

    prev = obj.state
    mid = _mid(obj)
    far = _far_side(obj)
    near = _near_side(obj)

    # Guarda PIT: velas antes de tradable_time no tocan nada.
    if not _bar_after_tradable(obj, bar_index, bar_time):
        return LifecycleDecision(
            previous_state=prev.value, new_state=prev.value, reason="BEFORE_TRADABLE",
            decision_time=decision_time, source_bar=bar_index, penetration=0.0,
            first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
            ce_touched=bool(obj.meta.get("CE_TOUCHED", False)), changed=False,
        )

    # Penetración máxima dentro de la zona (0 si no toca).
    penetration = 0.0
    touched = (low <= obj.zone_high) and (high >= obj.zone_low)
    if touched:
        if obj.first_touch_time is None or obj.first_touch_bar is None:
            obj.first_touch_time = bar_time
            obj.first_touch_bar = bar_index
        obj.touch_count += 1
        # profundidad: qué fracción del rango de la zona fue penetrada.
        span = obj.zone_high - obj.zone_low
        if span > 0:
            if obj.direction >= 0:  # bull: penetración desde arriba (zone_high) hacia abajo
                penetration = max(0.0, min(1.0, (obj.zone_high - low) / span))
            else:  # bear: penetración desde abajo (zone_low) hacia arriba
                penetration = max(0.0, min(1.0, (high - obj.zone_low) / span))

    # Marca CE 50% como evidencia adicional (no estado terminal).
    ce_touched = bool(obj.meta.get("CE_TOUCHED", False))
    if touched and not ce_touched:
        if obj.direction >= 0:
            if low <= mid:
                ce_touched = True
        else:
            if high >= mid:
                ce_touched = True
        if ce_touched:
            obj.meta["CE_TOUCHED"] = True

    # Estado terminal: nada que hacer.
    if obj.is_terminal:
        return LifecycleDecision(
            previous_state=prev.value, new_state=prev.value, reason="ALREADY_TERMINAL",
            decision_time=decision_time, source_bar=bar_index, penetration=penetration,
            first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
            ce_touched=ce_touched, changed=False,
        )

    # FVG/OB: misma geometría, dirección invertida para simetría.
    # MITIGATED: la vela recorre completamente hasta el far_side (low/high lo cruza).
    # INVALIDATED: el cierre queda más allá del far_side.
    reached_far = (low <= far) if obj.direction >= 0 else (high >= far)
    close_beyond = (close < far) if obj.direction >= 0 else (close > far)

    new_state = prev
    reason = "NO_CHANGE"

    if reached_far and close_beyond:
        # Precedencia INVALIDATED > MITIGATED.
        new_state = ObjectState.INVALIDATED
        obj.invalidated_bar = bar_index
        obj.invalidated_time = bar_time
        reason = "INVALIDATED_FAR_SIDE_CLOSE"
    elif reached_far:
        new_state = ObjectState.MITIGATED
        reason = "MITIGATED_FULL_TRAVERSE"
    elif touched and prev is ObjectState.ACTIVE:
        new_state = ObjectState.PARTIALLY_MITIGATED
        reason = "PARTIAL_PENETRATION"

    # EXPIRED / CONSUMED deshabilitados en v1 (no se emiten nunca).
    if new_state is not prev:
        obj.transition_to(new_state)

    return LifecycleDecision(
        previous_state=prev.value, new_state=new_state.value, reason=reason,
        decision_time=decision_time, source_bar=bar_index, penetration=penetration,
        first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
        ce_touched=ce_touched, changed=(new_state is not prev),
    )


def observe_lower_tf(
    market_object: MarketObject,
    closed_bar: Mapping[str, Any],
    *,
    observed_tf: str,
    decision_time: Optional[Any] = None,
) -> LifecycleDecision:
    """Solo OBSERVA desde una temporalidad subordinada.

    No transiciona estado terminal. Registra first_touch/penetration como
    evidencia para que el authority_tf decida al cerrar. Esto materializa la
    regla OBSERVAR != MATAR: un M15 puede tocar un OB H4, pero no lo invalida.
    """
    obj = market_object
    if decision_time is None:
        decision_time = closed_bar.get("time")
    bar_index = int(closed_bar.get("__index__", closed_bar.get("index", -1)))
    bar_time = closed_bar.get("time")
    low = float(closed_bar["low"])
    high = float(closed_bar["high"])

    if not _bar_after_tradable(obj, bar_index, bar_time):
        return LifecycleDecision(
            previous_state=obj.state.value, new_state=obj.state.value, reason="BEFORE_TRADABLE",
            decision_time=decision_time, source_bar=bar_index, penetration=0.0,
            first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
            ce_touched=bool(obj.meta.get("CE_TOUCHED", False)), changed=False,
        )

    touched = (low <= obj.zone_high) and (high >= obj.zone_low)
    penetration = 0.0
    if touched:
        if obj.first_touch_time is None or obj.first_touch_bar is None:
            obj.first_touch_time = bar_time
            obj.first_touch_bar = bar_index
        obj.touch_count += 1
        obj.meta.setdefault("observed_touches", []).append(
            {"tf": observed_tf, "bar": bar_index, "penetration": None}
        )
        span = obj.zone_high - obj.zone_low
        if span > 0:
            if obj.direction >= 0:
                penetration = max(0.0, min(1.0, (obj.zone_high - low) / span))
            else:
                penetration = max(0.0, min(1.0, (high - obj.zone_low) / span))
        if obj.meta.get("observed_touches"):
            obj.meta["observed_touches"][-1]["penetration"] = round(penetration, 6)

    # No cambia estado físico; solo lineage de observación.
    return LifecycleDecision(
        previous_state=obj.state.value, new_state=obj.state.value, reason="OBSERVED_ONLY",
        decision_time=decision_time, source_bar=bar_index, penetration=penetration,
        first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
        ce_touched=bool(obj.meta.get("CE_TOUCHED", False)), changed=False,
    )


__all__ = ["evaluate", "observe_lower_tf", "LifecycleDecision"]
