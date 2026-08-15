"""Fase C2+ — Tier engine para calidad POI (josé/B1 data + stacking + narrativa HTF).

NO es filtro duro: solo calcula calidad objetiva (tier, stacking, ancla narrativa,
BPR status, confidence_weight). El consumidor (observador / estrategia / optimizador)
decidir si lo usa como peso, threshold o demo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Orden canónico de autoridad (libro 21 §2 / PRINCIPIOS R10/R11):
# T1 = BPR / actor mayoritario > T2 = FVG/OB > T3 = rejection/mitigation
TIER_RANK = {"T1": 3, "T2": 2, "T3": 1, "NONE": 0}

# Detector de BPR local requiere zonas LTF(H1/M15/etc.) preconstruidas.
def _zones_overlap(a_high: float, a_low: float, b_high: float, b_low: float) -> bool:
    return max(a_low, b_low) < min(a_high, b_high)


def bpr_status(
    directions: Sequence[int],
    high: Sequence[float],
    low: Sequence[float],
    pd_type: Sequence[str],
    direction: int | None = None,
) -> str:
    """Devuelve el pd_type fusionado si hay BPR en la dirección pedida.

    BPR = FVG + OB caen en zona de precio superpuesta en el mismo TF.
    """
    if direction is None:
        return "NONE"
    hits = [
        (p, h, l)
        for d, p, h, l in zip(directions, pd_type, high, low)
        if d == direction and p in ("FVG", "OB", "BPR")
    ]
    fvg = [r for r in hits if r[0] == "FVG"]
    ob = [r for r in hits if r[0] == "OB"]
    if not fvg or not ob:
        return "NONE"
    for fp, fh, fl in fvg:
        for op, oh, ol in ob:
            if _zones_overlap(fh, fl, oh, ol):
                return "BPR"
    return "NONE"


def best_tier(htf_zones: Sequence[object]) -> str:
    best = "NONE"
    for z in htf_zones:
        t = getattr(z, "pd_tier", "NONE")
        if TIER_RANK.get(t, 0) >= TIER_RANK.get(best, 0):
            best = t
    return best


def stacking_level(htf_zones: Sequence[object]) -> int:
    return len({getattr(z, "tf", "?") for z in htf_zones})


def narrative_anchor(
    htf_zones: Sequence[object],
    direction: int,
    sweep_up: bool,
    sweep_down: bool,
) -> bool:
    """La zona HTF respalda narrativa institucional hacia la dirección pedida."""
    has_dir = any(getattr(z, "direction", 0) == direction for z in htf_zones)
    sweep = sweep_up if direction == 1 else sweep_down
    return bool(has_dir and sweep)


def confidence_weight(
    tier: str,
    stacking: int,
    anchor: bool,
) -> float:
    """Peso objetivo [0,1] para autoridad de POI."""
    w = 0.0
    if tier != "NONE":
        w += 0.55
    w += {"T1": 0.30, "T2": 0.15, "T3": 0.05, "NONE": 0.0}.get(tier, 0.0)
    w += {1: 0.0, 2: 0.10}.get(stacking, 0.20 if stacking >= 3 else 0.0)
    if anchor:
        w += 0.15
    return min(1.0, max(0.0, w))


def level_label(w: float) -> str:
    return "Alta" if w >= 0.8 else ("Media" if w >= 0.5 else "Baja")


@dataclass(frozen=True)
class POIQuality:
    tier: str                        # mejor tier anclado (T1>T2>T3)
    stacking_level: int              # capas TF distintas
    narrative_anchor: bool           # ancla narrativa HTF presente
    bpr_status: str                  # NONE | BPR
    confidence_weight: float         # 0..1
    level: str                       # Alta | Media | Baja


def quality_for(
    *,
    ltf_directions: Sequence[int],
    ltf_high: Sequence[float],
    ltf_low: Sequence[float],
    ltf_pd_type: Sequence[str],
    htf_zones: Sequence[object],
    direction: int,
    sweep_up: bool,
    sweep_down: bool,
) -> POIQuality:
    """Calcula calidad POI para un setup concreto."""
    tier = best_tier(htf_zones)
    stacking = stacking_level(htf_zones)
    anchor = narrative_anchor(htf_zones, direction, sweep_up, sweep_down)
    bpr = bpr_status(ltf_directions, ltf_high, ltf_low, ltf_pd_type, direction)
    w = confidence_weight(tier, stacking, anchor)
    if bpr == "BPR":
        w = min(1.0, w + 0.05)
    return POIQuality(
        tier=tier,
        stacking_level=stacking,
        narrative_anchor=anchor,
        bpr_status=bpr,
        confidence_weight=round(w, 4),
        level=level_label(w),
    )
