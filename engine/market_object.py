"""Objeto de mercado ICT (fuente canónica del motor).

Un MarketObject representa una estructura real del mercado con identidad,
capa, propósito, estado y linaje. Para PD Arrays (FVG/OB/Breaker/BPR) el
contrato temporal distingue claramente candidate/confirmation/tradable y el
lifecycle se gobierna mediante transiciones explícitas.
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
    CONTRACT = "CONTRACT"
    CANDLE = "CANDLE"
    BREAKER = "BREAKER"
    BPR = "BPR"


class Role(str, Enum):
    POI = "POI"
    REFINEMENT = "REFINEMENT"
    EXECUTION = "EXECUTION"
    CONTEXT = "CONTEXT"


class ObjectState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    MITIGATED = "MITIGATED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


_POI_TFS = {"D1", "H4", "H1"}
_TERMINAL_STATES = {
    ObjectState.MITIGATED,
    ObjectState.INVALIDATED,
    ObjectState.EXPIRED,
    ObjectState.CONSUMED,
}
_ALLOWED_TRANSITIONS = {
    ObjectState.CREATED: {ObjectState.ACTIVE, ObjectState.INVALIDATED, ObjectState.EXPIRED},
    ObjectState.ACTIVE: {
        ObjectState.PARTIALLY_MITIGATED,
        ObjectState.MITIGATED,
        ObjectState.INVALIDATED,
        ObjectState.EXPIRED,
        ObjectState.CONSUMED,
    },
    ObjectState.PARTIALLY_MITIGATED: {
        ObjectState.PARTIALLY_MITIGATED,
        ObjectState.MITIGATED,
        ObjectState.INVALIDATED,
        ObjectState.EXPIRED,
        ObjectState.CONSUMED,
    },
    ObjectState.MITIGATED: set(),
    ObjectState.INVALIDATED: set(),
    ObjectState.EXPIRED: set(),
    ObjectState.CONSUMED: set(),
}


@dataclass
class MarketObject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    type: ObjectType = ObjectType.FVG
    origin_tf: str = ""
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
    bar_index: int | None = None
    bar_time: object = None
    candidate_bar: int | None = None
    candidate_time: object = None
    confirmation_bar: int | None = None
    confirmation_time: object = None
    tradable_bar: int | None = None
    tradable_time: object = None
    first_touch_bar: int | None = None
    first_touch_time: object = None
    touch_count: int = 0
    invalidated_bar: int | None = None
    invalidated_time: object = None
    mitigation_level: float | None = None
    age_bars: int = 0

    def __post_init__(self) -> None:
        if not self.origin_tf:
            raise TypeError("origin_tf es obligatorio (sello de capa)")
        if self.role == Role.POI and self.origin_tf not in _POI_TFS:
            raise ValueError(f"POI solo en HTF ({sorted(_POI_TFS)}); recibido {self.origin_tf}")
        self._validate_foundational_invariants()
        self._validate_temporal_contract()
        self._validate_lineage_contract()

    def _validate_foundational_invariants(self) -> None:
        if self.direction not in (-1, 0, 1):
            raise ValueError("direction debe ser -1, 0 o 1")
        if self.zone_high < self.zone_low:
            raise ValueError("zone_high debe ser >= zone_low")
        if self.touch_count < 0:
            raise ValueError("touch_count no puede ser negativo")
        if self.age_bars < 0:
            raise ValueError("age_bars no puede ser negativo")
        if self.first_touch_bar is not None and self.touch_count < 1:
            raise ValueError("first_touch_bar requiere touch_count >= 1")
        if self.quality_score is not None and not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score debe estar entre 0 y 1")

    def _validate_temporal_contract(self) -> None:
        bars = [b for b in (self.candidate_bar, self.confirmation_bar, self.tradable_bar) if b is not None]
        if bars != sorted(bars):
            raise ValueError("Contrato temporal inválido: candidate <= confirmation <= tradable")
        if self.tradable_bar is not None and self.confirmation_bar is None:
            raise ValueError("tradable_bar requiere confirmation_bar")
        if self.first_touch_bar is not None and self.tradable_bar is not None and self.first_touch_bar < self.tradable_bar:
            raise ValueError("first_touch_bar no puede preceder a tradable_bar")
        if self.invalidated_bar is not None and self.candidate_bar is not None and self.invalidated_bar < self.candidate_bar:
            raise ValueError("invalidated_bar no puede preceder a candidate_bar")
        times = [t for t in (self.candidate_time, self.confirmation_time, self.tradable_time) if t is not None]
        if len(times) >= 2:
            try:
                if times != sorted(times):
                    raise ValueError("Contrato temporal inválido: candidate_time <= confirmation_time <= tradable_time")
            except TypeError as exc:
                raise ValueError("Los tiempos del contrato deben ser comparables") from exc

    def _validate_lineage_contract(self) -> None:
        if self.parent_object == self.id:
            raise ValueError("parent_object no puede apuntar al propio objeto")
        if any(obj_id == self.id for obj_id in self.related_objects):
            raise ValueError("related_objects no puede contener el propio objeto")
        if len(self.related_objects) != len(set(self.related_objects)):
            raise ValueError("related_objects no puede contener duplicados")
        if any(not obj_id for obj_id in self.related_objects):
            raise ValueError("related_objects no puede contener ids vacíos")

    def can_transition_to(self, target: ObjectState) -> bool:
        if not isinstance(target, ObjectState):
            target = ObjectState(target)
        return target in _ALLOWED_TRANSITIONS[self.state]

    def transition_to(self, target: ObjectState) -> "MarketObject":
        if not isinstance(target, ObjectState):
            target = ObjectState(target)
        if not self.can_transition_to(target):
            raise ValueError(f"Transición de estado inválida: {self.state.value} -> {target.value}")
        self.state = target
        return self

    @property
    def is_terminal(self) -> bool:
        return self.state in _TERMINAL_STATES

    def to_dict(self) -> dict:
        def _f(v):
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return v
            return None if fv != fv else fv
        return {
            "id": self.id, "symbol": self.symbol,
            "type": self.type.value if isinstance(self.type, ObjectType) else self.type,
            "origin_tf": self.origin_tf,
            "role": self.role.value if isinstance(self.role, Role) else self.role,
            "direction": int(self.direction), "zone_high": _f(self.zone_high), "zone_low": _f(self.zone_low),
            "creation_time": str(self.creation_time) if self.creation_time is not None else None,
            "state": self.state.value if isinstance(self.state, ObjectState) else self.state,
            "parent_object": self.parent_object, "related_objects": list(self.related_objects),
            "quality_score": _f(self.quality_score), "bar_index": self.bar_index,
            "bar_time": str(self.bar_time) if self.bar_time is not None else None,
            "candidate_bar": self.candidate_bar,
            "candidate_time": str(self.candidate_time) if self.candidate_time is not None else None,
            "confirmation_bar": self.confirmation_bar,
            "confirmation_time": str(self.confirmation_time) if self.confirmation_time is not None else None,
            "tradable_bar": self.tradable_bar,
            "tradable_time": str(self.tradable_time) if self.tradable_time is not None else None,
            "first_touch_bar": self.first_touch_bar,
            "first_touch_time": str(self.first_touch_time) if self.first_touch_time is not None else None,
            "touch_count": int(self.touch_count), "invalidated_bar": self.invalidated_bar,
            "invalidated_time": str(self.invalidated_time) if self.invalidated_time is not None else None,
            "mitigation_level": _f(self.mitigation_level), "age_bars": int(self.age_bars),
            "meta": {k: _f(v) for k, v in self.meta.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MarketObject":
        return cls(
            id=d.get("id", ""), symbol=d.get("symbol", ""), type=ObjectType(d["type"]),
            origin_tf=d.get("origin_tf", ""), role=Role(d["role"]), direction=int(d.get("direction", 0)),
            zone_high=float(d.get("zone_high", 0.0)), zone_low=float(d.get("zone_low", 0.0)),
            creation_time=d.get("creation_time"), state=ObjectState(d.get("state", ObjectState.CREATED)),
            meta=dict(d.get("meta", {})), parent_object=d.get("parent_object"),
            related_objects=list(d.get("related_objects", [])), quality_score=d.get("quality_score"),
            bar_index=d.get("bar_index"), bar_time=d.get("bar_time"), candidate_bar=d.get("candidate_bar"),
            candidate_time=d.get("candidate_time"), confirmation_bar=d.get("confirmation_bar"),
            confirmation_time=d.get("confirmation_time"), tradable_bar=d.get("tradable_bar"),
            tradable_time=d.get("tradable_time"), first_touch_bar=d.get("first_touch_bar"),
            first_touch_time=d.get("first_touch_time"), touch_count=int(d.get("touch_count", 0)),
            invalidated_bar=d.get("invalidated_bar"), invalidated_time=d.get("invalidated_time"),
            mitigation_level=d.get("mitigation_level"), age_bars=int(d.get("age_bars", 0)),
        )
