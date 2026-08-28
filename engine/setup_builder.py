"""Modelo de datos del Setup Builder (SDD §13.2).

Este módulo define ÚNICAMENTE la entidad de datos ``Setup`` y su estado de
elegibilidad ``SetupEligibility``. NO contiene lógica de composición: la
construcción de un setup a partir de MarketObjects (contexto, POI,
refinamiento, confirmación, trigger) la realiza otro agente / módulo.

Invariantes del modelo (ver brief de Agente 1):
- El ``Setup`` NO altera ``object_state`` de ningún ``MarketObject`` que
  referencia; solo lectura. La línea de linaje (``used_by_setup``) vive en
  ``POI.meta``, no en el ``Setup``.
- Serialización JSON-safe con ``to_dict`` / ``from_dict`` y un
  ``_normalize_meta`` idéntico en espíritu al de ``engine.market_object``.
- No importa ``backtest/``; no toca ``lifecycle.py`` ni ``market_state.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid

from engine.market_object import MarketObject


class SetupEligibility(str, Enum):
    """Estado de elegibilidad de un setup compuesto.

    Es un ``str`` Enum para que su valor serialice directamente a JSON y sea
    legible en la bitácora / trazabilidad.
    """

    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    OUT_OF_CONTEXT = "OUT_OF_CONTEXT"
    SUPERSEDED = "SUPERSEDED"


@dataclass
class Setup:
    """Entidad de datos de un setup ICT/SMC ya compuesto.

    El modelo es una instantánea inmutable de la intención de operación:
    referencia los MarketObjects que la componen (contexto HTF, POI,
    refinamiento, confirmación y trigger) y declara su elegibilidad.

    No se incluye ``used_by_setup`` como campo propio: la línea de linaje
    vive en ``POI.meta['used_by_setup']`` (lista de ids de setups que usan
    ese POI) y se expone de solo lectura vía la propiedad ``used_by_setup``.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    direction: int = 0  # 1 / -1 / 0 (undefined)
    context_htf: Optional[MarketObject] = None
    poi: Optional[MarketObject] = None
    refinement: Optional[MarketObject] = None
    confirmation: Optional[MarketObject] = None
    trigger: Optional[MarketObject] = None
    eligibility: SetupEligibility = SetupEligibility.ELIGIBLE
    reason: str = ""
    created_at: Any = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction debe ser -1, 0 o 1")
        if not isinstance(self.eligibility, SetupEligibility):
            self.eligibility = SetupEligibility(self.eligibility)

    # --- linaje (solo lectura; vive en POI.meta) ---
    @property
    def used_by_setup(self) -> list[str]:
        """Ids de setups que reutilizan el POI (lee ``POI.meta``, NO muta)."""
        if self.poi is None:
            return []
        val = self.poi.meta.get("used_by_setup")
        return list(val) if isinstance(val, (list, tuple, set)) else []

    @staticmethod
    def _normalize_meta(meta: dict) -> dict:
        """Convierte meta a JSON-safe para garantizar round-trip SAVE->LOAD.

        Espejo de ``MarketObject._normalize_meta``: JSON no soporta ``set``,
        así que cualquier set se serializa como lista ordenada; los dict
        internos con valores set también se normalizan.
        """
        out: dict = {}
        for k, v in meta.items():
            if isinstance(v, set):
                out[k] = sorted(v)
            elif isinstance(v, dict):
                out[k] = {kk: (sorted(vv) if isinstance(vv, set) else vv) for kk, vv in v.items()}
            else:
                out[k] = v
        return out

    def to_dict(self) -> dict:
        def _obj(o: Optional[MarketObject]) -> Optional[dict]:
            return o.to_dict() if isinstance(o, MarketObject) else None

        created = self.created_at
        if created is None:
            created_ser = None
        elif hasattr(created, "isoformat"):
            created_ser = created.isoformat()
        else:
            created_ser = str(created)

        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": int(self.direction),
            "context_htf": _obj(self.context_htf),
            "poi": _obj(self.poi),
            "refinement": _obj(self.refinement),
            "confirmation": _obj(self.confirmation),
            "trigger": _obj(self.trigger),
            "eligibility": (
                self.eligibility.value
                if isinstance(self.eligibility, SetupEligibility)
                else self.eligibility
            ),
            "reason": self.reason,
            "created_at": created_ser,
            "meta": self._normalize_meta(self.meta),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Setup":
        def _obj(o):
            return MarketObject.from_dict(o) if isinstance(o, dict) else None

        return cls(
            id=d.get("id", ""),
            symbol=d.get("symbol", ""),
            direction=int(d.get("direction", 0)),
            context_htf=_obj(d.get("context_htf")),
            poi=_obj(d.get("poi")),
            refinement=_obj(d.get("refinement")),
            confirmation=_obj(d.get("confirmation")),
            trigger=_obj(d.get("trigger")),
            eligibility=SetupEligibility(d.get("eligibility", SetupEligibility.ELIGIBLE)),
            reason=d.get("reason", ""),
            created_at=d.get("created_at"),
            meta=dict(d.get("meta", {})),
        )
