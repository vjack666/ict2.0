"""Causal relations between canonical ICT market objects.

The relation layer does not invent a trading signal. It connects already
validated FVG/OB objects using explicit, point-in-time geometric/temporal
rules so downstream setup construction can be audited.

Strict causal mode (default)
----------------------------
Models the ICT narrative "OB is the origin of the impulse that left the FVG":

1. same direction (optional but default on);
2. positive price-zone overlap;
3. OB forms **before** the FVG is confirmed (never the reverse);
4. lag from OB anchor to FVG confirmation <= ``max_bars_apart``;
5. CausalLink always has parent=OB, child=FVG.

Symmetric mode keeps the legacy geometric overlap (|Δbars| <= max) for
ablation / comparison only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

from engine.lineage import CausalLink, validate_links
from engine.market_object import MarketObject, ObjectType


@dataclass(frozen=True)
class FVGOBRelation:
    """A reproducible relation between one FVG and one OB."""

    fvg_id: str
    ob_id: str
    relation: str
    direction: int
    overlap_low: float
    overlap_high: float
    temporal_ok: bool
    bars_apart: int
    # Strict causal metadata (None in symmetric-only pairs if ever emitted)
    ob_anchor_bar: int | None = None
    fvg_confirm_bar: int | None = None
    causal_order: str | None = None  # "OB_BEFORE_FVG" | "SYMMETRIC"


def _overlap(a: MarketObject, b: MarketObject) -> tuple[float, float] | None:
    low = max(float(a.zone_low), float(b.zone_low))
    high = min(float(a.zone_high), float(b.zone_high))
    if high <= low:
        return None
    return low, high


def _anchor_bar(obj: MarketObject) -> int:
    """Earliest known bar of the object (candidate if present, else bar_index)."""
    if obj.candidate_bar is not None:
        return int(obj.candidate_bar)
    if obj.bar_index is None:
        raise ValueError(f"{obj.id} sin bar_index/candidate_bar")
    return int(obj.bar_index)


def _confirm_bar(obj: MarketObject) -> int:
    """Bar at which the object is confirmed / tradable."""
    if obj.confirmation_bar is not None:
        return int(obj.confirmation_bar)
    if obj.tradable_bar is not None:
        return int(obj.tradable_bar)
    if obj.bar_index is None:
        raise ValueError(f"{obj.id} sin confirmation/tradable/bar_index")
    return int(obj.bar_index)


def _as_time(ts: Any) -> Optional[datetime]:
    """Normaliza candidate/confirmation/bar time a datetime UTC (o None)."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    try:
        from pandas import to_datetime

        dt = to_datetime(ts, utc=True, errors="coerce")
        return dt if dt is not None else None
    except Exception:
        return None


def _causal_precedes(parent: MarketObject, child: MarketObject) -> bool:
    """OE-07 / H6: orden causal cross-TF por TIMESTAMP, no por bar_index de relojes distintos.

    Regla: el ``parent`` (antecedente: OB footprint / confirm) debe ser
    estrictamente anterior al ``child`` (FVG confirmation) en el tiempo real.
    Cuando ambos comparten ``origin_tf`` podemos usar ``bar_index`` (mismo
    reloj); en cross-TF comparamos ``candidate_time``/``confirmation_time``.
    Devuelve True si el parent precede causalmente (relación posible).
    """
    same_tf = parent.origin_tf == child.origin_tf
    if same_tf:
        p = _anchor_bar(parent)
        c = _confirm_bar(child)
        return p < c  # mismo reloj => bar_index comparable
    p_time = _as_time(parent.candidate_time) or _as_time(parent.creation_time)
    c_time = _as_time(child.confirmation_time) or _as_time(child.creation_time)
    if p_time is None or c_time is None:
        return False  # falta tiempo en cross-TF => no inventar causalidad
    return p_time < c_time


def relate_fvg_ob(
    fvgs: Sequence[MarketObject],
    obs: Sequence[MarketObject],
    *,
    max_bars_apart: int = 20,
    same_direction: bool = True,
    causal_mode: str = "strict",
) -> list[FVGOBRelation]:
    """Find FVG↔OB relations.

    Parameters
    ----------
    causal_mode:
        ``"strict"`` (default) — OB must precede FVG confirmation (ICT order).
        ``"symmetric"`` — legacy geometric window on |Δbars| only.
    """
    if max_bars_apart < 0:
        raise ValueError("max_bars_apart debe ser >= 0")
    if causal_mode not in {"strict", "symmetric"}:
        raise ValueError("causal_mode debe ser 'strict' o 'symmetric'")

    result: list[FVGOBRelation] = []
    for fvg in fvgs:
        if fvg.type is not ObjectType.FVG or fvg.bar_index is None:
            continue
        fvg_confirm = _confirm_bar(fvg)
        fvg_anchor = _anchor_bar(fvg)

        for ob in obs:
            if ob.type is not ObjectType.ORDER_BLOCK or ob.bar_index is None:
                continue
            if same_direction and int(fvg.direction) != int(ob.direction):
                continue

            ob_anchor = _anchor_bar(ob)
            ob_confirm = _confirm_bar(ob)
            overlap = _overlap(fvg, ob)
            if overlap is None:
                continue

            if causal_mode == "strict":
                # OE-07 / H6: el orden causal se valida por reloj correcto.
                # Misma TF => bar_index comparable; cross-TF => timestamps.
                if not _causal_precedes(ob, fvg):
                    continue
                # Lag en strict mode solo es significativo dentro del MISMO reloj.
                if ob.origin_tf == fvg.origin_tf:
                    lag = fvg_confirm - ob_anchor
                    if lag < 0 or lag > max_bars_apart:
                        continue
                    if ob_anchor >= fvg_confirm:
                        continue
                else:
                    # Cross-TF: la distancia en bars es basura; no la usamos
                    # como filtro de ventana (el tiempo ya garantiza el orden).
                    lag = 0

                result.append(
                    FVGOBRelation(
                        fvg_id=fvg.id,
                        ob_id=ob.id,
                        relation="FVG_OB_CAUSAL",
                        direction=int(fvg.direction),
                        overlap_low=overlap[0],
                        overlap_high=overlap[1],
                        temporal_ok=True,
                        bars_apart=int(lag),
                        ob_anchor_bar=ob_anchor,
                        fvg_confirm_bar=fvg_confirm,
                        causal_order="OB_BEFORE_FVG",
                    )
                )
            else:
                # Legacy symmetric geometric window on confirmation bars.
                delta = abs(fvg_confirm - ob_confirm)
                if delta > max_bars_apart:
                    continue
                if max(fvg_confirm, ob_confirm) < 0:
                    continue
                result.append(
                    FVGOBRelation(
                        fvg_id=fvg.id,
                        ob_id=ob.id,
                        relation="FVG_OB_OVERLAP",
                        direction=int(fvg.direction),
                        overlap_low=overlap[0],
                        overlap_high=overlap[1],
                        temporal_ok=True,
                        bars_apart=int(delta),
                        ob_anchor_bar=ob_anchor,
                        fvg_confirm_bar=fvg_confirm,
                        causal_order="SYMMETRIC",
                    )
                )

    return sorted(result, key=lambda x: (x.fvg_id, x.ob_id, x.bars_apart))


def relation_links(
    relations: Iterable[FVGOBRelation],
    fvgs_by_id: dict[str, MarketObject],
    obs_by_id: dict[str, MarketObject],
) -> list[CausalLink]:
    """Convert accepted relations into auditable causal links.

    Strict causal pairs always use parent=OB, child=FVG.
    Symmetric pairs keep earlier bar as parent (legacy).
    """
    links: list[CausalLink] = []
    for relation in relations:
        fvg = fvgs_by_id.get(relation.fvg_id)
        ob = obs_by_id.get(relation.ob_id)
        if fvg is None or ob is None:
            raise ValueError("Relation references unknown FVG/OB")

        if relation.causal_order == "OB_BEFORE_FVG" or relation.relation == "FVG_OB_CAUSAL":
            parent, child = ob, fvg
        else:
            # symmetric / legacy: earlier confirmation is parent
            if _confirm_bar(fvg) <= _confirm_bar(ob):
                parent, child = fvg, ob
            else:
                parent, child = ob, fvg

        links.append(
            CausalLink(
                parent_id=parent.id,
                child_id=child.id,
                relation=relation.relation,
                parent_bar=_confirm_bar(parent) if parent.type is ObjectType.ORDER_BLOCK else _confirm_bar(parent),
                child_bar=_confirm_bar(child),
                parent_time=parent.bar_time or parent.creation_time,
                child_time=child.bar_time or child.creation_time,
            )
        )
    return validate_links(links)
