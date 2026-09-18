#!/usr/bin/env python3
"""Materializador causal de episodios temporales ICT + contexto Wyckoff.

Esta capa NO recalcula detectores, lifecycle, SetupBuilder ni labels. Consume
la autoridad existente:

    MarketState.projection_at(T)
        -> engine.episodes.build_episodes(...)
        -> Temporal Episode v1

El contrato temporal canónico viene de CONTRATO_EPISODES_FUNNEL_V1 §6:
available_at = tradable_time -> confirmation_time -> creation_time -> candidate_time.
Esto distingue el ancla inicial del patrón del instante realmente utilizable.

Wyckoff se conserva únicamente si un contexto causal lo provee. Si no existe,
se marca MISSING en vez de inventar una fase/evento.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from engine.episodes import CONTRACT_VERSION, available_time, build_episodes
from engine.market_object import MarketObject
from engine.market_state import MarketState

SCHEMA_VERSION = "TEMPORAL_EPISODE_V1"
TIMEFRAME_AUTHORITY = ("D1", "H4", "H1", "M15", "M5", "M1")


def _ser(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif hasattr(value, "to_pydatetime"):
        try:
            dt = value.to_pydatetime()
        except Exception:
            dt = None
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _le(a: Any, b: Any) -> bool:
    da, db = _as_datetime(a), _as_datetime(b)
    if da is not None and db is not None:
        return da <= db
    try:
        return a <= b
    except TypeError as exc:
        raise ValueError(f"TEMPORAL_INCOMPARABLE:{a!r}:{b!r}") from exc


def _seconds_between(a: Any, b: Any) -> float | None:
    da, db = _as_datetime(a), _as_datetime(b)
    if da is None or db is None:
        return None
    return float((db - da).total_seconds())


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, MarketObject):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "to_dict"):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def _lookup_by_decision(mapping: Mapping[Any, Any] | None, decision_time: Any) -> Any:
    if not mapping:
        return None
    if decision_time in mapping:
        return mapping[decision_time]
    key = _ser(decision_time)
    if key in mapping:
        return mapping[key]
    return None


def _lineage_depth(obj: MarketObject, selected: Mapping[str, MarketObject]) -> int:
    seen: set[str] = set()
    depth = 0
    parent = obj.parent_object
    while parent:
        if parent in seen:
            raise ValueError(f"TEMPORAL_LINEAGE_CYCLE:{obj.id}")
        seen.add(parent)
        parent_obj = selected.get(parent)
        if parent_obj is None:
            break
        depth += 1
        parent = parent_obj.parent_object
    return depth


def _collect_episode_objects(
    projection: Mapping[str, MarketObject],
    object_refs: Iterable[str],
) -> dict[str, MarketObject]:
    """Collect episode components plus parent ancestry already visible at T."""
    selected: dict[str, MarketObject] = {}
    pending = [str(ref) for ref in object_refs if ref and str(ref) != "NONE"]

    while pending:
        oid = pending.pop()
        if oid in selected:
            continue
        obj = projection.get(oid)
        if obj is None:
            raise ValueError(f"TEMPORAL_OBJECT_OUTSIDE_SNAPSHOT:{oid}")
        selected[oid] = obj
        if obj.parent_object:
            if obj.parent_object not in projection:
                raise ValueError(
                    f"TEMPORAL_LINEAGE_PARENT_OUTSIDE_SNAPSHOT:{oid}:{obj.parent_object}"
                )
            pending.append(obj.parent_object)
    return selected


def _validate_temporal_contract(obj: MarketObject, decision_time: Any) -> None:
    avail = available_time(obj)
    if avail is None:
        raise ValueError(f"TEMPORAL_EVENT_WITHOUT_AVAILABLE_AT:{obj.id}")
    if decision_time is not None and not _le(avail, decision_time):
        raise ValueError(f"TEMPORAL_FUTURE_DATA:{obj.id}")

    candidate = obj.candidate_time
    confirmed = obj.confirmation_time
    tradable = obj.tradable_time

    if candidate is not None and confirmed is not None and not _le(candidate, confirmed):
        raise ValueError(f"FAIL_TEMPORAL_CONTRACT:{obj.id}:candidate>confirmation")
    if confirmed is not None and tradable is not None and not _le(confirmed, tradable):
        raise ValueError(f"FAIL_TEMPORAL_CONTRACT:{obj.id}:confirmation>tradable")
    if tradable is not None and decision_time is not None and not _le(tradable, decision_time):
        raise ValueError(f"FAIL_TEMPORAL_CONTRACT:{obj.id}:tradable>decision")


def _explicit_price(obj: MarketObject) -> float | None:
    for key in ("price", "close", "entry"):
        value = (obj.meta or {}).get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _event_payload(obj: MarketObject, decision_time: Any) -> dict[str, Any]:
    _validate_temporal_contract(obj, decision_time)
    avail = available_time(obj)
    missing = []
    if obj.candidate_time is None:
        missing.append("candidate_time")
    if obj.confirmation_time is None:
        missing.append("confirmation_time")
    if obj.tradable_time is None:
        missing.append("tradable_time")
    if obj.parent_object is None:
        missing.append("parent_id")
    price = _explicit_price(obj)
    if price is None:
        missing.append("price")

    return {
        "object_id": obj.id,
        "event_type": obj.type.value,
        "role": obj.role.value,
        "event_time": _ser(obj.creation_time),
        "candidate_time": _ser(obj.candidate_time),
        "available_at": _ser(avail),
        "confirmed_at": _ser(obj.confirmation_time),
        "tradable_at": _ser(obj.tradable_time),
        "timeframe": obj.origin_tf,
        "authority_tf": obj.authority_tf,
        "direction": int(obj.direction),
        "state": obj.state.value,
        "parent_id": obj.parent_object,
        "lineage": {
            "parent_id": obj.parent_object,
            "related_ids": list(obj.related_objects or []),
        },
        "price": price,
        "geometry": {
            "zone_high": obj.zone_high,
            "zone_low": obj.zone_low,
            "mitigation_level": obj.mitigation_level,
        },
        "quality_score": obj.quality_score,
        "missing_mask": sorted(missing),
    }


def _sort_events(events: list[dict[str, Any]], objects: Mapping[str, MarketObject]) -> list[dict[str, Any]]:
    def key(event: dict[str, Any]):
        dt = _as_datetime(event["available_at"])
        if dt is not None:
            time_key: tuple[Any, ...] = (0, dt.timestamp())
        else:
            time_key = (1, str(event["available_at"]))
        depth = _lineage_depth(objects[event["object_id"]], objects)
        return (*time_key, depth, event["object_id"])

    return sorted(events, key=key)


def _attach_durations(events: list[dict[str, Any]], decision_time: Any) -> tuple[list[dict[str, Any]], float | None]:
    if not events:
        return events, None
    first = events[0]["available_at"]
    previous = None
    out = []
    for index, raw in enumerate(events):
        event = dict(raw)
        event["event_index"] = index
        event["delta_t_seconds"] = (
            None if previous is None else _seconds_between(previous, event["available_at"])
        )
        event["age_seconds"] = _seconds_between(first, event["available_at"])
        event["duration_seconds"] = event["age_seconds"]
        out.append(event)
        previous = event["available_at"]
    return out, _seconds_between(first, decision_time)


def _resolve_wyckoff(ctx: Any, explicit: Any) -> dict[str, Any]:
    if explicit is not None:
        value = _json_safe(explicit)
        if isinstance(value, dict):
            return {"status": "AVAILABLE", **value}
        return {"status": "AVAILABLE", "value": value}
    if isinstance(ctx, Mapping):
        for key in ("wyckoff_context", "wyckoff"):
            value = ctx.get(key)
            if value is not None:
                safe = _json_safe(value)
                if isinstance(safe, dict):
                    return {"status": "AVAILABLE", **safe}
                return {"status": "AVAILABLE", "value": safe}
    return {
        "status": "MISSING",
        "reason": "no causal Wyckoff context supplied for this decision_time",
    }


def _materialize_episode(
    ms: MarketState,
    episode: Mapping[str, Any],
    *,
    ctx: Any = None,
    wyckoff: Any = None,
) -> dict[str, Any]:
    decision_time = episode.get("decision_time")
    projection = ms.projection_at(decision_time)
    objects = _collect_episode_objects(projection, episode.get("object_refs", []))
    events = [_event_payload(obj, decision_time) for obj in objects.values()]
    events = _sort_events(events, objects)
    events, duration = _attach_durations(events, decision_time)

    present_tfs = {event["timeframe"] for event in events if event.get("timeframe")}
    tf_presence = {tf: tf in present_tfs for tf in TIMEFRAME_AUTHORITY}

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": episode.get("contract_version", CONTRACT_VERSION),
        "episode_id": episode.get("episode_id"),
        "canonical_setup_key": episode.get("canonical_setup_key"),
        "symbol": episode.get("symbol"),
        "decision_time": _ser(decision_time),
        "direction": int(episode.get("direction", 0)),
        "status": episode.get("status"),
        "reason": episode.get("reason", ""),
        "events": events,
        "episode_duration_seconds": duration,
        "timeframe_authority": list(TIMEFRAME_AUTHORITY),
        "timeframe_presence": tf_presence,
        "missing_timeframes": [tf for tf, present in tf_presence.items() if not present],
        "ict_context": _json_safe(ctx) if ctx is not None else {"status": "MISSING"},
        "wyckoff_context": _resolve_wyckoff(ctx, wyckoff),
        "component_tfs": _json_safe(episode.get("component_tfs", {})),
        "lineage": _json_safe(episode.get("lineage", {})),
        "provenance": {
            "source": "engine.episodes+MarketState.projection_at",
            "available_at_policy": "tradable_confirmation_creation_candidate",
            "labels_used": False,
            "outcomes_used": False,
        },
        "training_eligible": False,
        "can_trade": False,
        "entry_authorized": False,
    }


def temporalize_episode_artifact(
    ms: MarketState,
    episode_artifact: Mapping[str, Any],
    *,
    default_context: Any = None,
    context_by_decision: Mapping[Any, Any] | None = None,
    wyckoff_by_decision: Mapping[Any, Any] | None = None,
) -> dict[str, Any]:
    """Convert accepted engine Episodes to ordered temporal episodes."""
    episodes = []
    for episode in episode_artifact.get("episodes", []):
        if str(episode.get("status")) != "ACCEPTED":
            continue
        decision_time = episode.get("decision_time")
        ctx = _lookup_by_decision(context_by_decision, decision_time)
        if ctx is None:
            ctx = default_context
        wyckoff = _lookup_by_decision(wyckoff_by_decision, decision_time)
        episodes.append(_materialize_episode(ms, episode, ctx=ctx, wyckoff=wyckoff))

    result = {
        "schema_version": SCHEMA_VERSION,
        "source_contract_version": episode_artifact.get("contract_version", CONTRACT_VERSION),
        "episodes": episodes,
        "episodes_total": len(episodes),
        "events_total": sum(len(ep["events"]) for ep in episodes),
        "training_eligible": False,
        "can_trade": False,
        "entry_authorized": False,
    }
    result["checksum"] = _artifact_checksum(result)
    result["order_reversal"] = order_reversal_report(episodes)
    return result


def build_temporal_artifact(
    ms: MarketState,
    decisions_T: Iterable[Any],
    ctx: Any = None,
    *,
    context_by_decision: Mapping[Any, Any] | None = None,
    wyckoff_by_decision: Mapping[Any, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Public path: build canonical Episodes first, then temporalize them."""
    temporal_episodes: list[dict[str, Any]] = []
    source_checksums: list[str] = []

    for decision_time in decisions_T:
        decision_ctx = _lookup_by_decision(context_by_decision, decision_time)
        if decision_ctx is None:
            decision_ctx = ctx
        base = build_episodes(
            ms,
            [decision_time],
            decision_ctx,
            config=dict(config or {}),
        )
        source_checksums.append(str(base.get("checksum", "")))
        temporal = temporalize_episode_artifact(
            ms,
            base,
            default_context=decision_ctx,
            wyckoff_by_decision=wyckoff_by_decision,
        )
        temporal_episodes.extend(temporal["episodes"])

    result = {
        "schema_version": SCHEMA_VERSION,
        "source_contract_version": CONTRACT_VERSION,
        "source_episode_checksums": source_checksums,
        "episodes": temporal_episodes,
        "episodes_total": len(temporal_episodes),
        "events_total": sum(len(ep["events"]) for ep in temporal_episodes),
        "training_eligible": False,
        "can_trade": False,
        "entry_authorized": False,
    }
    result["checksum"] = _artifact_checksum(result)
    result["order_reversal"] = order_reversal_report(temporal_episodes)
    return result


def temporal_sequence_fingerprint(episode: Mapping[str, Any], *, reverse: bool = False) -> str:
    events = list(episode.get("events", []))
    if reverse:
        events = list(reversed(events))
    ordered = [
        {
            "object_id": event.get("object_id"),
            "event_type": event.get("event_type"),
            "timeframe": event.get("timeframe"),
            "available_at": event.get("available_at"),
            "confirmed_at": event.get("confirmed_at"),
            "tradable_at": event.get("tradable_at"),
            "parent_id": event.get("parent_id"),
        }
        for event in events
    ]
    payload = json.dumps(ordered, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def order_reversal_report(episodes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    tested = different = identical = 0
    insufficient = 0
    for episode in episodes:
        if len(episode.get("events", [])) < 2:
            insufficient += 1
            continue
        tested += 1
        original = temporal_sequence_fingerprint(episode)
        reversed_fp = temporal_sequence_fingerprint(episode, reverse=True)
        if original == reversed_fp:
            identical += 1
        else:
            different += 1
    sensitivity = (100.0 * different / tested) if tested else None
    return {
        "episodes_tested": tested,
        "different": different,
        "identical": identical,
        "insufficient_events": insufficient,
        "sensitivity_percentage": sensitivity,
        "verdict": "PASS" if tested > 0 and identical == 0 else "NOT_CERTIFIED",
    }


def _artifact_checksum(artifact: Mapping[str, Any]) -> str:
    core = {k: v for k, v in artifact.items() if k not in {"checksum", "created_at"}}
    payload = json.dumps(_json_safe(core), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_outputs(
    artifact: Mapping[str, Any],
    output_dir: Path | str,
    *,
    source_files: Iterable[Path | str] = (),
    git_commit: str = "",
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    jsonl_path = output / "episodes_pilot_v1.jsonl"
    manifest_path = output / "episodes_pilot_v1_manifest.json"

    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for episode in artifact.get("episodes", []):
            handle.write(json.dumps(_json_safe(episode), ensure_ascii=False, sort_keys=True) + "\n")

    sources = [Path(item) for item in source_files]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "materializer": "scripts/lab/experiments/mt_temporal_episode_materializer.py",
        "git_commit": git_commit,
        "source_files": [str(path) for path in sources],
        "source_hashes": {
            str(path): _sha256_file(path) for path in sources if path.is_file()
        },
        "episodes": int(artifact.get("episodes_total", 0)),
        "events": int(artifact.get("events_total", 0)),
        "timeframes": {
            tf: sum(
                1
                for episode in artifact.get("episodes", [])
                if episode.get("timeframe_presence", {}).get(tf)
            )
            for tf in TIMEFRAME_AUTHORITY
        },
        "available_at_policy": "tradable_confirmation_creation_candidate",
        "order_reversal": _json_safe(artifact.get("order_reversal", {})),
        "artifact_checksum": artifact.get("checksum"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_eligible": False,
        "can_trade": False,
        "entry_authorized": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return jsonl_path, manifest_path


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_time(text: str) -> datetime:
    value = text[:-1] + "+00:00" if text.endswith("Z") else text
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize causal Temporal Episode v1 from a saved MarketState")
    parser.add_argument("--market-state-json", required=True)
    parser.add_argument("--decision-time", action="append", required=True)
    parser.add_argument("--context-json")
    parser.add_argument("--wyckoff-json")
    parser.add_argument("--output-dir", default="reports/audits/experiments/temporal")
    parser.add_argument("--git-commit", default="")
    args = parser.parse_args(argv)

    state_path = Path(args.market_state_json)
    ms = MarketState.from_dict(_load_json(state_path))
    ctx = _load_json(Path(args.context_json)) if args.context_json else None
    wyckoff = _load_json(Path(args.wyckoff_json)) if args.wyckoff_json else None
    decisions = [_parse_time(value) for value in args.decision_time]

    wyckoff_map = None
    if wyckoff is not None:
        wyckoff_map = {_ser(t): wyckoff for t in decisions}

    artifact = build_temporal_artifact(
        ms,
        decisions,
        ctx,
        wyckoff_by_decision=wyckoff_map,
    )
    paths = write_outputs(
        artifact,
        args.output_dir,
        source_files=[state_path],
        git_commit=args.git_commit,
    )
    print(json.dumps({
        "status": "OK",
        "episodes_total": artifact["episodes_total"],
        "events_total": artifact["events_total"],
        "order_reversal": artifact["order_reversal"],
        "outputs": [str(path) for path in paths],
        "can_trade": False,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
