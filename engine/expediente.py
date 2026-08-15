"""engine/expediente.py — Expediente por señal (Ley 8 / Ley 7 / Ley 4).

Cada señal de `run_sequence` lleva un `Expediente`: la bitácora inmutable de
su vida (nacimiento, fases alcanzadas, regla de invalidación y desenlace).

Contrato anti-look-ahead (Ley 1): el expediente NUNCA lee precios. Solo
recibe HECHOS YA DECIDIDOS por `run_sequence` (índices/tiempos/condiciones).
`advance` e `invalidate` solo aceptan `idx >= último idx registrado`; si se
pasa un índice menor o futuro respecto a la vela en curso, lanzan `ValueError`
(imposible mirar el futuro ni reescribir el pasado).

Regresión cero: `run_sequence` sigue devolviendo `(signals, phase_seen)`. El
expediente se adjunta DENTRO de cada señal (`sig["expediente"]`) y la firma
vieja no cambia. La función nueva `run_sequence_traced` (definida en
engine/sequence.py post-migración) lo expone como 3er elemento.

Ley 7 (unicidad): `id` es un hash determinista de
symbol + ltf_tf + sweep_idx + direction -> dos señales iguales colisionan
intencionalmente (misma identidad = mismo expediente).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PhaseEvent:
    """Un hecho ya decidido en la vida de la señal.

    Añadido Fase 5 (Arquitectura A): event_id / parent_event_id dan identidad
    causal al evento. event_id es el id del MarketObject de este evento;
    parent_event_id es el id del evento padre ya confirmado (anti-look-ahead:
    el padre siempre tiene idx <= este). Sin ellos, el linaje es solo temporal.
    """

    phase: str          # "SWEEP" | "DISPLACE" | "BOS" | "ENTRY" | "INVALID"
    idx: int            # índice de la vela LTF donde ocurrió
    time: Any = None    # timestamp de la vela (cerrada)
    condition: str = ""  # texto descriptivo (p.ej. "SWEEP_DOWN@LTF")
    event_id: str = ""   # id del MarketObject de este evento (Arq A)
    parent_event_id: str = ""  # id del evento padre ya confirmado (Arq A)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "idx": int(self.idx),
            "time": str(self.time) if self.time is not None else None,
            "condition": self.condition,
            "event_id": self.event_id,
            "parent_event_id": self.parent_event_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseEvent":
        return cls(
            phase=d["phase"],
            idx=int(d["idx"]),
            time=d.get("time"),
            condition=d.get("condition", ""),
            event_id=d.get("event_id", ""),
            parent_event_id=d.get("parent_event_id", ""),
        )


@dataclass
class Expediente:
    """Bitácora inmutable de una señal (Ley 8: trazabilidad; Ley 4: geometría)."""

    id: str
    symbol: str
    tf: str
    direction: int
    birth_idx: int
    birth_time: Any = None
    birth_condition: str = ""
    phase_events: list[PhaseEvent] = field(default_factory=list)
    invalidation_rule: str = ""          # regla predefinida en el nacimiento
    invalidation_idx: int | None = None
    invalidation_time: Any = None
    invalidation_reason: str | None = None
    outcome: str = "OPEN"                # "OPEN" | "ENTRY" | "INVALID"
    meta: dict = field(default_factory=dict)

    # _last_idx rastrea el último idx registrado para la guarda anti-look-ahead.
    _last_idx: int = field(default=-1, repr=False, compare=False)

    @classmethod
    def open(
        cls,
        *,
        symbol: str,
        tf: str,
        direction: int,
        birth_idx: int,
        birth_time: Any = None,
        birth_condition: str = "",
        invalidation_rule: str = "",
        meta: dict | None = None,
    ) -> "Expediente":
        """Crea un expediente en su nacimiento (al confirmarse el sweep)."""
        raw = f"{symbol}|{tf}|{birth_idx}|{direction}"
        hid = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        obj = cls(
            id=hid,
            symbol=symbol,
            tf=tf,
            direction=int(direction),
            birth_idx=int(birth_idx),
            birth_time=birth_time,
            birth_condition=birth_condition,
            invalidation_rule=invalidation_rule,
            meta=dict(meta or {}),
        )
        obj._last_idx = int(birth_idx)
        return obj

    def advance(self, phase: str, idx: int, time: Any = None, condition: str = "",
                 event_id: str = "", parent_event_id: str = "") -> None:
        """Registra un hecho ya decidido. Índice monótono no decreciente."""
        idx = int(idx)
        if idx < self._last_idx:
            raise ValueError(
                f"Expediente.advance: idx={idx} < último idx registrado "
                f"{self._last_idx} (anti-look-ahead / no reescritura del pasado)"
            )
        if idx == self._last_idx and self.phase_events and self.phase_events[-1].phase == phase:
            # mismo índice y misma fase -> idempotente, no duplica
            self._last_idx = idx
            return
        self.phase_events.append(PhaseEvent(phase, idx, time, condition,
                                            event_id=event_id, parent_event_id=parent_event_id))
        self._last_idx = idx

    def invalidate(self, idx: int, time: Any = None, reason: str | None = None,
                   event_id: str = "", parent_event_id: str = "") -> None:
        """Marca la señal como invalidada por su regla predefinida."""
        idx = int(idx)
        if idx < self._last_idx:
            raise ValueError(
                f"Expediente.invalidate: idx={idx} < último idx registrado "
                f"{self._last_idx} (anti-look-ahead)"
            )
        self.phase_events.append(PhaseEvent("INVALID", idx, time, reason or "",
                                            event_id=event_id, parent_event_id=parent_event_id))
        self.invalidation_idx = idx
        self.invalidation_time = time
        self.invalidation_reason = reason
        self.outcome = "INVALID"
        self._last_idx = idx

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "tf": self.tf,
            "direction": self.direction,
            "birth_idx": self.birth_idx,
            "birth_time": str(self.birth_time) if self.birth_time is not None else None,
            "birth_condition": self.birth_condition,
            "phase_events": [e.to_dict() for e in self.phase_events],
            "invalidation_rule": self.invalidation_rule,
            "invalidation_idx": self.invalidation_idx,
            "invalidation_time": (
                str(self.invalidation_time) if self.invalidation_time is not None else None
            ),
            "invalidation_reason": self.invalidation_reason,
            "outcome": self.outcome,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Expediente":
        """Reconstruye un Expediente desde su to_dict (round-trip persistence)."""
        exp = cls(
            id=d["id"],
            symbol=d["symbol"],
            tf=d["tf"],
            direction=int(d["direction"]),
            birth_idx=int(d["birth_idx"]),
            birth_time=d.get("birth_time"),
            birth_condition=d.get("birth_condition", ""),
            invalidation_rule=d.get("invalidation_rule", ""),
            invalidation_idx=d.get("invalidation_idx"),
            invalidation_time=d.get("invalidation_time"),
            invalidation_reason=d.get("invalidation_reason"),
            outcome=d.get("outcome", "OPEN"),
            meta=dict(d.get("meta", {})),
        )
        exp.phase_events = [PhaseEvent.from_dict(e) for e in d.get("phase_events", [])]
        # Restaura la guarda anti-look-ahead al ultimo idx registrado.
        exp._last_idx = exp.phase_events[-1].idx if exp.phase_events else int(exp.birth_idx)
        return exp
