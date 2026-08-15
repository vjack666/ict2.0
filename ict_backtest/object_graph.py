"""ict_backtest/object_graph.py — Fase C (R10.C): grafo causal vivo.

Contenedor de MarketObjects indexado por id, con navegación por las aristas
ya existentes en MarketObject (`parent_object` / `related_objects`).

Navega por PUNTEROS (id), NUNCA por tiempo ni nº de velas. Cualquier
consulta devuelve objetos, no índices.

Interfaz consumida por Invalidators.B2: `opuesto_en(obj)`. Alias de diseño:
`opposite_in_narrative(obj)`.
"""
from __future__ import annotations

from ict_backtest.market_object import MarketObject, ObjectType


class ObjectGraph:
    """Grafo causal: mapa id -> objeto + consultas de vecindad por punteros."""

    def __init__(self) -> None:
        self._by_id: dict[str, MarketObject] = {}

    def add(self, obj: MarketObject) -> None:
        self._by_id[obj.id] = obj

    def link(self, parent: MarketObject, child: MarketObject) -> None:
        """Enlaza child a parent (sweep -> bos -> fvg).

        Arista dirigida: child.parent_object = parent.id. Los hijos de un
        nodo se derivan de que OTROS objetos tengan parent_object == su id
        (see children()). NO se escribe el padre en child.related_objects,
        para no contaminar la navegacion inversa.
        """
        child.parent_object = parent.id
        if child.id not in self._by_id:
            self._by_id[child.id] = child
        if parent.id not in self._by_id:
            self._by_id[parent.id] = parent
        # Navegacion inversa rapida: el padre lista a sus hijos.
        if child.id not in parent.related_objects:
            parent.related_objects.append(child.id)

    def get(self, oid: str) -> MarketObject | None:
        return self._by_id.get(oid)

    def parents(self, obj: MarketObject) -> list[MarketObject]:
        """Objetos de los que cuelga `obj` (padre directo)."""
        if obj.parent_object is None:
            return []
        p = self._by_id.get(obj.parent_object)
        return [p] if p is not None else []

    def children(self, obj: MarketObject) -> list[MarketObject]:
        """Objetos que cuelgan de `obj` (hijos directos)."""
        out = []
        for cid in obj.related_objects:
            c = self._by_id.get(cid)
            if c is not None and c.id != obj.id:
                out.append(c)
        return out

    def opuesto_en(self, obj: MarketObject) -> MarketObject | None:
        """BOS de dirección opuesta en el grafo (interfaz B2). Por punteros."""
        for other in self._by_id.values():
            if (
                other.id != obj.id
                and other.type == ObjectType.BOS
                and other.direction != obj.direction
            ):
                return other
        return None

    # Alias de diseño (DISENO_R10C_R11.md §4.3 / Fase C DoD).
    def opposite_in_narrative(self, obj: MarketObject) -> MarketObject | None:
        return self.opuesto_en(obj)
