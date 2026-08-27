"""Projection of the canonical engine state into a persistent Market State per candle.

This module is a READ-ONLY projection (FASE 4, SDD v1.2). It does NOT compute new
ICT/Wyckoff rules and it is NOT a second engine. It reuses the canonical
MarketObjects created by ``engine/sequence.py`` (sequence ICT objects) and by the
canonical detectors ``engine/detectors/fvg.py`` / ``engine/detectors/ob.py``
(FVG/OB regions) and exposes them per ``decision_time`` with their lifecycle.

Market State(T) = the causal set of entities and states the engine knew and that
were still in force at ``decision_time=T``. No future information is used: every
snapshot only considers data with ``time <= decision_time`` (no look-ahead).
Terminal objects (MITIGATED/INVALIDATED/EXPIRED/CONSUMED) are kept as history for
traceability but are not drawn as active entities.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.market_object import MarketObject, ObjectState
from backtest.schema import json_safe, stable_sha256


def _detect_regions(frames: Mapping[str, pd.DataFrame], symbol: str) -> dict[str, list[MarketObject]]:
    """Detect FVG/OB regions per TF over the full frame.

    Both detectors are causal: they only use data through the confirmation candle
    (``tradable_time``). Filtering by ``tradable_time <= decision_time`` later
    guarantees no look-ahead.
    """
    regions: dict[str, list[MarketObject]] = {}
    for tf, frame in frames.items():
        rows = frame.to_dict("records")
        fvgs = detect_fvg(rows, timeframe=tf, symbol=symbol)
        obs = detect_order_blocks(rows, timeframe=tf, symbol=symbol)
        regions[tf] = [*fvgs, *obs]
    return regions


def _collect_sequence_objects(signals: list[dict[str, Any]]) -> dict[str, MarketObject]:
    """Collect the canonical sequence ICT MarketObjects from signal event_objects.

    Each signal carries ``event_objects`` (a snapshot of the engine state at the
    signal instant). We keep the first occurrence per id (creation state); the
    objects are immutable after creation for the sequence phase.
    """
    raw_objects: dict[str, dict[str, Any]] = {}
    for signal in signals:
        for obj_id, obj_dict in (signal.get("event_objects") or {}).items():
            if obj_id in raw_objects:
                continue
            if isinstance(obj_dict, dict):
                raw_objects[obj_id] = dict(obj_dict)

    # The canonical sequence engine historically uses UUIDs for event objects.
    # UUIDs are valid runtime identities but make two causal replays of the same
    # prefix differ, which breaks deterministic artifact hashes and FULL/PREFIX
    # comparison. Normalize only this read-only projection; the engine objects
    # and their causal relationships remain untouched.
    id_map: dict[str, str] = {}
    for raw_id, obj_dict in raw_objects.items():
        identity = {
            key: obj_dict.get(key)
            for key in (
                "type", "origin_tf", "role", "direction", "creation_time",
                "candidate_time", "confirmation_time", "tradable_time",
                "bar_index", "bar_time", "zone_high", "zone_low", "meta",
            )
        }
        id_map[raw_id] = f"SEQ_{str(obj_dict.get('type', 'OBJECT'))}_{stable_sha256(identity)[:16]}"

    collected: dict[str, MarketObject] = {}
    for raw_id, original in raw_objects.items():
        obj_dict = dict(original)
        obj_dict["id"] = id_map[raw_id]
        if obj_dict.get("parent_object") in id_map:
            obj_dict["parent_object"] = id_map[obj_dict["parent_object"]]
        obj_dict["related_objects"] = [id_map.get(item, item) for item in obj_dict.get("related_objects", [])]
        try:
            collected[obj_dict["id"]] = MarketObject.from_dict(obj_dict)
        except (KeyError, TypeError, ValueError):
            # Skip malformed objects defensively; the canonical engine always
            # emits well-formed ones, but a projection must not crash the replay.
            continue
    return collected


def _touches(row: Any, zone_high: float, zone_low: float) -> bool:
    return float(row["low"]) <= float(zone_high) and float(row["high"]) >= float(zone_low)


def build_market_state(
    frames: Mapping[str, pd.DataFrame],
    signals: list[dict[str, Any]],
    config: Any,
    visible_start: int,
    visible_end: int,
) -> list[dict[str, Any]]:
    """Build a persistent Market State snapshot per visible candle.

    Returns a list of snapshots (one per visible candle index in
    ``[visible_start, visible_end]``), each with ``decision_time``, ``authority_tf``,
    ``entities`` (live), ``terminal_entities`` (history) and ``delta``.
    """
    main_tf = config.timeframe.upper()
    main_frame = frames[main_tf]
    authority_tf = config.authority_tf.upper()

    regions = _detect_regions(frames, config.symbol)
    sequence_objects = _collect_sequence_objects(signals)

    # Index sequence objects by creation_time for per-candle activation.
    seq_by_time: list[tuple[pd.Timestamp, MarketObject]] = []
    for obj in sequence_objects.values():
        created = pd.to_datetime(obj.creation_time, utc=True, errors="coerce")
        if pd.notna(created):
            seq_by_time.append((created, obj))
    seq_by_time.sort(key=lambda pair: (pair[0], pair[1].id))

    # Live / history registries keyed by object id.
    live: dict[str, MarketObject] = {}
    history: dict[str, MarketObject] = {}

    snapshots: list[dict[str, Any]] = []
    prev_live_ids: set[str] = set()
    prev_states: dict[str, str] = {}

    for i in range(visible_start, visible_end + 1):
        decision_time = main_frame.iloc[i]["time"]
        decision = pd.to_datetime(decision_time, utc=True, errors="coerce")

        # 1) Activate FVG/OB regions whose tradable_time <= decision_time.
        for tf, objs in regions.items():
            for obj in objs:
                if obj.id in live or obj.id in history:
                    continue
                tt = pd.to_datetime(obj.tradable_time, utc=True, errors="coerce")
                if pd.notna(tt) and tt <= decision:
                    live[obj.id] = obj

        # 2) Activate sequence ICT objects whose creation_time <= decision_time.
        for created, obj in seq_by_time:
            if obj.id in live or obj.id in history:
                continue
            if created <= decision:
                live[obj.id] = obj

        # 3) Apply causal touch observation for the current candle on FVG/OB
        #    regions (strictly after tradable_time; the confirmation candle does
        #    not count as a retest). Replicates ltf_canonical_feed._touch_state.
        row = main_frame.iloc[i]
        for obj in live.values():
            if obj.type.value in ("FVG", "ORDER_BLOCK") and obj.state is ObjectState.ACTIVE:
                tt = pd.to_datetime(obj.tradable_time, utc=True, errors="coerce")
                if pd.notna(tt) and tt < decision and _touches(row, obj.zone_high, obj.zone_low):
                    obj.touch_count += 1
                    if obj.first_touch_time is None:
                        obj.first_touch_time = row["time"]
                        obj.first_touch_bar = int(i)
                    obj.state = ObjectState.PARTIALLY_MITIGATED

        # 4) Move terminal objects to history (traceability, not drawn active).
        for obj_id in list(live.keys()):
            if live[obj_id].is_terminal:
                history[obj_id] = live.pop(obj_id)

        # 5) Compute delta of entities since T-1.
        live_ids = set(live.keys())
        created_ids = sorted(live_ids - prev_live_ids)
        terminal_ids = sorted(set(history.keys()) & prev_live_ids)
        transitioned: list[dict[str, Any]] = []
        for obj_id in sorted(live_ids):
            prev_state = prev_states.get(obj_id)
            current_state = live[obj_id].state.value
            if prev_state is not None and prev_state != current_state:
                transitioned.append({"id": obj_id, "from": prev_state, "to": current_state})

        # 6) Build the snapshot.
        entities = [obj.to_dict() for obj in sorted(live.values(), key=lambda o: (o.origin_tf, o.id))]
        terminal_entities = [
            obj.to_dict() for obj in sorted(history.values(), key=lambda o: (o.origin_tf, o.id))
        ]
        snapshots.append(
            {
                "decision_time": decision_time.isoformat(),
                "authority_tf": authority_tf,
                "entities": json_safe(entities),
                "terminal_entities": json_safe(terminal_entities),
                "delta": {
                    "created": created_ids,
                    "transitioned": transitioned,
                    "terminal": terminal_ids,
                },
            }
        )

        prev_live_ids = live_ids
        prev_states = {obj_id: live[obj_id].state.value for obj_id in live}

    return snapshots


__all__ = ["build_market_state"]
