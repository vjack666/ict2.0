"""Canonical closed-bar producer for historical BOS/displacement MarketObjects.

This module composes existing detector authorities. It does not redefine BOS,
displacement, FVG, or OB. Lineage is child-to-parent only so an older object
never exposes a future child in an as-of projection.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

import pandas as pd

from detectors.displacement import DisplacementConfig, detect_displacement
from engine.bos.structure import StructureConfig, detect_market_structure
from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.lifecycle import evaluate
from engine.market_object import MarketObject, ObjectState, ObjectType, Role


@dataclass(frozen=True)
class HistoricalEventConfig:
    poi_to_child_max_hours: int = 120
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


def _active_at(obj: MarketObject, frame: pd.DataFrame, event_time: Any) -> bool:
    """Return the authority-time state without mutating the birth object."""
    projected = deepcopy(obj)
    start, end = _utc(projected.tradable_time), _utc(event_time)
    for index, row in frame.loc[(frame["time"] > start) & (frame["time"] <= end)].iterrows():
        bar = row.to_dict()
        bar["tf"] = projected.origin_tf
        bar["__index__"] = int(index)
        evaluate(projected, bar, authority_tf=projected.origin_tf)
        if projected.is_terminal:
            break
    return projected.state is ObjectState.ACTIVE


def build_historical_event_objects(
    frames: Mapping[str, pd.DataFrame],
    *,
    symbol: str = "EURUSD",
    config: HistoricalEventConfig | None = None,
) -> dict[str, Any]:
    """Build the deterministic v2 causal event DAG.

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
    poi_window = pd.Timedelta(hours=cfg.poi_to_child_max_hours)
    structure = detect_market_structure(m15, cfg.structure).frame
    bos_objects: list[MarketObject] = []
    bos_parent: dict[str, MarketObject] = {}
    for i, row in structure.loc[structure["bos_dir"] != 0].iterrows():
        direction = int(row["bos_dir"])
        event_time = _utc(m15.iloc[int(i)]["time"])
        candidates = [
            ob for ob in obs
            if ob.direction == direction
            and _utc(ob.tradable_time) <= event_time
            and event_time - _utc(ob.tradable_time) <= poi_window
            and _active_at(ob, h4, event_time)
        ]
        if not candidates:
            continue
        ob = max(candidates, key=lambda item: (_utc(item.tradable_time), item.id))
        level = float(row["bos_level"])
        quality = float(row["bos_quality_score"]) if isfinite(float(row["bos_quality_score"])) else None
        obj = MarketObject(
            id=_event_id("BOS", "M15", event_time, direction), symbol=symbol,
            type=ObjectType.BOS, origin_tf="M15", role=Role.CONFIRMATION,
            direction=direction, zone_low=level, zone_high=level,
            creation_time=event_time, state=ObjectState.ACTIVE,
            bar_index=int(i), bar_time=event_time,
            candidate_bar=max(0, int(i) - cfg.structure.confirm_bars + 1),
            candidate_time=_utc(m15.iloc[max(0, int(i) - cfg.structure.confirm_bars + 1)]["time"]),
            confirmation_bar=int(i), confirmation_time=event_time,
            tradable_bar=int(i), tradable_time=event_time,
            parent_object=ob.id, quality_score=quality,
            meta={"producer": "detect_market_structure", "lineage_relation": "BOS_CONFIRMS_OB_HTF"},
        )
        bos_objects.append(obj)
        bos_parent[obj.id] = ob

    displacement = detect_displacement(m15, cfg.displacement)
    displacement_objects: list[MarketObject] = []
    for i, row in displacement.loc[
        displacement["displacement_bullish"] | displacement["displacement_bearish"]
    ].iterrows():
        direction = 1 if bool(row["displacement_bullish"]) else -1
        event_time = _utc(m15.iloc[int(i)]["time"])
        candidates = [
            ob for ob in obs
            if ob.direction == direction
            and _utc(ob.tradable_time) <= event_time
            and event_time - _utc(ob.tradable_time) <= poi_window
            and _active_at(ob, h4, event_time)
        ]
        if not candidates:
            continue
        ob = max(candidates, key=lambda item: (_utc(item.tradable_time), item.id))
        obj = MarketObject(
            id=_event_id("DISP", "M15", event_time, direction), symbol=symbol,
            type=ObjectType.DISPLACEMENT, origin_tf="M15", role=Role.TRIGGER,
            direction=direction, zone_low=float(row["low"]), zone_high=float(row["high"]),
            creation_time=event_time, state=ObjectState.ACTIVE,
            bar_index=int(i), bar_time=event_time,
            candidate_bar=int(i), candidate_time=event_time,
            confirmation_bar=int(i), confirmation_time=event_time,
            tradable_bar=int(i), tradable_time=event_time,
            parent_object=ob.id,
            meta={"producer": "detect_displacement", "lineage_relation": "DISPLACEMENT_EVIDENCES_OB_HTF", "magnitude": float(row["displacement_magnitude"])},
        )
        displacement_objects.append(obj)

    raw_fvgs = detect_fvg(m15.to_dict("records"), timeframe="M15", symbol=symbol)
    linked_fvgs: list[MarketObject] = []
    for fvg in raw_fvgs:
        event_time = _utc(fvg.tradable_time)
        candidates = [
            ob for ob in obs
            if ob.direction == fvg.direction
            and _utc(ob.tradable_time) <= event_time
            and event_time - _utc(ob.tradable_time) <= poi_window
            and _overlaps(ob, fvg)
            and _active_at(ob, h4, event_time)
        ]
        if not candidates:
            continue
        ob = max(candidates, key=lambda item: (_utc(item.tradable_time), item.id))
        fvg.parent_object = ob.id
        fvg.meta["lineage_relation"] = "FVG_REFINES_OB_HTF"
        linked_fvgs.append(fvg)

    objects = sorted(
        [*obs, *linked_fvgs, *bos_objects, *displacement_objects],
        key=lambda item: (_utc(item.tradable_time), item.type.value, item.id),
    )
    return {
        "objects": objects,
        "counts": {
            "ob_h4": len(obs), "fvg_m15_linked": len(linked_fvgs),
            "bos_m15_linked": len(bos_objects), "displacement_m15_linked": len(displacement_objects),
        },
        "config": {
            "poi_to_child_max_hours": cfg.poi_to_child_max_hours,
        },
    }


__all__ = ["HistoricalEventConfig", "build_historical_event_objects"]
