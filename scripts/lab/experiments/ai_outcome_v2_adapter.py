"""Engine->v2 causal adapter (T3 component, scaffold for G6/G8 tests).

Converts the canonical engine funnel artifact into v2 dataset rows with
causal per-event extraction at time <= decision_time. Dispatches to
OutcomeClassifier._features dispatch for V2_A parity test (Finding 2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from runtime.ai_learning.outcome_classifier import (
    V2_FEATURE_PROFILES,
    OUTCOME_CLASSES,
)


class AdapterError(ValueError):
    """Error de adapter del v2 AI Outcome."""


@dataclass(frozen=True)
class AdaptedEvent:
    episode_id: str
    decision_time: str
    direction: int
    status: str
    reason: str
    lineage_depth: int
    lineage_count: int
    features_at_t: dict
    can_trade: bool = False


@dataclass(frozen=True)
class AdaptedResult:
    events: tuple[AdaptedEvent, ...]
    audit: tuple[dict[str, Any], ...]
    diagnostics: tuple[str, ...]
    funnel_row_count: int
    adapted_row_count: int
    reason_counts: dict[str, int]


def _validate_tristate(features_at_t: Mapping[str, Any]) -> None:
    """Verify allow_long/allow_short tri-state is preserved (G6)."""
    perms = features_at_t.get("permissions", {})
    for key in ("allow_long", "allow_short"):
        val = perms.get(key)
        if val not in (True, False, None):
            raise AdapterError(f"permissions.{key} must be True/False/None, got {val!r}")


def _check_forbidden(name: str) -> bool:
    """Return True if feature name matches a forbidden token."""
    tokens = set(part.lower() for part in name.replace("=", "_").split("_"))
    forbidden = {
        "label", "outcome", "exit", "future", "pnl", "profit", "return",
        "entry", "stop", "target", "sl", "tp", "bars_held", "result",
    }
    return bool(tokens & forbidden)


def adapt_funnel_artifact(
    funnel: Mapping[str, Any] | str | Path,
    frames: Mapping[str, Any],
    *,
    context_provider=None,
    frames_sha256: dict | None = None,
) -> AdaptedResult:
    """
    Convert funnel artifact (engine/episodes) to v2 dataset rows.

    Args:
        funnel: dict (or path to JSON) with records[] + episodes[] + rejections[]
        frames: TF -> OHLC closed-bar data (pinned parquet)
        context_provider: optional callable (decision_time, tf) -> causal dict
        frames_sha256: per-file sha256 fingerprints (G0/G7/G11)

    Returns:
        AdaptedResult with all ACCEPTED/REJECTED/SUPERSEDED candidates preserved
    """
    if isinstance(funnel, (str, Path)):
        path = Path(funnel)
        if not path.is_file():
            raise AdapterError(f"funnel artifact not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AdapterError(f"cannot read funnel artifact: {exc}") from exc
    elif isinstance(funnel, Mapping):
        raw = dict(funnel)
    else:
        raise AdapterError("funnel must be dict or path to JSON")

    records = raw.get("records", [])
    episodes = raw.get("episodes", [])
    rejections = raw.get("rejections", [])

    # Index episodes by id for quick lookup
    ep_by_id = {ep.get("canonical_setup_key"): ep for ep in episodes if isinstance(ep, Mapping)}

    events: list[AdaptedEvent] = []
    audit: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    reason_counts: dict[str, int] = {}
    funnel_row_count = len(records)

    for idx, record in enumerate(records):
        if not isinstance(record, Mapping):
            continue

        decision_time = record.get("decision_time") or record.get("time", "")
        direction = record.get("direction", 0)
        status = record.get("status", "UNKNOWN")
        reason = record.get("reason", "")
        episode_id = record.get("episode_id") or record.get("canonical_setup_key", f"AUDIT_{idx}")
        lineage_depth = record.get("lineage_depth", 0)
        lineage_count = record.get("lineage_count", 0)
        can_trade = record.get("can_trade", False)

        # Causal extraction at decision_time (time <= event_time)
        if context_provider:
            ctx = context_provider(decision_time)
        else:
            ctx = _default_causal_context(record, frames, decision_time)

        features_at_t = ctx["features_at_t"]
        _validate_tristate(features_at_t)

        # Check forbidden fields
        for key in _flatten_keys(features_at_t):
            if _check_forbidden(key):
                raise AdapterError(f"forbidden feature field: {key}")

        event = AdaptedEvent(
            episode_id=str(episode_id),
            decision_time=str(decision_time),
            direction=int(direction),
            status=str(status),
            reason=str(reason),
            lineage_depth=int(lineage_depth),
            lineage_count=int(lineage_count),
            features_at_t=features_at_t,
            can_trade=can_trade,
        )
        events.append(event)

        if reason:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        # Track in audit if rejected
        if status in ("REJECTED", "SUPERSEDED") and reason:
            audit.append({
                "episode_id": str(episode_id),
                "status": status,
                "reason": reason,
                "features_at_t": features_at_t,
            })

    diagnostics.append("validated funnel rows")
    diagnostics.append("tri-state guard verified")
    diagnostics.append("forbidden field scan passed")
    if frames_sha256:
        diagnostics.append(f"frames_sha256: {len(frames_sha256)} files")

    return AdaptedResult(
        events=tuple(events),
        audit=tuple(audit),
        diagnostics=tuple(diagnostics),
        funnel_row_count=funnel_row_count,
        adapted_row_count=len(events),
        reason_counts=reason_counts,
    )


def _flatten_keys(payload: Any, prefix: str = "") -> list[str]:
    """Recursively collect all keys in a nested dict/list."""
    keys: list[str] = []
    if isinstance(payload, Mapping):
        for k, v in payload.items():
            keys.append(str(k))
            keys.extend(_flatten_keys(v, prefix=f"{prefix}.{k}"))
    elif isinstance(payload, (list, tuple)):
        for i, v in enumerate(payload):
            keys.extend(_flatten_keys(v, prefix=f"{prefix}[{i}]"))
    return keys


def _load_pinned_frames(data_dir: str | Path = "data/raw/EURUSD") -> tuple[dict[str, Any], dict[str, str]]:
    """Load pinned parquet frames + compute sha256 (G0/G7/G11)."""
    import hashlib
    from engine.data_feed import load_frames
    from pathlib import Path
    data_dir = Path(data_dir)
    frames = load_frames("EURUSD", ("M1", "M5", "M15", "H1", "H4", "D1"), data_dir=data_dir)
    sha = {}
    for tf in ("M1", "M5", "M15", "H1", "H4", "D1"):
        path = data_dir / f"EURUSD_{tf}.parquet"
        if path.exists():
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            sha[tf] = h
    return frames, sha


def _prefix_frame(frame, decision_time: str) -> Any:
    """Compute PREFIX: frame[time <= decision_time] (forward-PIT, G4/G5/G8)."""
    # Delegate to engine._frame_prefix if available; else simple filter
    try:
        from engine.mt5_operational_snapshot import _frame_prefix
        return _frame_prefix(frame, decision_time)
    except Exception as exc:
        raise AdapterError(f"PREFIX causal failure: cannot build prefix for decision_time={decision_time}: {exc}") from exc


def _default_causal_context(
    record: Mapping[str, Any],
    frames: Mapping[str, Any],
    decision_time: str,
) -> dict[str, Any]:
    """
    Default causal extraction for testing without live navigator.

    Strict mode: requires the record to already carry an engine_v2
    `features_at_t` payload. If the record is empty or has a different
    schema_group, this fails closed. No placeholder constants are used:
    absent causal context is reported as an explicit rejection, never
    silently substituted with zeros/UNKNOWN.
    """
    features = record.get("features_at_t", {})
    if not isinstance(features, Mapping) or not features:
        raise AdapterError(
            f"causal context unavailable: record lacks features_at_t at decision_time={decision_time}; "
            f"fallback to placeholder values is forbidden (R3 / C-3.4 / C-3.5)"
        )

    if features.get("schema_group") != "engine_v2":
        raise AdapterError(
            f"causal context unavailable: schema_group must be 'engine_v2', got {features.get('schema_group')!r}; "
            f"record is not from the canonical engine_v2 snapshot"
        )

    return {"features_at_t": dict(features)}
