"""Evento de salida de una herramienta ICT individual (vela a vela).

Contrato común de Fase 1: cada herramienta envuelve un detector de
`detectors/` o `engine/` y emite ToolEvent por cada barra donde hay señal.
Sin look-ahead: solo usa filas <= k (lo garantiza el detector subyacente).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ToolEvent:
    bar_index: int
    time: Any = None
    symbol: str = ""
    tf: str = "M5"
    tool_name: str = ""
    signal: str = ""          # ej: BOS_UP, CHOCH_BULLISH, FVG_BULLISH, SWING_HH
    detail: str = ""          # contexto legible (nivel, tier, etc.)
    confidence_raw: float = 0.0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
