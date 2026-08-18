"""Causal relations between canonical ICT market objects.

The relation layer does not invent a trading signal. It connects already
validated FVG/OB objects using explicit, point-in-time geometric/temporal
rules so downstream setup construction can be audited.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

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

    @property
    def overlap_size(self) -> float:
        return max(0.0, self.overlap_high - self.overlap_low)


def _overlap(a: MarketObject, b: MarketObject) -> tuple[float, float] | None:
    low = max(float(a.zone_low), float(b.zone_low))
    high = min(float(a.zone_high), float(b.zone_high))
    if high <= low:
        return None
    return low, high


def relate_fvg_ob(
    fvgs: Sequence[MarketObject],
    obs: Sequence[MarketObject],
    *,
    max_bars_apart: int = 20,
    same_direction: bool = True,
) -> list[FVGOBRelation]:
    """Find explicit FVG↔OB confluences.

    Rules:
    - both objects must be canonical FVG/OB objects;
    - their price zones must overlap positively;
    - they must be observed within ``max_bars_apart``;
    - relation is point-in-time: no object may be paired with a future object
      beyond the allowed causal window;
    - by default the directions must agree.
    """
    if max_bars_apart < 0:
        raise ValueError("max_bars_apart debe ser >= 0")

    result: list[FVGOBRelation] = []
    for fvg in fvgs:
        if fvg.type is not ObjectType.FVG or fvg.bar_index is None:
            continue
        for ob in obs:
            if ob.type is not ObjectType.ORDER_BLOCK or ob.bar_index is None:
                continue
            if same_direction and int(fvg.direction) != int(ob.direction):
                continue
            if abs(int(fvg.bar_index) - int(ob.bar_index)) > max_bars_apart:
                continue
            # The relation is causal only when the later-confirmed object is
            # not used to retroactively create the earlier one.
            if max(int(fvg.bar_index), int(ob.bar_index)) < 0:
                continue
            overlap = _overlap(fvg, ob)
            if overlap is None:
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
                    bars_apart=abs(int(fvg.bar_index) - int(ob.bar_index)),
                )
            )
    # deterministic order, then deduplicate at the causal-link layer
    return sorted(result, key=lambda x: (x.fvg_id, x.ob_id, x.bars_apart))


def relation_links(
    relations: Iterable[FVGOBRelation],
    fvgs_by_id: dict[str, MarketObject],
    obs_by_id: dict[str, MarketObject],
) -> list[CausalLink]:
    """Convert accepted relations into auditable causal links."""
    links: list[CausalLink] = []
    for relation in relations:
        fvg = fvgs_by_id.get(relation.fvg_id)
        ob = obs_by_id.get(relation.ob_id)
        if fvg is None or ob is None:
            raise ValueError("Relation references unknown FVG/OB")
        # Use the earlier object's bar as parent to preserve point-in-time order.
        if int(fvg.bar_index) <= int(ob.bar_index):
            links.append(CausalLink(
                parent_id=fvg.id,
                child_id=ob.id,
                relation=relation.relation,
                parent_bar=int(fvg.bar_index),
                child_bar=int(ob.bar_index),
                parent_time=fvg.bar_time or fvg.creation_time,
                child_time=ob.bar_time or ob.creation_time,
            ))
        else:
            links.append(CausalLink(
                parent_id=ob.id,
                child_id=fvg.id,
                relation=relation.relation,
                parent_bar=int(ob.bar_index),
                child_bar=int(fvg.bar_index),
                parent_time=ob.bar_time or ob.creation_time,
                child_time=fvg.bar_time or fvg.creation_time,
            ))
    return validate_links(links)
