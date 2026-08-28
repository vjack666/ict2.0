"""Market State — proyección event-sourced del universo de MarketObjects.

Este módulo es la capa inmediatamente superior a ``engine.lifecycle``. Donde
lifecycle decide el destino de UN objeto, MarketState responde las preguntas
que el auditor exigió como criterio de cierre:

  * ¿Qué objetos existen ahora?
  * ¿Cuándo nacieron? / ¿En qué TF nacieron?
  * ¿Cuál sigue activo? / ¿Cuál fue mitigado? / ¿Cuál murió?
  * ¿Quién tuvo autoridad para matarlo?
  * ¿Qué objetos HTF contienen objetos LTF?
  * ¿Qué eventos LTF están refinando qué contexto HTF?

Diseno (event-sourcing, sin repaint):
  - Los objetos se INGESTAN una sola vez (nacimiento). En el nacimiento se
    registra una transición fundacional (prev=None -> estado inicial).
  - Se AVANZAN vela a vela con ``advance_bar`` (delega en lifecycle.evaluate /
    observe_lower_tf, respetando la autoridad por TF). Cada vez que el estado
    OFICIAL del objeto cambia, se registra una transición
    ``(timestamp, bar_index, tf, prev_state, new_state)`` en una línea temporal
    INMUTABLE y append-only por objeto.
  - ``snapshot_at(T)`` NO retrocede el estado y NO mira el futuro: reconstruye
    el mundo conocido en o antes de T haciendo replay de la línea temporal de
    cada objeto (último estado conocido <= T).
  - ``objects_existing_at(T)`` / ``projection_at(T)`` devuelven PROYECCIONES
    HISTÓRICAS: copias profundas de cada objeto con su ``state`` congelado en T.
    Jamás devuelven referencias vivas al objeto actual (evita look-ahead).
  - Toda lectura es DETERMINISTA y CAUSAL: no mira velas futuras.

El visor (replay) puede parar en cualquier T y preguntar exactamente "el mundo
que el motor conocia en ese instante", sin que un estado futuro contamine la
respuesta.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional

from engine.lifecycle import evaluate, observe_lower_tf
from engine.market_object import MarketObject, ObjectState


def _as_utc(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    try:
        from pandas import to_datetime
        dt = to_datetime(ts, utc=True, errors="coerce")
        return None if (dt is None or getattr(dt, "tzinfo", None) is None and dt is None) else dt
    except Exception:
        return None


@dataclass(frozen=True)
class StateTransition:
    """Un salto de estado causal de UN objeto en un instante concreto.

    Línea temporal inmutable: prev_state=None solo en el nacimiento fundacional.
    """

    timestamp: Any
    bar_index: Optional[int]
    tf: Optional[str]
    prev_state: Optional[ObjectState]
    new_state: ObjectState

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": str(self.timestamp) if self.timestamp is not None else None,
            "bar_index": self.bar_index,
            "tf": self.tf,
            "prev_state": (
                self.prev_state.value
                if isinstance(self.prev_state, ObjectState)
                else self.prev_state
            ),
            "new_state": (
                self.new_state.value
                if isinstance(self.new_state, ObjectState)
                else self.new_state
            ),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StateTransition":
        prev = d.get("prev_state")
        new = d.get("new_state")
        return cls(
            timestamp=d.get("timestamp"),
            bar_index=d.get("bar_index"),
            tf=d.get("tf"),
            prev_state=ObjectState(prev) if prev is not None else None,
            new_state=ObjectState(new),
        )


class MarketState:
    """Universo coherente de MarketObjects con identidad, autoridad y lineage."""

    def __init__(self) -> None:
        self._objects: dict[str, MarketObject] = {}
        # Línea temporal causal e inmutable por objeto (append-only).
        self._history: dict[str, list[StateTransition]] = {}
        # OE-03 / H7: registro del último instante procesado por reloj de TF.
        # Si llega una vela con time/bar_index MENOR al ya visto en esa TF,
        # se rechaza fail-closed (no se reorganiza el pasado silenciosamente).
        self._last_seen: dict[str, tuple[Optional[datetime], Optional[int]]] = {}
        self._out_of_order_events: list[dict[str, Any]] = []

    # --- Ingesta (nacimiento) ------------------------------------------------
    def _add_object(self, obj: MarketObject) -> MarketObject:
        """Registra el objeto sin tocar la historia (usado por from_dict)."""
        self._objects[obj.id] = obj
        self._history.setdefault(obj.id, [])
        return obj

    def ingest(self, obj: MarketObject) -> MarketObject:
        """Registra un objeto recien nacido. Idempotente por id.

        Registra la transición fundacional (prev=None -> estado inicial) usando
        creation_time como sello temporal del nacimiento.
        """
        if obj.id in self._objects:
            return self._objects[obj.id]
        self._objects[obj.id] = obj
        self._record_transition(
            obj.id, obj.creation_time, obj.bar_index, obj.authority_tf, None, obj.state
        )
        return obj

    def add(self, obj: MarketObject) -> MarketObject:
        return self.ingest(obj)

    # --- Historia causal (append-only, inmutable) ----------------------------
    def _record_transition(
        self,
        obj_id: str,
        timestamp: Any,
        bar_index: Optional[int],
        tf: Optional[str],
        prev: Optional[ObjectState],
        new: ObjectState,
    ) -> None:
        self._history.setdefault(obj_id, []).append(
            StateTransition(
                timestamp=timestamp,
                bar_index=bar_index,
                tf=tf,
                prev_state=prev,
                new_state=new,
            )
        )

    def history_of(self, obj_id: str) -> list[StateTransition]:
        """Línea temporal de transiciones de un objeto (copia, no editable)."""
        return list(self._history.get(obj_id, []))

    # --- Avance causal vela a vela ------------------------------------------
    def advance_bar(
        self,
        obj_id: str,
        bar: Mapping[str, Any],
        *,
        observed_tf: Optional[str] = None,
    ) -> None:
        """Avanza el lifecycle del objeto con una vela cerrada de su authority_tf.

        Si se pasa ``observed_tf`` (subordinado), la vela se trata como
        OBSERVACION (no cambia estado oficial). Si no, se asume que la vela
        pertenece al authority_tf del objeto y decide estado.

        Tras la decisión de lifecycle, si el estado OFICIAL cambió, se registra
        una transición causal en la línea temporal del objeto.
        """
        obj = self._objects.get(obj_id)
        if obj is None:
            return
        # OE-03 / H7: guarda fail-closed contra datos fuera de orden.
        # El reloj que rige es el de la TF que decide/observa, no el origin_tf.
        tf = observed_tf if observed_tf is not None else obj.authority_tf
        bar_time = _as_utc(bar.get("time"))
        bar_idx = bar.get("__index__", bar.get("index"))
        bar_idx = int(bar_idx) if isinstance(bar_idx, (int, float)) else None
        if self._is_out_of_order(tf, bar_time, bar_idx):
            self._out_of_order_events.append(
                {
                    "obj_id": obj_id,
                    "tf": tf,
                    "bar_time": str(bar_time) if bar_time is not None else None,
                    "bar_index": bar_idx,
                    "reason": "OUT_OF_ORDER",
                }
            )
            raise ValueError(
                f"advance_bar rechazado (OUT_OF_ORDER): tf={tf} recibió barra "
                f"time={bar_time} index={bar_idx} anterior al último instante "
                f"procesado en esa TF; no se reescribe el pasado (contrato H7 fail-closed)."
            )
        prev = obj.state
        if observed_tf is not None:
            observe_lower_tf(obj, bar, observed_tf=observed_tf)
        else:
            evaluate(obj, bar, authority_tf=obj.authority_tf)
        new = obj.state
        if new != prev:
            ts = bar.get("time")
            bi = bar.get("__index__", bar.get("index"))
            self._record_transition(obj_id, ts, bi, tf, prev, new)
        # Avanza el reloj de la TF sólo si la barra fue aceptada.
        self._update_last_seen(tf, bar_time, bar_idx)

    def observe(self, obj_id: str, bar: Mapping[str, Any], *, observed_tf: str) -> None:
        obj = self._objects.get(obj_id)
        if obj is None:
            return
        observe_lower_tf(obj, bar, observed_tf=observed_tf)
        # La observación LTF no cambia el estado oficial => no hay transición.

    # --- OE-03 / H7: reloj de TF y guarda fail-closed ------------------------
    def _is_out_of_order(
        self, tf: str, bar_time: Optional[datetime], bar_idx: Optional[int]
    ) -> bool:
        """True si la barra llega antes del último instante visto en `tf`.

        El reloj de cada TF es independiente: una vela M15 atrasada no
        invalida la historia H4, pero sí debe rechazarse dentro de su propio
        reloj. Si falta timestamp Y bar_index no podemos ordenar => no
        rechazamos (no inventamos causalidad por omisión).
        """
        if bar_time is None and bar_idx is None:
            return False
        last_time, last_idx = self._last_seen.get(tf, (None, None))
        if last_time is None and last_idx is None:
            return False
        if bar_time is not None and last_time is not None:
            if bar_time < last_time:
                return True
            if bar_time == last_time:
                # mismo instante: desempata por bar_index si existe
                if bar_idx is not None and last_idx is not None and bar_idx < last_idx:
                    return True
                return False
            return False
        # solo bar_index disponible en ambos
        if bar_idx is not None and last_idx is not None and bar_idx < last_idx:
            return True
        return False

    def _update_last_seen(
        self, tf: str, bar_time: Optional[datetime], bar_idx: Optional[int]
    ) -> None:
        """Avanza el reloj de `tf` al instante más reciente visto (no retrocede)."""
        last_time, last_idx = self._last_seen.get(tf, (None, None))
        if bar_time is not None and (last_time is None or bar_time > last_time):
            last_time = bar_time
        if bar_idx is not None and (last_idx is None or bar_idx > last_idx):
            last_idx = bar_idx
        self._last_seen[tf] = (last_time, last_idx)

    def out_of_order_events(self) -> list[dict[str, Any]]:
        """Registro evidence de eventos fuera de orden rechazados (OE-03)."""
        return list(self._out_of_order_events)

    # --- Replay causal (state-at / projection) ------------------------------
    def state_at(self, obj_id: str, t: Any) -> Optional[ObjectState]:
        """Estado OFICIAL del objeto en o antes de T (replay de la línea temporal).

        Devuelve el ``new_state`` de la ÚLTIMA transición cuya marca temporal sea
        ``<= T`` (una transición fundacional sin sello se trata como baseline).
        Si no hay historia, devuelve None.
        """
        hist = self._history.get(obj_id)
        if not hist:
            return None
        tt = _as_utc(t)
        chosen: Optional[StateTransition] = None
        for tr in hist:
            trt = _as_utc(tr.timestamp)
            if trt is None:
                considered = True  # nacimiento: baseline siempre válido
            else:
                considered = (tt is None) or (trt <= tt)
            if considered:
                chosen = tr
            else:
                break
        return chosen.new_state if chosen is not None else None

    def projection_at(self, t: Any) -> dict[str, MarketObject]:
        """Proyecciones históricas de todos los objetos existentes en o antes de T.

        Devuelve COPIAS PROFUNDAS con ``state`` congelado en T. No son
        referencias vivas: mutar el objeto actual no las afecta (sin look-ahead).
        """
        tt = _as_utc(t)
        out: dict[str, MarketObject] = {}
        for oid, obj in self._objects.items():
            ct = _as_utc(obj.creation_time)
            if tt is not None and ct is not None and ct > tt:
                continue  # aún no nacía en T
            s = self.state_at(oid, t)
            if s is None:
                continue
            proj = deepcopy(obj)
            proj.state = s
            out[oid] = proj
        return out

    def objects_existing_at(self, t: Any) -> list[MarketObject]:
        """Objetos que ya habian nacido en o antes de T, como PROYECCIONES.

        Copias profundas con el ``state`` en T. Nunca referencias vivas.
        """
        return list(self.projection_at(t).values())

    # --- Queries deterministas (criterio de certificacion del auditor) ------
    def all_objects(self) -> list[MarketObject]:
        return list(self._objects.values())

    def born_in_tf(self, tf: str) -> list[MarketObject]:
        return [o for o in self._objects.values() if o.origin_tf == tf]

    def active(self) -> list[MarketObject]:
        return [o for o in self._objects.values() if o.state == ObjectState.ACTIVE]

    def partially_mitigated(self) -> list[MarketObject]:
        return [o for o in self._objects.values() if o.state == ObjectState.PARTIALLY_MITIGATED]

    def mitigated(self) -> list[MarketObject]:
        return [o for o in self._objects.values() if o.state == ObjectState.MITIGATED]

    def dead(self) -> list[MarketObject]:
        """Objetos en estado terminal (INVALIDATED / EXPIRED / CONSUMED)."""
        return [o for o in self._objects.values() if o.is_terminal]

    def by_state(self, state: ObjectState) -> list[MarketObject]:
        return [o for o in self._objects.values() if o.state == state]

    def authority_of(self, obj_id: str) -> Optional[str]:
        obj = self._objects.get(obj_id)
        return obj.authority_tf if obj is not None else None

    def htf_contains_ltf(self, parent_id: str) -> list[MarketObject]:
        """Hijos (objetos LTF contenidos) de un objeto HTF dado."""
        parent = self._objects.get(parent_id)
        if parent is None:
            return []
        out = []
        for o in self._objects.values():
            if o.parent_object == parent_id:
                out.append(o)
            elif parent_id in o.related_objects:
                if parent.origin_tf in ("D1", "H4", "H1") and o.origin_tf in ("H1", "M15", "M5", "M1"):
                    out.append(o)
        return out

    def ltf_refines_htf(self, child_id: str) -> Optional[MarketObject]:
        """El objeto HTF que contiene / da contexto a un objeto LTF dado."""
        child = self._objects.get(child_id)
        if child is None or not child.parent_object:
            return None
        return self._objects.get(child.parent_object)

    def snapshot_at(self, t: Any) -> dict[str, Any]:
        """Estado del mundo conocido hasta T (replay causal, sin repaint).

        Reconstruye el resumen a partir de las PROYECCIONES históricas: los
        conteos y listas de ids reflejan el estado de cada objeto EN o antes de
        T, no el estado actual del motor. Es lo que el visor de replay consume
        al detenerse en la vela T.
        """
        projections = self.projection_at(t)
        counts: dict[str, int] = {s.value: 0 for s in ObjectState}
        for p in projections.values():
            counts[p.state.value] += 1
        return {
            "as_of": str(t),
            "existing": len(projections),
            "counts": counts,
            "active_ids": [oid for oid, p in projections.items() if p.state == ObjectState.ACTIVE],
            "dead_ids": [oid for oid, p in projections.items() if p.is_terminal],
        }

    # API para consumidores que necesitan el snapshot proyectado (p.ej. build_setups_at).
    def build_setups_at(self, t: Any) -> list[MarketObject]:
        """Proyecciones históricas en T listas para ser consumidas por el builder."""
        return self.objects_existing_at(t)

    # --- Round-trip JSON (preserva authority_tf, observaciones, historia) ----
    def to_dict(self) -> dict[str, Any]:
        return {
            "objects": [o.to_dict() for o in self._objects.values()],
            "history": {
                oid: [tr.to_dict() for tr in hist]
                for oid, hist in self._history.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MarketState":
        ms = cls()
        for od in d.get("objects", []):
            obj = MarketObject.from_dict(od)
            ms._add_object(obj)  # no duplica la transición fundacional
        for oid, trs in d.get("history", {}).items():
            ms._history[oid] = [StateTransition.from_dict(tr) for tr in trs]
        return ms


__all__ = ["MarketState", "StateTransition"]
