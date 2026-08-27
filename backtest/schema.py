"""Versioned schema and deterministic serialization for visual replay artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import numpy as np
import pandas as pd


SCHEMA_VERSION = "1.2"
REQUIRED_POLICY = {
    "diagnostic_only": True,
    "entry_authorized": False,
    "can_trade": False,
    "can_train": False,
    "promotion_authorized": False,
}

# Operational lineage is disclosed in the artifact but deliberately excluded
# from its scientific content hash. Branch names, worktree cleanliness and
# runtime versions can change without changing code, normalized configuration
# or the certified data slice.
CONTENT_HASH_EXCLUDED_METADATA = {
    "artifact_content_sha256",
    "git_branch",
    "generator_worktree_clean_before_run",
    "python_version",
    "node_version",
}


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy values into deterministic JSON-compatible values."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (float, np.floating)):
        return None if not np.isfinite(float(value)) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set, np.ndarray, pd.Series)):
        return [json_safe(item) for item in list(value)]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def canonical_json(value: Any) -> str:
    """Return the one canonical representation used by every replay hash."""

    return json.dumps(
        json_safe(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def artifact_content_sha256(payload: dict[str, Any]) -> str:
    """Hash a payload excluding only its self-referential content hash."""

    clean = json_safe(payload)
    metadata = dict(clean.get("run_metadata") or {})
    for key in CONTENT_HASH_EXCLUDED_METADATA:
        metadata.pop(key, None)
    clean["run_metadata"] = metadata
    return stable_sha256(clean)


def finalize_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    finalized = json_safe(payload)
    finalized.setdefault("run_metadata", {})["artifact_content_sha256"] = artifact_content_sha256(finalized)
    return finalized


@dataclass
class VisualBacktest:
    """Complete v1.1 artifact consumed by the local visualizer."""

    symbol: str
    timeframe: str
    authority_tf: str
    visible_window: dict[str, Any]
    policy: dict[str, Any]
    candles: list[dict[str, Any]]
    structure_events: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    wyckoff_events: list[dict[str, Any]]
    data_manifest: dict[str, Any]
    run_metadata: dict[str, Any]
    scientific_status: dict[str, Any]
    market_state: list[dict[str, Any]] = field(default_factory=list)
    setups: list[dict[str, Any]] = field(default_factory=list)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)

    @property
    def events(self) -> list[dict[str, Any]]:
        """Compatibility alias for older callers; not emitted in v1.1 JSON."""

        return self.structure_events

    @property
    def metadata(self) -> dict[str, Any]:
        """Compatibility alias for older callers; not emitted in v1.1 JSON."""

        return self.run_metadata

    def to_dict(self) -> dict[str, Any]:
        return finalize_artifact(
            {
                "schema_version": self.schema_version,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "authority_tf": self.authority_tf,
                "visible_window": self.visible_window,
                "policy": self.policy,
                "candles": self.candles,
                "structure_events": self.structure_events,
                "trades": self.trades,
                "timeline": self.timeline,
                "wyckoff_events": self.wyckoff_events,
                "data_manifest": self.data_manifest,
                "run_metadata": self.run_metadata,
                "scientific_status": self.scientific_status,
                "market_state": self.market_state,
                "setups": self.setups,
            }
        )


def _timestamp(value: Any, *, field_name: str) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        raise ValueError(f"invalid UTC timestamp in {field_name}: {value!r}")
    return timestamp


def _assert_no_nonfinite(value: Any, path: str = "payload") -> None:
    if isinstance(value, (float, np.floating)) and not np.isfinite(float(value)):
        raise ValueError(f"non-finite numeric value at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_nonfinite(item, f"{path}[{index}]")


def _require_fields(value: Any, required: set[str], *, scope: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{scope} must be an object")
    missing = required - set(value)
    if missing:
        raise ValueError(f"{scope} missing keys: {sorted(missing)}")
    return value


def _is_absolute_path(value: str) -> bool:
    return PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()


def validate_visual_backtest(payload: dict[str, Any]) -> None:
    """Fail closed on incomplete, unsafe, non-causal or non-reproducible artifacts."""

    _assert_no_nonfinite(payload)
    required = {
        "schema_version", "symbol", "timeframe", "authority_tf", "visible_window",
        "policy", "candles", "structure_events", "trades", "timeline",
        "wyckoff_events", "data_manifest", "run_metadata", "scientific_status",
        "market_state", "setups",
    }
    missing = required - set(payload)
    if missing:
        raise ValueError(f"visual_backtest missing keys: {sorted(missing)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported visual_backtest schema: {payload['schema_version']!r}; expected {SCHEMA_VERSION}")
    for flag, expected in REQUIRED_POLICY.items():
        if payload["policy"].get(flag) is not expected:
            raise ValueError(f"unsafe policy flag {flag}: expected {expected!r}")

    candles = payload["candles"]
    timeline = payload["timeline"]
    if not isinstance(candles, list) or not candles:
        raise ValueError("candles must be a non-empty list")
    if not isinstance(timeline, list) or len(timeline) != len(candles):
        raise ValueError("timeline must contain exactly one point per visible candle")

    window = _require_fields(
        payload["visible_window"],
        {"start", "end", "warmup_bars", "rows", "index_semantics"},
        scope="visible_window",
    )
    if int(window["rows"]) != len(candles) or int(window["warmup_bars"]) < 0:
        raise ValueError("visible_window rows or warmup_bars are inconsistent")

    manifest = _require_fields(
        payload["data_manifest"],
        {"symbol", "timezone", "timestamp_semantics", "timeframes", "mutation_policy"},
        scope="data_manifest",
    )
    if manifest["symbol"] != payload["symbol"] or manifest["timezone"] != "UTC":
        raise ValueError("data_manifest symbol/timezone mismatch")
    if manifest["mutation_policy"] != "READ_ONLY_NO_DOWNLOADS":
        raise ValueError("data_manifest must be read-only and download-free")
    timeframe_manifest = manifest.get("timeframes")
    if not isinstance(timeframe_manifest, dict) or not timeframe_manifest:
        raise ValueError("data_manifest.timeframes must be non-empty")

    prior_close: pd.Timestamp | None = None
    for expected_index, (candle, point) in enumerate(zip(candles, timeline, strict=True)):
        candle = _require_fields(
            candle,
            {
                "index", "source_index", "bar_open_time", "bar_close_time",
                "available_time", "open", "high", "low", "close",
            },
            scope=f"candles[{expected_index}]",
        )
        point = _require_fields(
            point,
            {"index", "decision_time", "asof_by_tf", "ict", "wyckoff", "delta"},
            scope=f"timeline[{expected_index}]",
        )
        if candle.get("index") != expected_index or point.get("index") != expected_index:
            raise ValueError("candles and timeline must use contiguous matching zero-based indexes")
        opened = _timestamp(candle.get("bar_open_time"), field_name="bar_open_time")
        closed = _timestamp(candle.get("bar_close_time"), field_name="bar_close_time")
        available = _timestamp(candle.get("available_time"), field_name="available_time")
        decision = _timestamp(point.get("decision_time"), field_name="decision_time")
        if opened >= closed or available != closed or decision != closed:
            raise ValueError(f"invalid candle availability at index {expected_index}")
        if prior_close is not None and closed <= prior_close:
            raise ValueError("visible candle close times must be strictly increasing")
        prior_close = closed
        prices: dict[str, float] = {}
        for field_name in ("open", "high", "low", "close"):
            value = candle.get(field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
                raise ValueError(f"candle OHLC must be finite numeric: {field_name}")
            prices[field_name] = float(value)
        if (
            prices["low"] > min(prices["open"], prices["close"])
            or prices["high"] < max(prices["open"], prices["close"])
            or prices["low"] > prices["high"]
        ):
            raise ValueError(f"incoherent candle OHLC at index {expected_index}")
        asof_by_tf = point.get("asof_by_tf") or {}
        if set(asof_by_tf) != set(timeframe_manifest):
            raise ValueError(f"asof_by_tf keys mismatch at timeline index {expected_index}")
        for tf, asof in asof_by_tf.items():
            if asof is not None and _timestamp(asof, field_name=f"asof_by_tf.{tf}") > decision:
                raise ValueError(f"future as-of detected at timeline index {expected_index}: {tf}")
        ict = _require_fields(
            point.get("ict"), {"context", "visible_event_ids"}, scope=f"timeline[{expected_index}].ict"
        )
        if not isinstance(ict["visible_event_ids"], list):
            raise ValueError("ict.visible_event_ids must be a list")
        snapshot = _require_fields(
            point.get("wyckoff"),
            {"authority_tf", "decision_time", "range_id", "episode_id", "fsm_contract"},
            scope=f"timeline[{expected_index}].wyckoff",
        )
        if snapshot.get("fsm_contract") != "RUNTIME_BASIC_NOT_WYCKOFF_7":
            raise ValueError("timeline must disclose the basic non-WYCKOFF-7 runtime")
        if snapshot.get("range_id") is not None or snapshot.get("episode_id") is not None:
            raise ValueError("basic runtime cannot claim range_id or episode_id")
        if _timestamp(snapshot["decision_time"], field_name="wyckoff.decision_time") != decision:
            raise ValueError("Wyckoff snapshot decision_time mismatch")
        if snapshot.get("policy") != "WYCKOFF_DISABLED" and snapshot.get("authority_tf") != payload["authority_tf"]:
            raise ValueError("Wyckoff authority is absent or inconsistent")

    if _timestamp(window["start"], field_name="visible_window.start") != _timestamp(
        candles[0]["bar_close_time"], field_name="candles.first"
    ) or _timestamp(window["end"], field_name="visible_window.end") != _timestamp(
        candles[-1]["bar_close_time"], field_name="candles.last"
    ):
        raise ValueError("visible_window boundaries do not match visible candles")

    event_ids: set[str] = set()
    event_positions: dict[str, int] = {}
    event_by_id: dict[str, dict[str, Any]] = {}
    for position, event in enumerate(payload["structure_events"]):
        event = _require_fields(
            event,
            {
                "id", "kind", "index", "confirmed_index", "time", "confirmed_time",
                "parent_id", "direction", "price", "status",
            },
            scope=f"structure_events[{position}]",
        )
        event_id = str(event.get("id", ""))
        if not event_id or event_id in event_ids:
            raise ValueError(f"invalid or duplicate structure event id: {event_id!r}")
        event_ids.add(event_id)
        event_positions[event_id] = position
        event_by_id[event_id] = event
        index = int(event["index"])
        confirmed = int(event["confirmed_index"])
        if not 0 <= index < len(candles) or not 0 <= confirmed < len(candles):
            raise ValueError(f"structure event outside visible range: {event_id}")
        if confirmed < index:
            raise ValueError(f"structure event confirmation precedes event index: {event_id}")
        born = _timestamp(event["time"], field_name="structure.time")
        confirmed_time = _timestamp(event["confirmed_time"], field_name="structure.confirmed_time")
        decision = _timestamp(candles[confirmed]["bar_close_time"], field_name="structure.candle")
        if born > confirmed_time or confirmed_time > decision:
            raise ValueError(f"structure event visible before confirmation: {event_id}")

    for event_id, event in event_by_id.items():
        parent_id = event.get("parent_id")
        if parent_id is None:
            continue
        if parent_id not in event_by_id or event_positions[parent_id] >= event_positions[event_id]:
            raise ValueError(f"structure event parent must precede child: {event_id}")
        if int(event_by_id[parent_id]["confirmed_index"]) > int(event["confirmed_index"]):
            raise ValueError(f"structure event parent is later than child: {event_id}")

    for point in timeline:
        cursor = int(point["index"])
        decision = _timestamp(point["decision_time"], field_name="timeline.decision_time")
        expected_ids = [
            event["id"]
            for event in payload["structure_events"]
            if int(event["confirmed_index"]) <= cursor
            and _timestamp(event["confirmed_time"], field_name="structure.confirmed_time") <= decision
        ]
        if point["ict"]["visible_event_ids"] != expected_ids:
            raise ValueError(f"structure event visibility mismatch at timeline index {cursor}")

    wyckoff_ids: set[str] = set()
    for position, event in enumerate(payload["wyckoff_events"]):
        event = _require_fields(
            event,
            {
                "id", "engine_event_id", "event_type", "tf", "event_time",
                "first_seen_index", "first_seen_decision_time", "source_ref",
                "evidence_refs", "confirmation_status", "detail",
            },
            scope=f"wyckoff_events[{position}]",
        )
        wrapper_id = str(event.get("id", ""))
        if not wrapper_id or wrapper_id in wyckoff_ids:
            raise ValueError(f"invalid or duplicate Wyckoff wrapper id: {wrapper_id!r}")
        wyckoff_ids.add(wrapper_id)
        first_seen = int(event["first_seen_index"])
        if not 0 <= first_seen < len(candles):
            raise ValueError(f"Wyckoff event outside visible range: {wrapper_id}")
        first_seen_time = _timestamp(
            event["first_seen_decision_time"], field_name="wyckoff.first_seen_decision_time"
        )
        if first_seen_time != _timestamp(timeline[first_seen]["decision_time"], field_name="timeline.first_seen"):
            raise ValueError(f"Wyckoff first-seen decision mismatch: {wrapper_id}")
        if _timestamp(event["event_time"], field_name="wyckoff.event_time") > _timestamp(
            candles[first_seen]["bar_close_time"], field_name="wyckoff.first_seen"
        ):
            raise ValueError(f"Wyckoff event appears before it is observable: {wrapper_id}")
        if wrapper_id not in timeline[first_seen]["delta"].get("new_wyckoff_event_ids", []):
            raise ValueError(f"Wyckoff event missing from its first-seen delta: {wrapper_id}")

    for position, trade in enumerate(payload["trades"]):
        trade = _require_fields(
            trade,
            {
                "id", "entry_index", "entry_time", "exit_index", "exit_time",
                "exit_price", "outcome", "exit_r", "bars_held", "result_confirmed_index",
            },
            scope=f"trades[{position}]",
        )
        entry_index = int(trade["entry_index"])
        if not 0 <= entry_index < len(candles):
            raise ValueError("trade entry outside visible candle range")
        entry_time = _timestamp(trade["entry_time"], field_name="trade.entry_time")
        if entry_time > _timestamp(candles[entry_index]["bar_close_time"], field_name="trade.entry_candle"):
            raise ValueError("trade entry is visible before its entry_time")
        result_index = trade.get("result_confirmed_index")
        if result_index is None:
            protected = ("exit_index", "exit_time", "exit_price", "exit_r", "bars_held")
            if trade.get("outcome") != "PENDING" or any(trade.get(key) is not None for key in protected):
                raise ValueError("trade exposes outcome or exit before result confirmation")
            continue
        result_index = int(result_index)
        exit_index = trade.get("exit_index")
        if not 0 <= result_index < len(candles) or result_index < entry_index:
            raise ValueError("trade result precedes entry or lies outside visible range")
        if exit_index is None or not entry_index <= int(exit_index) <= result_index:
            raise ValueError("trade exit precedes entry or follows result confirmation")
        exit_time = _timestamp(trade.get("exit_time"), field_name="trade.exit_time")
        result_time = _timestamp(candles[result_index]["bar_close_time"], field_name="trade.result_candle")
        if exit_time < entry_time or exit_time > result_time:
            raise ValueError("trade result is visible before exit availability")
        if trade.get("outcome") == "PENDING":
            raise ValueError("confirmed trade result cannot remain PENDING")

    manifest_fields = {
        "relative_source_path", "symbol", "timeframe", "timezone", "timestamp_semantics",
        "source_rows", "used_rows", "warmup_rows", "visible_rows", "source_first_time",
        "source_last_time", "used_first_time", "used_last_time", "warmup_first_time",
        "warmup_last_time", "visible_first_time", "visible_last_time", "last_asof_available",
        "slice_sha256", "volume_source",
    }
    for tf, raw_item in timeframe_manifest.items():
        item = _require_fields(raw_item, manifest_fields, scope=f"data_manifest.timeframes.{tf}")
        if item["symbol"] != payload["symbol"] or item["timeframe"] != tf:
            raise ValueError(f"manifest symbol/timeframe mismatch: {tf}")
        if item.get("timezone") != "UTC":
            raise ValueError(f"manifest timezone must be UTC: {tf}")
        if item.get("timestamp_semantics") not in {"OPEN_TIME", "CLOSE_TIME"}:
            raise ValueError(f"manifest timestamp semantics missing: {tf}")
        if item.get("volume_source") not in {"TICK_VOLUME_PROXY", "UNAVAILABLE", "REAL_EXCHANGE_VOLUME"}:
            raise ValueError(f"manifest volume source invalid: {tf}")
        relative_path = str(item["relative_source_path"])
        if not relative_path or _is_absolute_path(relative_path):
            raise ValueError(f"manifest source path must be relative: {tf}")
        source_rows = int(item["source_rows"])
        used_rows = int(item["used_rows"])
        warmup_rows = int(item["warmup_rows"])
        visible_rows = int(item["visible_rows"])
        if source_rows < used_rows or used_rows != warmup_rows + visible_rows or visible_rows <= 0:
            raise ValueError(f"manifest row counts are inconsistent: {tf}")
        for first_key, last_key in (
            ("source_first_time", "source_last_time"),
            ("used_first_time", "used_last_time"),
            ("visible_first_time", "visible_last_time"),
        ):
            if _timestamp(item[first_key], field_name=f"{tf}.{first_key}") > _timestamp(
                item[last_key], field_name=f"{tf}.{last_key}"
            ):
                raise ValueError(f"manifest time bounds are reversed: {tf}")
        if warmup_rows:
            if item["warmup_first_time"] is None or item["warmup_last_time"] is None:
                raise ValueError(f"manifest warmup bounds are missing: {tf}")
            if _timestamp(item["warmup_last_time"], field_name=f"{tf}.warmup_last_time") >= _timestamp(
                item["visible_first_time"], field_name=f"{tf}.visible_first_time"
            ):
                raise ValueError(f"manifest warmup overlaps visible window: {tf}")
        elif item["warmup_first_time"] is not None or item["warmup_last_time"] is not None:
            raise ValueError(f"manifest zero warmup has non-null bounds: {tf}")
        if _timestamp(item["last_asof_available"], field_name=f"{tf}.last_asof_available") != _timestamp(
            item["visible_last_time"], field_name=f"{tf}.visible_last_time"
        ):
            raise ValueError(f"manifest last asof mismatch: {tf}")
        if not isinstance(item["slice_sha256"], str) or len(item["slice_sha256"]) != 64:
            raise ValueError(f"manifest slice hash invalid: {tf}")

    metadata = _require_fields(
        payload["run_metadata"],
        {
            "run_id", "git_commit", "git_branch", "generator_worktree_clean_before_run",
            "python_version", "node_version", "config", "config_sha256",
            "artifact_content_sha256", "slice_sha256", "engine_lineage", "command",
        },
        scope="run_metadata",
    )
    for key in ("run_id", "git_commit", "git_branch", "python_version", "node_version", "command"):
        if not isinstance(metadata[key], str) or not metadata[key].strip():
            raise ValueError(f"run_metadata.{key} must be a non-empty string")
    if not isinstance(metadata["generator_worktree_clean_before_run"], bool):
        raise ValueError("generator_worktree_clean_before_run must be boolean")
    if metadata.get("config_sha256") != stable_sha256(metadata.get("config")):
        raise ValueError("config_sha256 does not match canonical config")
    expected_slices = {tf: item["slice_sha256"] for tf, item in timeframe_manifest.items()}
    if metadata.get("slice_sha256") != expected_slices:
        raise ValueError("run metadata slice hashes do not match data manifest")
    expected_run_id = stable_sha256(
        {
            "git_commit": metadata["git_commit"],
            "config_sha256": metadata["config_sha256"],
            "slice_sha256": expected_slices,
        }
    )[:24]
    if metadata["run_id"] != expected_run_id:
        raise ValueError("run_id does not match commit, config and data slices")

    # --- FASE 4 (SDD v1.2): Market State + Setup State validation ---
    # Validated before the content hash so malformed projections fail closed
    # regardless of hash consistency.
    market_state = payload.get("market_state")
    setups = payload.get("setups")
    if not isinstance(market_state, list) or len(market_state) != len(candles):
        raise ValueError("market_state must contain exactly one snapshot per visible candle")
    if not isinstance(setups, list) or len(setups) != len(candles):
        raise ValueError("setups must contain exactly one entry per visible candle")

    _MARKET_ENTITY_FIELDS = {
        "id", "type", "origin_tf", "role", "direction", "zone_high", "zone_low",
        "state", "parent_object", "related_objects", "candidate_bar",
        "confirmation_bar", "tradable_bar", "first_touch_bar", "invalidated_bar",
        "mitigation_level", "age_bars",
    }
    for position, (snapshot, point) in enumerate(zip(market_state, timeline, strict=True)):
        snapshot = _require_fields(
            snapshot,
            {"decision_time", "authority_tf", "entities", "terminal_entities", "delta"},
            scope=f"market_state[{position}]",
        )
        if _timestamp(snapshot["decision_time"], field_name="market_state.decision_time") != _timestamp(
            point["decision_time"], field_name="timeline.decision_time"
        ):
            raise ValueError(f"market_state decision_time mismatch at index {position}")
        if snapshot["authority_tf"] != payload["authority_tf"]:
            raise ValueError(f"market_state authority mismatch at index {position}")
        for entity in snapshot["entities"]:
            entity = _require_fields(entity, _MARKET_ENTITY_FIELDS, scope=f"market_state[{position}].entities")
            if entity["origin_tf"] not in timeframe_manifest:
                raise ValueError(f"market_state entity origin_tf not in manifest at index {position}")
            if entity["state"] not in {
                "CREATED", "ACTIVE", "PARTIALLY_MITIGATED", "MITIGATED",
                "INVALIDATED", "EXPIRED", "CONSUMED",
            }:
                raise ValueError(f"market_state entity invalid state at index {position}")
        delta = _require_fields(
            snapshot["delta"], {"created", "transitioned", "terminal"}, scope=f"market_state[{position}].delta"
        )
        if not isinstance(delta["created"], list) or not isinstance(delta["terminal"], list):
            raise ValueError(f"market_state delta lists invalid at index {position}")

    for position, (setup, point) in enumerate(zip(setups, timeline, strict=True)):
        setup = _require_fields(
            setup,
            {
                "id", "decision_time", "authority_tf", "direction", "cadena_htf_ltf",
                "estado", "active_tf", "condiciones_presentes", "condiciones_faltantes",
                "invalidacion", "evidence_refs", "policy",
            },
            scope=f"setups[{position}]",
        )
        if _timestamp(setup["decision_time"], field_name="setup.decision_time") != _timestamp(
            point["decision_time"], field_name="timeline.decision_time"
        ):
            raise ValueError(f"setup decision_time mismatch at index {position}")
        if setup["estado"] not in {
            "WAIT_D1", "D1_LOCKED", "WAIT_H4", "H4_LOCKED", "WAIT_H1",
            "WAIT_LTF", "SETUP_READY", "OUTCOME",
        }:
            raise ValueError(f"setup invalid estado at index {position}")
        if setup["policy"] != "CONTEXT_STATE_NOT_ENTRY_SIGNAL":
            raise ValueError(f"setup must disclose context-only policy at index {position}")

    expected_hash = artifact_content_sha256(payload)
    if metadata.get("artifact_content_sha256") != expected_hash:
        raise ValueError("artifact_content_sha256 does not match payload")

    scientific = _require_fields(
        payload["scientific_status"],
        {
            "classification", "scientific_gate", "edge_claimed", "wyckoff_contract",
            "pit_temporal_consistency", "h1_feasibility", "edge",
        },
        scope="scientific_status",
    )
    if scientific["edge_claimed"] is not False or scientific["edge"] != "NOT_PROVEN_BY_THIS_VIEWER":
        raise ValueError("viewer cannot claim economic edge")


def write_visual_backtest(payload: dict[str, Any], output: Path) -> None:
    """Write a validated artifact atomically."""

    validate_visual_backtest(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
