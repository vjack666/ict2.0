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
  - Los objetos se INGESTAN una sola vez (nacimiento).
  - Se AVANZAN vela a vela con ``advance_bar`` (delega en lifecycle.evaluate /
    observe_lower_tf, respetando la autoridad por TF).
  - ``snapshot_at(T)`` NO retrocede el estado: cada objeto conserva su ultimo
    estado conocido hasta T (append-only timeline). Reconstruir en T consiste
    en filtrar por ``creation_time <= T`` y usar el estado que lifecycle dejo
    en esa objeto (que ya es causal y forward-PIT).
  - Toda lectura es DETERMINISTA y CAUSAL: no mira velas futuras.

El visor (replay) puede parar en cualquier T y preguntar exactamente "el mundo
que el motor conocia en ese instante".
"""

from __future__ import annotations

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
        return None if dt is None or getattr(dt, "tzinfo", None) is None and dt is None else dt
    except Exception:
        return None


class MarketState:
    """Universo coherente de MarketObjects con identidad, autoridad y lineage."""

    def __init__(self) -> None:
        self._objects: dict[str, MarketObject] = {}

    # --- Ingesta (nacimiento) ------------------------------------------------
    def ingest(self, obj: MarketObject) -> MarketObject:
        """Registra un objeto recien nacido. Idempotente por id."""
        if obj.id in self._objects:
            return self._objects[obj.id]
        self._objects[obj.id] = obj
        return obj

    def add(self, obj: MarketObject) -> MarketObject:
        return self.ingest(obj)

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
        """
        obj = self._objects.get(obj_id)
        if obj is None:
            return
        if observed_tf is not None:
            observe_lower_tf(obj, bar, observed_tf=observed_tf)
        else:
            evaluate(obj, bar, authority_tf=obj.authority_tf)

    def observe(self, obj_id: str, bar: Mapping[str, Any], *, observed_tf: str) -> None:
        obj = self._objects.get(obj_id)
        if obj is None:
            return
        observe_lower_tf(obj, bar, observed_tf=observed_tf)

    # --- Queries deterministas (criterio de certificacion del auditor) ------
    def all_objects(self) -> list[MarketObject]:
        return list(self._objects.values())

    def objects_existing_at(self, t: Any) -> list[MarketObject]:
        """Objetos que ya habian nacido en o antes de T (append-only)."""
        tt = _as_utc(t)
        if tt is None:
            return list(self._objects.values())
        out = []
        for o in self._objects.values():
            ct = _as_utc(o.creation_time)
            if ct is not None and ct <= tt:
                out.append(o)
        return out

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
                # relacion explicita cuenta como contencion si el padre es HTF.
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
        """Estado del mundo conocido hasta T (sin repaint hacia atras).

        Devuelve un resumen inspectable: conteos por estado y listas de ids.
        Es lo que el visor de replay consume al detenerse en la vela T.
        """
        existing = self.objects_existing_at(t)
        counts: dict[str, int] = {s.value: 0 for s in ObjectState}
        for o in existing:
            counts[o.state.value] += 1
        return {
            "as_of": str(t),
            "existing": len(existing),
            "counts": counts,
            "active_ids": [o.id for o in existing if o.state == ObjectState.ACTIVE],
            "dead_ids": [o.id for o in existing if o.is_terminal],
        }

    def to_dict(self) -> dict[str, Any]:
        return {"objects": [o.to_dict() for o in self._objects.values()]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MarketState":
        ms = cls()
        for od in d.get("objects", []):
            ms.ingest(MarketObject.from_dict(od))
        return ms


__all__ = ["MarketState"]
