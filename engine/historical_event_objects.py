"""Canonical closed-bar producer for historical BOS/displacement MarketObjects.

This module composes existing detector authorities. It does not redefine BOS,
displacement, FVG, or OB. Lineage is child-to-parent only so an older object
never exposes a future child in an as-of projection.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

import pandas as pd

from detectors.displacement import DisplacementConfig, detect_displacement
from engine.bos.structure import StructureConfig, detect_market_structure
from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.market_object import MarketObject, ObjectState, ObjectType, Role


@dataclass(frozen=True)
class HistoricalEventConfig:
    ob_to_fvg_max_hours: int = 120
    fvg_to_bos_max_hours: int = 72
    bos_to_displacement_max_hours: int = 24
    structure: StructureConfig = StructureConfig()
    displacement: DisplacementConfig = DisplacementConfig()


def _utc(value: Any) -> pd.Timestamp:
    result = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(result):
        raise ValueError(f"invalid event time: {value!r}")
    return result


def _event_id(kind: str, tf: str, timestamp: Any, direction: int) -> str:
    epoch_ns = _utc(timestamp).value
    side = "BULL" if direction > 0 else "BEAR"
    return f"{kind}_{tf}_{epoch_ns}_{side}"


def _overlaps(a: MarketObject, b: MarketObject) -> bool:
    return max(float(a.zone_low), float(b.zone_low)) < min(float(a.zone_high), float(b.zone_high))


def build_historical_event_objects(
    frames: Mapping[str, pd.DataFrame],
    *,
    symbol: str = "EURUSD",
    config: HistoricalEventConfig | None = None,
) -> dict[str, Any]:
    """Build a deterministic OB→FVG→BOS→DISPLACEMENT population.

    Required frames are H4 and M15 with close-time column ``time``. Every event
    is published on its confirmation candle close. Pairing uses only already
    published parents and frozen elapsed-time windows.
    """
    cfg = config or HistoricalEventConfig()
    h4 = frames.get("H4")
    m15 = frames.get("M15")
    if h4 is None or h4.empty or m15 is None or m15.empty:
        raise ValueError("MISSING_LAYER: H4 and M15 are required")
    h4 = h4.copy().reset_index(drop=True)
    m15 = m15.copy().reset_index(drop=True)

    obs = detect_order_blocks(h4.to_dict("records"), timeframe="H4", symbol=symbol)
    for ob in obs:
        ob.role = Role.POI
    raw_fvgs = detect_fvg(m15.to_dict("records"), timeframe="M15", symbol=symbol)

    linked_fvgs: list[MarketObject] = []
    fvg_parent: dict[str, MarketObject] = {}
    ob_window = pd.Timedelta(hours=cfg.ob_to_fvg_max_hours)
    for fvg in raw_fvgs:
        ft = _utc(fvg.tradable_time)
        candidates = [
            ob for ob in obs
            if ob.direction == fvg.direction
            and _utc(ob.tradable_time) <= ft
            and ft - _utc(ob.tradable_time) <= ob_window
            and _overlaps(ob, fvg)
        ]
        if not candidates:
            continue
        parent = max(candidates, key=lambda item: (_utc(item.tradable_time), item.id))
        fvg.parent_object = parent.id
        fvg.meta["lineage_relation"] = "FVG_REFINES_OB_HTF"
        linked_fvgs.append(fvg)
        fvg_parent[fvg.id] = parent

    structure = detect_market_structure(h4, cfg.structure).frame
    bos_window = pd.Timedelta(hours=cfg.fvg_to_bos_max_hours)
    bos_objects: list[MarketObject] = []
    bos_chain: dict[str, tuple[MarketObject, MarketObject]] = {}
    for i, row in structure.loc[structure["bos_dir"] != 0].iterrows():
        direction = int(row["bos_dir"])
        event_time = _utc(h4.iloc[int(i)]["time"])
        candidates = [
            fvg for fvg in linked_fvgs
            if fvg.direction == direction
            and _utc(fvg.tradable_time) <= event_time
            and event_time - _utc(fvg.tradable_time) <= bos_window
        ]
        if not candidates:
            continue
        fvg = max(candidates, key=lambda item: (_utc(item.tradable_time), item.id))
        ob = fvg_parent[fvg.id]
        level = float(row["bos_level"])
        quality = float(row["bos_quality_score"]) if isfinite(float(row["bos_quality_score"])) else None
        obj = MarketObject(
            id=_event_id("BOS", "H4", event_time, direction), symbol=symbol,
            type=ObjectType.BOS, origin_tf="H4", role=Role.CONFIRMATION,
            direction=direction, zone_low=level, zone_high=level,
            creation_time=event_time, state=ObjectState.ACTIVE,
            bar_index=int(i), bar_time=event_time,
            candidate_bar=max(0, int(i) - cfg.structure.confirm_bars + 1),
            candidate_time=_utc(h4.iloc[max(0, int(i) - cfg.structure.confirm_bars + 1)]["time"]),
            confirmation_bar=int(i), confirmation_time=event_time,
            tradable_bar=int(i), tradable_time=event_time,
            parent_object=fvg.id, related_objects=[ob.id], quality_score=quality,
            meta={"producer": "detect_market_structure", "lineage_relation": "BOS_CONFIRMS_FVG_OB"},
        )
        bos_objects.append(obj)
        bos_chain[obj.id] = (fvg, ob)

    displacement = detect_displacement(m15, cfg.displacement)
    disp_window = pd.Timedelta(hours=cfg.bos_to_displacement_max_hours)
    displacement_objects: list[MarketObject] = []
    for i, row in displacement.loc[
        displacement["displacement_bullish"] | displacement["displacement_bearish"]
    ].iterrows():
        direction = 1 if bool(row["displacement_bullish"]) else -1
        event_time = _utc(m15.iloc[int(i)]["time"])
        candidates = [
            bos for bos in bos_objects
            if bos.direction == direction
            and _utc(bos.tradable_time) <= event_time
            and event_time - _utc(bos.tradable_time) <= disp_window
        ]
        if not candidates:
            continue
        bos = max(candidates, key=lambda item: (_utc(item.tradable_time), item.id))
        fvg, ob = bos_chain[bos.id]
        obj = MarketObject(
            id=_event_id("DISP", "M15", event_time, direction), symbol=symbol,
            type=ObjectType.DISPLACEMENT, origin_tf="M15", role=Role.TRIGGER,
            direction=direction, zone_low=float(row["low"]), zone_high=float(row["high"]),
            creation_time=event_time, state=ObjectState.ACTIVE,
            bar_index=int(i), bar_time=event_time,
            candidate_bar=int(i), candidate_time=event_time,
            confirmation_bar=int(i), confirmation_time=event_time,
            tradable_bar=int(i), tradable_time=event_time,
            parent_object=bos.id, related_objects=[fvg.id, ob.id],
            meta={"producer": "detect_displacement", "lineage_relation": "DISPLACEMENT_TRIGGERS_BOS_CHAIN", "magnitude": float(row["displacement_magnitude"])},
        )
        displacement_objects.append(obj)

    objects = sorted(
        [*obs, *linked_fvgs, *bos_objects, *displacement_objects],
        key=lambda item: (_utc(item.tradable_time), item.type.value, item.id),
    )
    return {
        "objects": objects,
        "counts": {
            "ob_h4": len(obs), "fvg_m15_linked": len(linked_fvgs),
            "bos_h4_linked": len(bos_objects), "displacement_m15_linked": len(displacement_objects),
        },
        "config": {
            "ob_to_fvg_max_hours": cfg.ob_to_fvg_max_hours,
            "fvg_to_bos_max_hours": cfg.fvg_to_bos_max_hours,
            "bos_to_displacement_max_hours": cfg.bos_to_displacement_max_hours,
        },
    }


__all__ = ["HistoricalEventConfig", "build_historical_event_objects"]
