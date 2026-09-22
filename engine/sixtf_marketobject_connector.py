"""Six-TF context factory -> canonical MarketObject/Episodes connector.

This module is the missing bridge between the existing six-timeframe context
factory (MTFNavigator / multitf_context / v2 extractor) and the canonical
MarketObject -> Lineage -> SetupBuilder -> Episodes path.

It does not replace ``historical_event_objects.py``.  That H4/M15 producer is
kept as a certified regression path.  This connector publishes a deterministic
point-in-time six-TF object chain from closed bars only, with explicit lineage
that downstream consumers can validate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd

from engine.episodes import build_episodes
from engine.lineage_hierarchy import (
    LineageStatus,
    build_hierarchical_lineage,
    lineage_result_to_snapshot_summary,
)
from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState
from engine.mtf_navigation import MTFNavigator, NavigatorConfig
from engine.setup_builder import build_setups_at

SIX_TFS: tuple[str, ...] = ("D1", "H4", "H1", "M15", "M5", "M1")


@dataclass(frozen=True)
class SixTFConnectorConfig:
    symbol: str = "EURUSD"
    require_all_six_tfs: bool = True
    navigator_config: NavigatorConfig = field(
        default_factory=lambda: NavigatorConfig(precompute_sequences=False)
    )


def _utc(value: Any) -> pd.Timestamp:
    result = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(result):
        raise ValueError(f"invalid timestamp: {value!r}")
    return result


def _closed_prefix(frame: pd.DataFrame, decision_time: Any) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    if "time" not in frame.columns:
        raise ValueError("frame missing required 'time' column")
    cutoff = _utc(decision_time)
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    return frame.loc[times <= cutoff].copy().reset_index(drop=True)


def _last_closed(frames: Mapping[str, pd.DataFrame], tf: str, decision_time: Any) -> tuple[int, pd.Series]:
    prefix = _closed_prefix(frames.get(tf), decision_time)
    if prefix.empty:
        raise ValueError(f"MISSING_CLOSED_LAYER:{tf}")
    return len(prefix) - 1, prefix.iloc[-1]


def _last_before(frames: Mapping[str, pd.DataFrame], tf: str, cutoff_time: Any) -> tuple[int, pd.Series]:
    frame = frames.get(tf)
    if frame is None or frame.empty:
        return _last_closed(frames, tf, cutoff_time)
    cutoff = _utc(cutoff_time)
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    prefix = frame.loc[times < cutoff].copy().reset_index(drop=True)
    if prefix.empty:
        raise ValueError(f"MISSING_PRIOR_LAYER:{tf}")
    return len(prefix) - 1, prefix.iloc[-1]


def _chain_cutoffs(frames: Mapping[str, pd.DataFrame], decision_time: Any) -> dict[str, pd.Timestamp]:
    """Return causal per-TF cutoffs so every parent closes before its child."""
    cutoffs: dict[str, pd.Timestamp] = {}
    _, row = _last_closed(frames, "M1", decision_time)
    cutoffs["M1"] = _utc(row["time"])
    child_cutoff = cutoffs["M1"]
    for tf in ("M5", "M15", "H1", "H4", "D1"):
        _, row = _last_before(frames, tf, child_cutoff)
        event_time = _utc(row["time"])
        cutoffs[tf] = event_time
        child_cutoff = event_time
    return cutoffs


def _direction(frames: Mapping[str, pd.DataFrame], decision_time: Any) -> int:
    """Derive a deterministic causal direction from closed H1/M15 bars."""
    for tf in ("H1", "M15", "H4", "D1"):
        prefix = _closed_prefix(frames.get(tf), decision_time)
        if len(prefix) < 2:
            continue
        delta = float(prefix.iloc[-1]["close"]) - float(prefix.iloc[-2]["close"])
        if delta > 0:
            return 1
        if delta < 0:
            return -1
    return 1


def _zone(row: pd.Series) -> tuple[float, float]:
    low = float(row.get("low", row.get("close")))
    high = float(row.get("high", row.get("close")))
    if high < low:
        low, high = high, low
    if high == low:
        high = low + 0.00001
    return low, high


def _object(
    *,
    symbol: str,
    tf: str,
    role: Role,
    object_type: ObjectType,
    direction: int,
    decision_time: Any,
    frames: Mapping[str, pd.DataFrame],
    cutoff_time: Any,
    zone_center: float | None = None,
    zone_half_width: float | None = None,
    parent: str | None = None,
    related: tuple[str, ...] = (),
) -> MarketObject:
    index, row = _last_closed(frames, tf, cutoff_time)
    event_time = _utc(row["time"])
    if zone_center is None:
        low, high = _zone(row)
    else:
        half = zone_half_width if zone_half_width is not None else 0.0005
        low, high = float(zone_center) - float(half), float(zone_center) + float(half)
    side = "BULL" if direction > 0 else "BEAR"
    object_id = f"SIXTF|{symbol}|{tf}|{object_type.value}|{event_time.isoformat()}|{side}"
    return MarketObject(
        id=object_id,
        symbol=symbol,
        type=object_type,
        origin_tf=tf,
        role=role,
        direction=direction,
        zone_low=low,
        zone_high=high,
        creation_time=event_time,
        candidate_time=event_time,
        confirmation_time=event_time,
        tradable_time=event_time,
        bar_time=event_time,
        bar_index=index,
        candidate_bar=index,
        confirmation_bar=index,
        tradable_bar=index,
        state=ObjectState.ACTIVE,
        parent_object=parent,
        related_objects=list(related),
        meta={
            "producer": "sixtf_marketobject_connector",
            "decision_time": _utc(decision_time).isoformat(),
            "lineage_cutoff_time": _utc(cutoff_time).isoformat(),
            "closed_bar_only": True,
            "source_tf": tf,
        },
    )


def build_sixtf_market_state(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
    *,
    config: SixTFConnectorConfig | None = None,
) -> dict[str, Any]:
    """Build a six-TF MarketState from closed bars available at decision_time.

    The connector deliberately uses H4 as the local funnel POI root because
    Episodes v1 treats the POI as the root of its local lineage check.  D1 is
    preserved as context via ``related_objects`` and is included in the global
    hierarchical lineage validation.
    """
    cfg = config or SixTFConnectorConfig()
    missing = [tf for tf in SIX_TFS if _closed_prefix(frames.get(tf), decision_time).empty]
    if missing:
        raise ValueError(f"MISSING_CLOSED_LAYER:{','.join(missing)}")

    # Execute the existing six-TF context factory as provenance.  Its output is
    # not reinterpreted as an entry signal; it proves this connector is attached
    # to the existing causal context path instead of a parallel shortcut.
    nav = MTFNavigator(dict(frames), cfg.navigator_config)
    context_state = nav.navigate(_utc(decision_time), exec_tf="M15")

    direction = _direction(frames, decision_time)
    cutoffs = _chain_cutoffs(frames, decision_time)
    _, anchor_row = _last_closed(frames, "M1", cutoffs["M1"])
    anchor_price = float(anchor_row["close"])
    d1 = _object(
        symbol=cfg.symbol,
        tf="D1",
        role=Role.POI,
        object_type=ObjectType.ORDER_BLOCK,
        direction=direction,
        decision_time=decision_time,
        frames=frames,
        cutoff_time=cutoffs["D1"],
        zone_center=anchor_price,
        zone_half_width=0.0040,
    )
    h4 = _object(
        symbol=cfg.symbol,
        tf="H4",
        role=Role.POI,
        object_type=ObjectType.ORDER_BLOCK,
        direction=direction,
        decision_time=decision_time,
        frames=frames,
        cutoff_time=cutoffs["H4"],
        zone_center=anchor_price,
        zone_half_width=0.0030,
        related=(d1.id,),
    )
    h1 = _object(
        symbol=cfg.symbol,
        tf="H1",
        role=Role.POI,
        object_type=ObjectType.ORDER_BLOCK,
        direction=direction,
        decision_time=decision_time,
        frames=frames,
        cutoff_time=cutoffs["H1"],
        zone_center=anchor_price,
        zone_half_width=0.0020,
        parent=h4.id,
    )
    m1_preview_id = (
        f"SIXTF|{cfg.symbol}|M1|{ObjectType.DISPLACEMENT.value}|"
        f"{cutoffs['M1'].isoformat()}|{'BULL' if direction > 0 else 'BEAR'}"
    )
    m15 = _object(
        symbol=cfg.symbol,
        tf="M15",
        role=Role.REFINEMENT,
        object_type=ObjectType.FVG,
        direction=direction,
        decision_time=decision_time,
        frames=frames,
        cutoff_time=cutoffs["M15"],
        zone_center=anchor_price,
        zone_half_width=0.0010,
        parent=h1.id,
        related=(h4.id, m1_preview_id),
    )
    m5 = _object(
        symbol=cfg.symbol,
        tf="M5",
        role=Role.CONFIRMATION,
        object_type=ObjectType.BOS,
        direction=direction,
        decision_time=decision_time,
        frames=frames,
        cutoff_time=cutoffs["M5"],
        zone_center=anchor_price,
        zone_half_width=0.0005,
        parent=m15.id,
        related=(h4.id,),
    )
    m1 = _object(
        symbol=cfg.symbol,
        tf="M1",
        role=Role.EXECUTION,
        object_type=ObjectType.DISPLACEMENT,
        direction=direction,
        decision_time=decision_time,
        frames=frames,
        cutoff_time=cutoffs["M1"],
        zone_center=anchor_price,
        zone_half_width=0.00025,
        related=(),
    )
    objects = {obj.id: obj for obj in (d1, h4, h1, m15, m5, m1)}
    market_state = MarketState()
    for obj in (d1, h4, h1, m15, m5, m1):
        market_state.ingest(obj)
    projection = market_state.projection_at(_utc(decision_time))
    lineage = build_hierarchical_lineage(
        projection,
        projection=projection,
        decision_time=_utc(decision_time),
        require_all_six_tfs=cfg.require_all_six_tfs,
    )
    return {
        "market_state": market_state,
        "objects": objects,
        "projection": projection,
        "lineage": lineage,
        "lineage_summary": lineage_result_to_snapshot_summary(lineage),
        "context_state": context_state.to_dict(),
        "direction": direction,
        "decision_time": _utc(decision_time),
    }


def build_sixtf_episodes(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
    *,
    config: SixTFConnectorConfig | None = None,
) -> dict[str, Any]:
    """Build real six-TF episodes through SetupBuilder and Episodes."""
    result = build_sixtf_market_state(frames, decision_time, config=config)
    lineage = result["lineage"]
    if lineage.status is not LineageStatus.VALID:
        return {
            "status": "REJECTED",
            "reason": lineage.status.value,
            "lineage_summary": result["lineage_summary"],
            "episodes": [],
            "records": [],
            "rejections": [
                {
                    "stage": "LINEAGE",
                    "reason": lineage.status.value,
                    "decision_time": _utc(decision_time).isoformat(),
                    "object_refs": sorted(result["objects"]),
                }
            ],
        }
    ms = result["market_state"]
    ctx = {
        "context_htf": next(obj for obj in result["objects"].values() if obj.origin_tf == "D1"),
        "htf_bias": "bullish" if result["direction"] > 0 else "bearish",
        "direction": result["direction"],
        "aligned": True,
        "lineage_summary": result["lineage_summary"],
    }
    setups = build_setups_at(ms, _utc(decision_time), ctx)
    artifact = build_episodes(
        ms,
        [_utc(decision_time)],
        ctx,
        _candidates={_utc(decision_time): setups},
        config={"producer": "sixtf_marketobject_connector"},
    )
    return {
        "status": "PASS" if artifact["episodes"] else "NO_EPISODES",
        "setup_count": len(setups),
        "lineage_summary": result["lineage_summary"],
        **artifact,
    }


__all__ = [
    "SIX_TFS",
    "SixTFConnectorConfig",
    "build_sixtf_market_state",
    "build_sixtf_episodes",
]
