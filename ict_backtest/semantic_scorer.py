"""ict_backtest/semantic_scorer.py — Fase F: IA sobre entidades (R11 puro).

Scoring semantico de una narrativa derivado de ESTADO + NARRATIVA +
RELACIONES (MarketObjects), NO de features de vela aisladas (OHLC).

Contrato: la entrada son entidades (lista de MarketObject) + la raiz de la
narrativa. Un DataFrame de OHLC se rechaza explicitamente (TypeError): el
modelo aprende sobre el mercado modelado, no sobre velas crudas.
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from .market_object import MarketObject, ObjectState, ObjectType


class SemanticScorer:
    """Score de calidad/confianza de una narrativa sobre entidades.

    score(objects, narrative_root) -> float en [0, 1].

    El score se compone de:
      - completitud causal: la narrativa tiene raiz SWEEP y un BOS enlazado.
      - estado de las estructuras: ACTIVE/MITIGATED puntuan mas que INVALIDATED.
      - relacion: un BOS con padre (causal) puntua mas que uno suelto (ruido).
    Todo derivado de entidades, nunca de OHLC.
    """

    def score(
        self,
        objects: Sequence[MarketObject],
        narrative_root: MarketObject | None = None,
    ) -> float:
        if isinstance(objects, pd.DataFrame):
            raise TypeError(
                "SemanticScorer recibe entidades (MarketObject), no DataFrame OHLC"
            )
        objs = list(objects)
        if not objs:
            return 0.0

        root = narrative_root or objs[0]
        has_sweep_root = root.type == ObjectType.SWEEP
        bos_linked = any(
            o.type == ObjectType.BOS and o.parent_object is not None for o in objs
        )
        # Completitud causal: raiz SWEEP + BOS enlazado (narrativa, no ruido).
        completeness = 0.5 * (1.0 if has_sweep_root else 0.0) \
            + 0.5 * (1.0 if bos_linked else 0.0)

        # Estado: estructuras vivas puntuan mas que invalidadas.
        live = sum(1 for o in objs if o.state in (ObjectState.ACTIVE, ObjectState.MITIGATED))
        state_quality = live / len(objs) if objs else 0.0

        # Relacion: proporcion de objetos con padre (causalidad explícita).
        related = sum(1 for o in objs if o.parent_object is not None)
        relation_quality = related / len(objs) if objs else 0.0

        # Peso: completitud es la mitad del score; estado y relacion el resto.
        return round(
            0.5 * completeness + 0.25 * state_quality + 0.25 * relation_quality,
            4,
        )
