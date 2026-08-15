"""Permanent engine signal contract.

The engine emits a decision. It does not know how a historical trade is
filled, managed, or scored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ICTSignal:
    symbol: str
    time: str
    direction: int          # +1 long, -1 short
    entry: float
    stop_loss: float
    take_profit: float
    model: str = ""         # "intradia" | "scalping"
    confidence: float = 0.0
    # Sequence indices are decision provenance, not trade simulation state.
    sweep_at: int | None = None
    bos_at: int | None = None
    entry_at: int | None = None
    # Perception metadata. These fields do not change entry/SL/TP.
    zone_authority: Any = None
    htf_anchored: bool | None = None
    poi_present: bool | None = None
    zone_class: str | None = None
    po3_complete: bool | None = None
    external_tp: float | None = None

