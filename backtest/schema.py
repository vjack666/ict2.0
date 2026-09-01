"""Schema and JSON serialization for the new visual-backtest artifact."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCHEMA_VERSION = "1.0"
MTF_SCHEMA_VERSION = "2.0"
MTF_ARTIFACT_KIND = "MTF_REPLAY"
MTF_REQUIRED_POLICY = {
    "diagnostic_only": True,
    "entry_authorized": False,
    "can_trade": False,
    "can_train": False,
    "promotion_authorized": False,
}


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy values into deterministic JSON-compatible values."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (float, np.floating)):
        return None if not np.isfinite(float(value)) else float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray, pd.Series)):
        return [json_safe(v) for v in list(value)]
    if pd.isna(value):
        return None
    return str(value)


@dataclass
class VisualBacktest:
    """Complete artifact consumed by the visualizer."""

    symbol: str
    timeframe: str
    candles: list[dict[str, Any]]
    events: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    signals: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candles": self.candles,
            "events": self.events,
            "trades": self.trades,
            "signals": self.signals,
            "metadata": self.metadata,
        }
        return json_safe(payload)


def logical_checksum(payload: dict[str, Any]) -> str:
    """Stable SHA-256 excluding volatile/storage-only fields."""

    excluded = {"checksum", "generated_at", "chunks"}
    core = {key: value for key, value in payload.items() if key not in excluded}
    encoded = json.dumps(json_safe(core), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class MTFReplayArtifact:
    """Canonical schema 2.0 artifact; a consumer projection, never an engine."""

    run_metadata: dict[str, Any]
    profiles: list[dict[str, Any]]
    candles_by_tf: dict[str, list[dict[str, Any]]]
    timeline: list[dict[str, Any]]
    market_state_checkpoints: list[dict[str, Any]] = field(default_factory=list)
    state_deltas: list[dict[str, Any]] = field(default_factory=list)
    setups: list[dict[str, Any]] = field(default_factory=list)
    episodes: list[dict[str, Any]] = field(default_factory=list)
    invalidations: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    rejections: list[dict[str, Any]] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=lambda: dict(MTF_REQUIRED_POLICY))

    def to_dict(self) -> dict[str, Any]:
        payload = json_safe(
            {
                "schema_version": MTF_SCHEMA_VERSION,
                "artifact_kind": MTF_ARTIFACT_KIND,
                "run_metadata": self.run_metadata,
                "policy": self.policy,
                "profiles": self.profiles,
                "candles_by_tf": self.candles_by_tf,
                "timeline": self.timeline,
                "market_state_checkpoints": self.market_state_checkpoints,
                "state_deltas": self.state_deltas,
                "setups": self.setups,
                "episodes": self.episodes,
                "invalidations": self.invalidations,
                "trades": self.trades,
                "rejections": self.rejections,
            }
        )
        payload["checksum"] = logical_checksum(payload)
        return payload


def validate_visual_backtest(payload: dict[str, Any]) -> None:
    """Fail closed when an exporter emits an incomplete or non-causal artifact."""

    required = {"schema_version", "symbol", "timeframe", "candles", "events", "trades"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"visual_backtest missing keys: {sorted(missing)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported visual_backtest schema: {payload['schema_version']}")

    candles = payload["candles"]
    if not isinstance(candles, list):
        raise ValueError("candles must be a list")
    for expected, candle in enumerate(candles):
        if candle.get("index") != expected:
            raise ValueError("candles must have contiguous zero-based indexes")

    event_ids: set[str] = set()
    for event in payload["events"]:
        event_id = str(event.get("id", ""))
        if not event_id or event_id in event_ids:
            raise ValueError(f"invalid or duplicate event id: {event_id!r}")
        event_ids.add(event_id)
        index = int(event["index"])
        confirmed = int(event["confirmed_index"])
        if not 0 <= index < len(candles) or not 0 <= confirmed < len(candles):
            raise ValueError(f"event outside candle range: {event_id}")
        if confirmed < index:
            raise ValueError(f"event confirmation precedes event index: {event_id}")
        parent_id = event.get("parent_id")
        if parent_id is not None and parent_id not in event_ids:
            raise ValueError(f"event parent must precede child: {event_id}")

    for trade in payload["trades"]:
        entry_index = int(trade["entry_index"])
        if not 0 <= entry_index < len(candles):
            raise ValueError("trade entry outside candle range")
        exit_index = trade.get("exit_index")
        if exit_index is not None and int(exit_index) < entry_index:
            raise ValueError("trade exit precedes entry")


def _record_time(record: dict[str, Any], collection: str) -> pd.Timestamp:
    raw = record.get("observation_time")
    if raw is None:
        raise ValueError(f"{collection} record missing observation_time")
    value = pd.to_datetime(raw, utc=True, errors="coerce")
    if pd.isna(value):
        raise ValueError(f"{collection} record has invalid observation_time")
    confirmation = record.get("confirmation_time")
    if confirmation is not None:
        confirmed = pd.to_datetime(confirmation, utc=True, errors="coerce")
        if pd.isna(confirmed) or confirmed > value:
            raise ValueError(f"{collection} confirmation is future data")
    return value


def validate_mtf_replay(payload: dict[str, Any]) -> None:
    """Validate schema 2.0 identity, time, lineage, policy and checksum."""

    required = {
        "schema_version", "artifact_kind", "run_metadata", "policy", "profiles",
        "candles_by_tf", "timeline", "market_state_checkpoints", "state_deltas",
        "setups", "episodes", "invalidations", "trades", "rejections", "checksum",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"mtf replay missing keys: {sorted(missing)}")
    if payload["schema_version"] != MTF_SCHEMA_VERSION or payload["artifact_kind"] != MTF_ARTIFACT_KIND:
        raise ValueError("unsupported MTF replay schema or artifact kind")
    for key, expected in MTF_REQUIRED_POLICY.items():
        if payload["policy"].get(key) is not expected:
            raise ValueError(f"unsafe policy flag: {key}")
    if not isinstance(payload["candles_by_tf"], dict) or not payload["candles_by_tf"]:
        raise ValueError("candles_by_tf must be a non-empty mapping")
    for tf, candles in payload["candles_by_tf"].items():
        last_time: pd.Timestamp | None = None
        for index, candle in enumerate(candles):
            if candle.get("index") != index or candle.get("tf") != tf:
                raise ValueError(f"non-contiguous or mismatched candle in {tf}")
            now = _record_time(candle, f"candles_by_tf.{tf}")
            if last_time is not None and now <= last_time:
                raise ValueError(f"out-of-order candle in {tf}")
            last_time = now

    collections = ("timeline", "state_deltas", "setups", "episodes", "invalidations", "trades", "rejections")
    known_ids: set[str] = set()
    record_times: dict[str, pd.Timestamp] = {}
    all_records: list[tuple[str, dict[str, Any]]] = []
    for collection in collections:
        rows = payload[collection]
        if not isinstance(rows, list):
            raise ValueError(f"{collection} must be a list")
        for record in rows:
            record_time = _record_time(record, collection)
            record_id = str(record.get("id", ""))
            if not record_id or record_id in known_ids:
                raise ValueError(f"invalid or duplicate record id: {record_id!r}")
            known_ids.add(record_id)
            record_times[record_id] = record_time
            all_records.append((collection, record))
    graph: dict[str, list[str]] = {}
    for collection, record in all_records:
        graph[record["id"]] = list(record.get("parent_ids", []))
        for parent_id in record.get("parent_ids", []):
            if parent_id not in known_ids:
                raise ValueError(f"broken lineage in {collection}: {parent_id}")
            if record_times[parent_id] > record_times[record["id"]]:
                raise ValueError(f"future lineage in {collection}: {parent_id}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError(f"cyclic lineage: {node}")
        if node in visited:
            return
        visiting.add(node)
        for parent in graph.get(node, []):
            visit(parent)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    if logical_checksum(payload) != payload["checksum"]:
        raise ValueError("MTF replay checksum mismatch")


def write_visual_backtest(payload: dict[str, Any], output: Path) -> None:
    """Write a validated artifact atomically."""

    import json

    validate_visual_backtest(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


def write_mtf_replay(payload: dict[str, Any], output: Path) -> None:
    """Validate and atomically write one canonical schema 2.0 artifact."""

    validate_mtf_replay(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
