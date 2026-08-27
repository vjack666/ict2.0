"""Causal timeline orchestration around the canonical MTF and Wyckoff engines.

This module deliberately contains no phase, event, signal or trade rules.  It
only builds closed prefixes, calls engine APIs, and records their observations.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

from backtest.schema import json_safe
from engine.Wyckoff import build_wyckoff_snapshot
from engine.mtf_navigation import MTFNavigator, NavigatorConfig


FSM_CONTRACT = "RUNTIME_BASIC_NOT_WYCKOFF_7"


def _closed_prefix(frame: pd.DataFrame, decision_time: pd.Timestamp) -> pd.DataFrame:
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    return frame.loc[times <= decision_time].copy().reset_index(drop=True)


def _asof(prefix: pd.DataFrame) -> str | None:
    if prefix.empty:
        return None
    value = pd.to_datetime(prefix["time"], utc=True, errors="coerce").max()
    return None if pd.isna(value) else value.isoformat()


def _asof_at(frame: pd.DataFrame, decision_time: pd.Timestamp) -> str | None:
    values = np.fromiter(
        (pd.Timestamp(value).value for value in pd.to_datetime(frame["time"], utc=True)),
        dtype="int64",
        count=len(frame),
    )
    index = int(np.searchsorted(values, decision_time.value, side="right") - 1)
    return None if index < 0 else pd.Timestamp(frame.iloc[index]["time"]).isoformat()


def _event_key(event: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(event.get("tf", "")),
        str(event.get("event_type", "")),
        str(event.get("event_time", "")),
        str(event.get("source_ref", "")),
    )


def _wrapper_id(key: tuple[str, str, str, str]) -> str:
    digest = hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:20]
    return f"WY_{digest}"


def _snapshot_events(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Collect engine events from every layer without creating new semantics."""

    events: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    layers = snapshot.get("layers") or {}
    for tf in sorted(layers):
        for event in layers[tf].get("events") or []:
            item = dict(event)
            item.setdefault("tf", tf)
            key = _event_key(item)
            if key not in seen:
                events.append(item)
                seen.add(key)
    for event in snapshot.get("events") or []:
        item = dict(event)
        key = _event_key(item)
        if key not in seen:
            events.append(item)
            seen.add(key)
    return events


def _delta(previous: Mapping[str, Any] | None, current: Mapping[str, Any], new_ids: list[str]) -> dict[str, Any]:
    keys = (
        "phase", "phase_state", "range_ref", "ict_alignment", "conflict",
        "volume_mode", "authority_tf",
    )
    changes: dict[str, dict[str, Any]] = {}
    if previous is None:
        changes = {key: {"from": None, "to": json_safe(current.get(key))} for key in keys}
    else:
        for key in keys:
            before = json_safe(previous.get(key))
            after = json_safe(current.get(key))
            if before != after:
                changes[key] = {"from": before, "to": after}
    return {
        "changed": bool(changes or new_ids),
        "fields": changes,
        "new_wyckoff_event_ids": list(new_ids),
        "interpretation": "OBSERVATIONAL_DELTA_NOT_SIGNAL",
    }


def build_wyckoff_timeline(
    frames: Mapping[str, pd.DataFrame],
    *,
    main_tf: str,
    authority_tf: str,
    visible_start_index: int,
    visible_end_index: int,
    layers: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build one canonical snapshot for each visible, fully closed main candle."""

    main_tf = main_tf.upper()
    authority_tf = authority_tf.upper()
    unique_layers = tuple(dict.fromkeys(tf.upper() for tf in layers if tf.upper() in frames))
    if main_tf not in frames:
        raise KeyError(f"missing main timeframe for timeline: {main_tf}")
    if authority_tf not in frames:
        raise KeyError(f"missing authority timeframe for timeline: {authority_tf}")

    main = frames[main_tf]
    timeline: list[dict[str, Any]] = []
    catalog: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    previous: dict[str, Any] | None = None
    cached_context_key: tuple[str | None, ...] | None = None
    cached_navigator: MTFNavigator | None = None

    for visible_index, source_position in enumerate(range(visible_start_index, visible_end_index + 1)):
        decision_time = pd.to_datetime(main.iloc[source_position]["time"], utc=True, errors="raise")
        prefix_tfs = tuple(dict.fromkeys((*unique_layers, "D1", "H4", "H1")))
        prefixes = {
            tf: _closed_prefix(frames[tf], decision_time)
            for tf in prefix_tfs if tf in frames
        }
        asof_by_tf = {tf: _asof_at(frame, decision_time) for tf, frame in frames.items()}
        context_frames = {
            tf: prefixes[tf]
            for tf in ("D1", "H4", "H1")
            if tf in prefixes and not prefixes[tf].empty
        }
        if context_frames:
            context_key = tuple(asof_by_tf.get(tf) for tf in ("D1", "H4", "H1"))
            if cached_navigator is None or context_key != cached_context_key:
                cached_navigator = MTFNavigator(context_frames, NavigatorConfig(precompute_sequences=False))
                cached_context_key = context_key
            context_exec_tf = authority_tf if authority_tf in context_frames else sorted(context_frames)[-1]
            context_state = cached_navigator.navigate(decision_time, exec_tf=context_exec_tf)
            context_payload = json_safe(context_state.to_dict())
        else:
            context_state = None
            context_payload = {
                "decision_time": decision_time.isoformat(),
                "exec_tf": main_tf,
                "status": "INCOMPLETE",
                "layers": {},
                "constraints": None,
                "path": {"steps": []},
                "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
            }

        engine_snapshot = build_wyckoff_snapshot(
            prefixes,
            decision_time,
            context_state=context_state,
            authority_tf=authority_tf,
            layers=unique_layers,
        )
        snapshot = json_safe(engine_snapshot.to_dict())
        snapshot.update({"range_id": None, "episode_id": None, "fsm_contract": FSM_CONTRACT})

        newly_seen: list[str] = []
        for event in _snapshot_events(snapshot):
            key = _event_key(event)
            wrapper_id = _wrapper_id(key)
            if key not in catalog:
                catalog[key] = {
                    "id": wrapper_id,
                    "engine_event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "tf": event.get("tf"),
                    "event_time": event.get("event_time"),
                    "source_ref": event.get("source_ref"),
                    "evidence_refs": list(event.get("evidence_refs") or []),
                    "confirmation_status": event.get("confirmation_status"),
                    "detail": event.get("detail") or {},
                    "first_seen_index": visible_index,
                    "first_seen_decision_time": decision_time.isoformat(),
                }
                newly_seen.append(wrapper_id)

        timeline.append(
            {
                "index": visible_index,
                "decision_time": decision_time.isoformat(),
                "asof_by_tf": asof_by_tf,
                "ict": {"context": context_payload, "visible_event_ids": []},
                "wyckoff": snapshot,
                "delta": _delta(previous, snapshot, newly_seen),
                "policy": "CLOSED_PREFIX_DIAGNOSTIC_ONLY",
            }
        )
        previous = snapshot

    events = sorted(
        catalog.values(),
        key=lambda item: (int(item["first_seen_index"]), str(item["tf"]), str(item["event_type"]), str(item["id"])),
    )
    return timeline, events


__all__ = ["FSM_CONTRACT", "build_wyckoff_timeline"]
