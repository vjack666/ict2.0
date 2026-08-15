"""ict_backtest/market_object.py — Objeto de mercado ICT (fuente canonica).

Un MarketObject es UNA estructura real del mercado con identidad: sabe su
capa de origen (origin_tf), su proposito (role), su estado por EVENTO
(state) y su lugar en la cadena causal (parent_object / related_objects).

Disenado en DISENO_ARQUITECTURA_OBJETOS_MERCADO.md y definido
conceptualmente en MARKET_OBJECT_MODEL.md (ontologia / contrato).

Regla dura de capa (tesis 18 / ontologia): el POI institucional SOLO existe
en HTF (D1/H4/H1). Un FVG/OB de M15 es siempre REFINEMENT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import uuid


class ObjectType(str, Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"
    FVG = "FVG"
    ORDER_BLOCK = "ORDER_BLOCK"
    LIQUIDITY = "LIQUIDITY"
    SWEEP = "SWEEP"
    DISPLACEMENT = "DISPLACEMENT"
    RETURN = "RETURN"
    CONTRACT = "CONTRACT"  # Contratacion LTF (entry/sl/tp) hija del RETURN
    CANDLE = "CANDLE"  # R9 Paso 3: vista de vela con su contexto ICT completo (sequence)


class Role(str, Enum):
    POI = "POI"
    REFINEMENT = "REFINEMENT"
    EXECUTION = "EXECUTION"  # Contrato LTF: limite formacion->ejecucion (no mezcla eventos)
    CONTEXT = "CONTEXT"


class ObjectState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"
    CONSUMED = "CONSUMED"


# Capas permitidas para POI (ONTologia: POI solo en HTF).
_POI_TFS = {"D1", "H4", "H1"}


@dataclass
class MarketObject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    type: ObjectType = ObjectType.FVG
    origin_tf: str = ""               # SELLO DE CAPA: obligatorio
    role: Role = Role.REFINEMENT
    direction: int = 0
    zone_high: float = 0.0
    zone_low: float = 0.0
    creation_time: object = None
    state: ObjectState = ObjectState.CREATED
    meta: dict = field(default_factory=dict)
    parent_object: str | None = None
    related_objects: list[str] = field(default_factory=list)
    quality_score: float | None = None
    # R9: ancla al barra de origen para reconstruir el df legacy 1:1.
    bar_index: int | None = None      # índice de la vela en el TF de origen
    bar_time: object = None           # timestamp de la vela de origen

    def __post_init__(self) -> None:
        if not self.origin_tf:
            raise TypeError("origin_tf es obligatorio (sello de capa)")
        if self.role == Role.POI and self.origin_tf not in _POI_TFS:
            raise ValueError(
                f"POI solo en HTF ({sorted(_POI_TFS)}); recibido {self.origin_tf}"
            )

    def to_dict(self) -> dict:
        """Representación plana del objeto (sin semántica de trading).

        Permite que un consumidor puro (engine/lineage.py) reconstruya el
        linaje causal por parent_object sin acoplarse al dataclass. No altera
        ninguna regla ICT/SMC ni introduce indicadores.
        """
        def _f(v):
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return v
            return None if fv != fv else fv
        return {
            "id": self.id,
            "symbol": self.symbol,
            "type": self.type.value if isinstance(self.type, ObjectType) else self.type,
            "origin_tf": self.origin_tf,
            "role": self.role.value if isinstance(self.role, Role) else self.role,
            "direction": int(self.direction),
            "zone_high": _f(self.zone_high),
            "zone_low": _f(self.zone_low),
            "creation_time": str(self.creation_time) if self.creation_time is not None else None,
            "state": self.state.value if isinstance(self.state, ObjectState) else self.state,
            "parent_object": self.parent_object,
            "related_objects": list(self.related_objects),
            "bar_index": int(self.bar_index) if self.bar_index is not None else None,
            "bar_time": str(self.bar_time) if self.bar_time is not None else None,
            "meta": {k: _f(v) for k, v in self.meta.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MarketObject":
        """Reconstruye un MarketObject desde su to_dict (round-trip persistence)."""
        return cls(
            id=d.get("id", ""),
            symbol=d.get("symbol", ""),
            type=ObjectType(d["type"]),
            origin_tf=d.get("origin_tf", ""),
            role=Role(d["role"]),
            direction=int(d.get("direction", 0)),
            zone_high=float(d.get("zone_high", 0.0)) if d.get("zone_high") is not None else float("nan"),
            zone_low=float(d.get("zone_low", 0.0)) if d.get("zone_low") is not None else float("nan"),
            creation_time=d.get("creation_time"),
            state=ObjectState(d["state"]),
            meta=dict(d.get("meta", {})),
            parent_object=d.get("parent_object"),
            related_objects=list(d.get("related_objects", [])),
            quality_score=d.get("quality_score"),
            bar_index=d.get("bar_index"),
            bar_time=d.get("bar_time"),
        )
