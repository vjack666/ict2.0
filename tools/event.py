"""Evento de salida de una herramienta ICT individual (vela a vela).

Contrato común de Fase 1: cada herramienta envuelve un detector de
`detectors/` o `engine/` y emite ToolEvent por cada barra donde hay señal.
Sin look-ahead: solo usa filas <= k (lo garantiza el detector subyacente).

DISEÑO CARTESIANO (ver veredicto del Director 2026-08-15):
- SWING = objeto geométrico PERSISTENTE (nace en origin_bar, se confirma en
  confirmation_bar, queda activo hasta break_bar).
- BOS/CHOCH/etc = evento de RUPTURA que consume el nivel del swing padre
  (parent_id apunta al swing roto). Conserva origin_bar/confirmation_bar/price
  del padre para reconstruir la línea horizontal SIN look-ahead ni coincidencia.

Campos cartesianos:
  origin_bar      -> vela donde ocurrió el pivot (geometría pura)
  confirmation_bar-> vela donde el swing quedó confirmado (info disponible)
  break_bar      -> vela donde el evento rompió el nivel (None si no roto)
  price          -> nivel del evento (y1 = y2 en la línea horizontal)
  parent_id      -> id del swing roto (para BOS/CHOCH)
  status         -> "active" | "broken" | "confirmed"
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ToolEvent:
    bar_index: int                 # vela del evento (para BOS = break_bar)
    time: Any = None
    symbol: str = ""
    tf: str = "M5"
    tool_name: str = ""            # "swing", "bos", "choch", ...
    signal: str = ""               # SWING_HH, BOS_UP, ...
    event_kind: str = "event"      # "object" (persistente) | "event" (ruptura)
    id: str = ""                   # id único del evento (SW_001, BOS_001)
    parent_id: str = ""            # id del swing roto (para rupturas)
    origin_bar: int | None = None  # vela del pivot (geometría)
    confirmation_bar: int | None = None  # vela de confirmación del swing
    break_bar: int | None = None   # vela de ruptura (None si no roto)
    price: float | None = None     # nivel cartesiano y
    detail: str = ""               # contexto legible
    confidence_raw: float = 0.0
    status: str = ""               # active | broken | confirmed
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
