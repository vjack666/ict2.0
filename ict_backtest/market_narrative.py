"""ict_backtest/market_narrative.py — Fase D (R10.C): narrativa viva.

Agrupa una cadena causal del ObjectGraph (sweep -> BOS -> FVG) en una
"sola historia de precio coherente". Un objeto que no pertenece a ninguna
narrativa VIGENTE es RUIDO (no produce senal).

No usa tiempo ni nº de velas: la pertenencia es por navegacion de grafo
(punteros), y la vigencia por el estado semantico del MarketObject.
"""
from __future__ import annotations

from ict_backtest.market_object import MarketObject, ObjectState
from ict_backtest.object_graph import ObjectGraph


class MarketNarrative:
    """Una historia de precio coherente: raiz + descendencia del grafo."""

    def __init__(self, root: MarketObject, members: list[MarketObject]) -> None:
        self.root = root
        self._members = {m.id: m for m in members}

    @classmethod
    def from_root(cls, graph: ObjectGraph, root: MarketObject) -> "MarketNarrative":
        """Construye la narrativa absorbiendo la descendencia causal de root."""
        members: list[MarketObject] = [root]
        seen = {root.id}
        stack = [root]
        while stack:
            node = stack.pop()
            for child in graph.children(node):
                if child.id not in seen:
                    seen.add(child.id)
                    members.append(child)
                    stack.append(child)
        return cls(root, members)

    def contains(self, obj: MarketObject) -> bool:
        return obj.id in self._members

    def is_active(self) -> bool:
        """Vigente si la raiz no fue invalidada ni consumida."""
        return self.root.state not in (ObjectState.INVALIDATED, ObjectState.CONSUMED)

    def signal_objects(self) -> list[MarketObject]:
        """Candidatos a senal: miembros en estado activo/mitigado."""
        return [
            m
            for m in self._members.values()
            if m.state in (ObjectState.ACTIVE, ObjectState.MITIGATED)
        ]

    @staticmethod
    def is_noise(obj: MarketObject, narratives: list["MarketNarrative"]) -> bool:
        """True si el objeto no pertenece a ninguna narrativa vigente."""
        for narr in narratives:
            if narr.is_active() and narr.contains(obj):
                return False
        return True
