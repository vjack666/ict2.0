"""Autoridad canónica de transición de estado para ``MarketObject``.

Este módulo es la ÚNICA pieza autorizada para transicionar FVG/OB desde su
nacimiento hasta un estado terminal. Los detectores (engine/detectors/*) solo
crean objetos en ``ACTIVE``; engine/relations los relaciona; engine/market_state
proyecta; setup_builder usa evidencia. Ninguno de ellos debe mutar ``state``.

Convención metodológica v1 (congelada por CEO/Metodología, 2026-08-28), y
corregida por auditoría independiente (Codex, NEEDS REVISION 2026-08-28):

  * authority_tf = lifecycle_tf = origin_tf por defecto.
  * GARANTÍA DE MOTOR: ``evaluate()`` RECHAZA authority_tf != obj.authority_tf.
    Un objeto H4 no puede ser invalidado por una vela M15. La protección ya no
    depende del caller (ese era el defecto de la v1 inicial).
  * Solo se evalúa sobre velas YA CERRADAS del authority_tf, en o después de
    ``tradable_time``. Nunca se mira bar[t+1] (PIT / zero-lookahead).
  * FVG/OB PARTIAL: cualquier penetración real dentro de la zona.
  * FVG/OB CE 50%: se registra como evidencia ``CE_TOUCHED``; NO es terminal.
  * FVG/OB MITIGATED: el precio recorre la zona completa y alcanza el far_side.
  * FVG/OB INVALIDATED: la vela de authority_tf CIERRA más allá del far_side.
  * Precedencia: fill completo + cierre más allá => INVALIDATED > MITIGATED.
  * EXPIRED: deshabilitado en v1 (N=None).
  * CONSUMED: deshabilitado en v1 (lo marca lineage de setup, no lifecycle).

Separación estricta OBSERVACIÓN (LTF) vs ESTADO OFICIAL (authority_tf):
  * ``observe_lower_tf`` NO toca ``first_touch_bar``/``first_touch_time``/
    ``touch_count`` canónicos. Esos son del lifecycle oficial (authority_tf).
    La observación LTF se guarda en ``obj.meta["observations"][tf]``.
  * Idempotencia real: toda transición se deduplica por
    ``event_key = object_id | tf | candle_close_time | event_type`` (en
    ``obj.meta["_seen_events"]``). Reprocesar la misma vela no incrementa
    ``touch_count`` ni duplica observación.

La distinción física que importa para experimentos:
  MITIGATED  = el mercado recorrió completamente la zona.
  INVALIDATED = la estructura que justificaba la zona fue rota de forma confirmada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import pandas as pd


# Jerarquía de temporalidades (alto contexto -> ejecución). Usada para la
# regla OE-04 / H8: una TF solo puede OBSERVAR a otra ESTRICTAMENTE inferior.
_TF_RANK = {
    "D1": 6,
    "H4": 5,
    "H1": 4,
    "M15": 3,
    "M5": 2,
    "M1": 1,
}


def _tf_rank(tf: str) -> int:
    """Rango numérico de la TF (mayor = más contexto). -1 si desconocida."""
    return _TF_RANK.get(tf, -1)


def _is_strictly_lower_tf(observed_tf: str, reference_tf: str) -> bool:
    """OE-04 / H8: observed_tf es ESTRICTAMENTE subordinada a reference_tf."""
    o, r = _tf_rank(observed_tf), _tf_rank(reference_tf)
    if o < 0 or r < 0:
        return False
    return o < r

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
def _far_side(obj: MarketObject) -> float:
    return obj.zone_low if obj.direction >= 0 else obj.zone_high


def _near_side(obj: MarketObject) -> float:
    return obj.zone_high if obj.direction >= 0 else obj.zone_low


def _mid(obj: MarketObject) -> float:
    return 0.5 * (obj.zone_low + obj.zone_high)


def _bar_after_tradable(obj: MarketObject, bar_index: int, bar_time: Any) -> bool:
    """True si la vela evaluada ocurre en o después de ``tradable_time`` (PIT).

    CONTRATO POR TIMESTAMP (Corrección temporal LTF/HTF — Codex H4): la frontera
    PIT se decide EXCLUSIVAMENTE por timestamp. NUNCA se compara ``bar_index``
    contra ``obj.tradable_bar`` cuando pertenecen a temporalidades distintas:
    un índice M15 no es comparable con un índice H4 (la vela M15 que sigue por
    timestamp podría tener un índice menor que el objeto H4 y descartarse como
    BEFORE_TRADABLE de forma errónea). Como dentro de UNA MISMA tf el orden de
    índices equivale al orden de timestamps, prescindir de la comparación por
    índice no pierde información y elimina el riesgo cross-TF. Fail-closed: sin
    timestamp válido no se asume "después" — el llamador ya rechaza la vela por
    identidad incompleta antes de llegar aquí.
    """
    if bar_time is None:
        return False
    if obj.tradable_time is None:
        return True
    tt = pd.to_datetime(obj.tradable_time, utc=True, errors="coerce")
    bt = pd.to_datetime(bar_time, utc=True, errors="coerce")
    if pd.isna(tt) or pd.isna(bt):
        return False
    return bt >= tt


def _event_key(tf: str, bar_time: Any, bar_index: int, event_type: str) -> str:
    """Clave de deduplicación idempotente por objeto + tf + vela + tipo.

    IDENTIDAD FAIL-CLOSED (auditoría continuación, garantía 3): si no hay una
    identidad temporal válida (bar_time o bar_index), NO se fabrica una clave
    que colapse velas distintas. El llamador debe rechazar la vela antes de
    llegar aquí (ver ``evaluate``), no silenciar el descarte.
    """
    if bar_time is None:
        raise ValueError("event_key requiere bar_time no-None (identidad temporal)")
    if bar_index is None or bar_index < 0:
        raise ValueError("event_key requiere bar_index válido (identidad de vela)")
    return f"{tf}|{bar_time}|{bar_index}|{event_type}"


def _already_seen(obj: MarketObject, key: str) -> bool:
    seen = obj.meta.setdefault("_seen_events", set())
    if key in seen:
        return True
    seen.add(key)
    return False


def evaluate(
    market_object: MarketObject,
    closed_bar: Mapping[str, Any],
    *,
    authority_tf: Optional[str] = None,
    decision_time: Optional[Any] = None,
    allow_expired: bool = False,
    allow_consumed: bool = False,
) -> LifecycleDecision:
    """Evalúa una vela YA CERRADA del authority_tf y transiciona el objeto.

    GARANTÍA DE MOTOR (auditoría NEEDS REVISION, punto 1): si se pasa un
    ``authority_tf`` distinto de ``obj.authority_tf``, se rechaza. El caller no
    puede hacer que un objeto H4 sea invalidado por una vela M15.

    Reglas PIT:
      * No mira bar[t+1]. Solo estado(t-1) + vela cerrada(t) => estado(t).
      * Nada antes de ``tradable_time`` del objeto.
      * Idempotente: doble proceso de la misma vela => mismo resultado, sin
        efectos secundarios duplicados.
    """
    obj = market_object
    if authority_tf is None:
        authority_tf = obj.authority_tf
    # Protección de autoridad (auditoría NEEDS REVISION, punto 1): el motor la
    # exige, no confía en el caller. Un objeto H4 no puede ser invalidado por una
    # vela de otro TF.
    if authority_tf != obj.authority_tf:
        raise ValueError(
            f"evaluate() rechazado: authority_tf={authority_tf} != obj.authority_tf="
            f"{obj.authority_tf}. La autoridad de transición debe coincidir con el origen "
            f"(contrato MTF explícito requerido para delegar autoridad)."
        )
    if decision_time is None:
        decision_time = closed_bar.get("time")

    bar_index = int(closed_bar.get("__index__", closed_bar.get("index", -1)))
    bar_time = closed_bar.get("time")
    low = float(closed_bar["low"])
    high = float(closed_bar["high"])
    close = float(closed_bar["close"])

    # GARANTÍA DE FALSIFICACIÓN TF (auditoría continuación, garantía 1): la vela
    # cerrada debe LLEVAR tf explícito y ser EXACTAMENTE authority_tf. Un caller
    # no puede pasar authority_tf="H4" con una barra M15 (ni omitir tf) y esperar
    # que decida el estado oficial. Fail-closed: tf ausente => rechazo.
    bar_tf = closed_bar.get("tf")
    if bar_tf is None or bar_tf != authority_tf:
        raise ValueError(
            f"evaluate() rechazado: la vela cerrada requiere tf={authority_tf} explícito "
            f"(recibido tf={bar_tf}); SOLO una vela de {authority_tf} cerrada puede "
            f"cambiar el estado oficial (contrato MTF fail-closed)."
        )
    # IDENTIDAD FAIL-CLOSED (garantía 3): si la vela no tiene identidad temporal
    # confiable, no evaluamos (mejor rechazar que inventar causalidad).
    if bar_time is None or bar_index < 0:
        raise ValueError(
            f"evaluate() rechazado: vela sin identidad temporal (time={bar_time}, "
            f"index={bar_index}); no se puede procesar de forma causal."
        )

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

    # Idempotencia: esta vela ya fue procesada por la autoridad.
    ev_key = _event_key(authority_tf, bar_time, bar_index, "EVALUATE")
    if _already_seen(obj, ev_key):
        return LifecycleDecision(
            previous_state=prev.value, new_state=prev.value, reason="ALREADY_PROCESSED",
            decision_time=decision_time, source_bar=bar_index, penetration=0.0,
            first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
            ce_touched=bool(obj.meta.get("CE_TOUCHED", False)), changed=False,
        )

    # Penetración máxima dentro de la zona (0 si no toca). Metadatos OFICIALES.
    penetration = 0.0
    touched = (low <= obj.zone_high) and (high >= obj.zone_low)
    if touched:
        if obj.first_touch_time is None or obj.first_touch_bar is None:
            obj.first_touch_time = bar_time
            obj.first_touch_bar = bar_index
        obj.touch_count += 1
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
    """OBSERVA desde una temporalidad subordinada SIN tocar el estado oficial.

    Materializa OBSERVAR != MATAR: un M15 puede registrar toques sobre un OB H4,
    pero NO muta ``first_touch_bar``/``first_touch_time``/``touch_count`` canónicos
    (esos pertenecen al lifecycle de authority_tf). La observación se acumula en
    ``obj.meta["observations"][observed_tf]`` y es idempotente por event_key.
    """
    obj = market_object
    if decision_time is None:
        decision_time = closed_bar.get("time")
    bar_index = int(closed_bar.get("__index__", closed_bar.get("index", -1)))
    bar_time = closed_bar.get("time")
    low = float(closed_bar["low"])
    high = float(closed_bar["high"])

    # GARANTÍA DE FALSIFICACIÓN TF (Codex H4): la vela observada debe pertenecer
    # EXACTAMENTE a observed_tf. Un H4 no puede registrarse como observación M15.
    bar_tf = closed_bar.get("tf")
    if bar_tf is None or bar_tf != observed_tf:
        raise ValueError(
            f"observe_lower_tf() rechazado: la vela cerrada requiere tf={observed_tf} "
            f"explícito (recibido tf={bar_tf}); un objeto de otra temporalidad no puede "
            f"registrarse como observación {observed_tf} (contrato MTF fail-closed)."
        )

    # OE-04 / H8: solo una TF ESTRICTAMENTE subordinada puede observar. Ni la
    # propia TF (H4 observando H4) ni una superior (D1 observando H4) entran.
    # Observar != gobernar: la autoridad de transición queda en obj.authority_tf.
    if not _is_strictly_lower_tf(observed_tf, obj.origin_tf):
        raise ValueError(
            f"observe_lower_tf() rechazado: observed_tf={observed_tf} no es "
            f"estrictamente subordinada a origin_tf={obj.origin_tf} "
            f"(jerarquía D1>H4>H1>M15>M5>M1); una TF no se observa a sí misma ni "
            f"una superior observa a una inferior (contrato MTF fail-closed)."
        )

    # IDENTIDAD FAIL-CLOSED: observación sin identidad temporal confiable se
    # rechaza (no se descarta silenciosamente, no se fabrica clave colapsada).
    if bar_time is None or bar_index < 0:
        raise ValueError(
            f"observe_lower_tf() rechazado: vela sin identidad temporal (time={bar_time}, "
            f"index={bar_index}); no se puede observar de forma causal."
        )

    if not _bar_after_tradable(obj, bar_index, bar_time):
        return LifecycleDecision(
            previous_state=obj.state.value, new_state=obj.state.value, reason="BEFORE_TRADABLE",
            decision_time=decision_time, source_bar=bar_index, penetration=0.0,
            first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
            ce_touched=bool(obj.meta.get("CE_TOUCHED", False)), changed=False,
        )

    # Idempotencia de observación (separada de la del lifecycle oficial).
    ev_key = _event_key(observed_tf, bar_time, bar_index, "OBSERVE")
    if _already_seen(obj, ev_key):
        return LifecycleDecision(
            previous_state=obj.state.value, new_state=obj.state.value, reason="OBSERVED_ONLY",
            decision_time=decision_time, source_bar=bar_index, penetration=0.0,
            first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
            ce_touched=bool(obj.meta.get("CE_TOUCHED", False)), changed=False,
        )

    touched = (low <= obj.zone_high) and (high >= obj.zone_low)
    penetration = 0.0
    if touched:
        span = obj.zone_high - obj.zone_low
        if span > 0:
            if obj.direction >= 0:
                penetration = max(0.0, min(1.0, (obj.zone_high - low) / span))
            else:
                penetration = max(0.0, min(1.0, (high - obj.zone_low) / span))
        obs = obj.meta.setdefault("observations", {})
        obs.setdefault(observed_tf, []).append(
            {"bar": bar_index, "time": str(bar_time), "penetration": round(penetration, 6)}
        )

    # No cambia estado físico ni metadatos oficiales de lifecycle.
    return LifecycleDecision(
        previous_state=obj.state.value, new_state=obj.state.value, reason="OBSERVED_ONLY",
        decision_time=decision_time, source_bar=bar_index, penetration=penetration,
        first_touch_bar=obj.first_touch_bar, invalidated_bar=obj.invalidated_bar,
        ce_touched=bool(obj.meta.get("CE_TOUCHED", False)), changed=False,
    )


__all__ = ["evaluate", "observe_lower_tf", "LifecycleDecision"]
