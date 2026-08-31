"""Puente read-only entre las barras locales de MT5 y el estado operativo.

El módulo ensambla autoridades existentes; no define detectores, no crea una
segunda FSM y no ejecuta órdenes. Las ``frames`` recibidas deben haber sido
normalizadas y filtradas a velas cerradas por el loader operativo.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping
from pathlib import Path

import pandas as pd

from engine.Wyckoff import build_wyckoff_snapshot
from engine.daily_motor import build_daily_motor_snapshot
from engine.ltf_canonical_feed import build_canonical_objects, build_ltf_canonical_feed
from engine.market_state import MarketState as ObjectMarketState
from engine.mtf_navigation import MTFNavigator, NavigatorConfig


REQUIRED_TFS = ("D1", "H4", "H1", "M15", "M5", "M1")
OBJECT_TFS = ("D1", "H4", "H1", "M15")


def _utc(value: Any) -> pd.Timestamp | None:
    result = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(result) else result


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "value") and not hasattr(value, "isoformat"):
        return _safe(value.value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _frame_prefix(frame: pd.DataFrame | None, decision_time: Any) -> pd.DataFrame:
    if frame is None or frame.empty or "time" not in frame.columns:
        return pd.DataFrame()
    out = frame.copy()
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    out = out.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    out["__index__"] = out.index.astype(int)
    tt = _utc(decision_time)
    return out.loc[out["time"] <= tt].reset_index(drop=True) if tt is not None else pd.DataFrame()


def _source_artifacts(source_files: Mapping[str, str] | None) -> tuple[list[dict[str, Any]], list[str]]:
    artifacts: list[dict[str, Any]] = []
    errors: list[str] = []
    for tf, raw_path in sorted((source_files or {}).items()):
        path = Path(raw_path)
        if not path.is_file():
            errors.append(f"{tf}:missing_file")
            continue
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
                    size += len(chunk)
        except OSError as exc:
            errors.append(f"{tf}:hash_error:{type(exc).__name__}")
            continue
        artifacts.append({"tf": str(tf), "path": str(path), "bytes": size, "sha256": digest.hexdigest()})
    return artifacts, errors


def _advance_object_state(
    market_state: ObjectMarketState,
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
) -> None:
    """Avanza todos los objetos por reloj de TF, sin repetir una barra atrasada."""
    tt = _utc(decision_time)
    if tt is None:
        return
    for tf in OBJECT_TFS:
        frame = _frame_prefix(frames.get(tf), tt)
        if frame.empty:
            continue
        objects = [obj for obj in market_state.all_objects() if obj.authority_tf == tf]
        if not objects:
            continue
        for _, row in frame.iterrows():
            bar = row.to_dict()
            bar["tf"] = tf
            for obj in objects:
                tradable = _utc(obj.tradable_time)
                if tradable is None or row["time"] <= tradable:
                    continue
                # ``advance_bar`` delegates the transition to lifecycle and
                # records only official changes in the event-sourced history.
                market_state.advance_bar(obj.id, bar)


def build_object_market_state(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
    *,
    symbol: str = "",
    object_timeframes: tuple[str, ...] = OBJECT_TFS,
) -> ObjectMarketState:
    """Build an event-sourced object state from closed MT5 frames."""
    assembled = build_canonical_objects(
        frames,
        decision_time,
        timeframes=object_timeframes,
        symbol=symbol,
    )
    state = ObjectMarketState()
    for obj in assembled["objects"]:
        state.ingest(deepcopy(obj))
    _advance_object_state(state, frames, decision_time)
    return state


def build_mt5_operational_snapshot(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
    *,
    symbol: str = "EURUSD",
    required_tfs: tuple[str, ...] = REQUIRED_TFS,
    source_files: Mapping[str, str] | None = None,
    source_hashes: Mapping[str, str] | None = None,
    generator_commit: str | None = None,
) -> dict[str, Any]:
    """Compose the deterministic, closed-only MT5 operational snapshot."""
    tt = _utc(decision_time)
    normalized = {str(tf).upper(): _frame_prefix(frame, tt) for tf, frame in (frames or {}).items()}
    missing = [tf for tf in required_tfs if normalized.get(tf, pd.DataFrame()).empty]
    mtf_frames = {tf: normalized[tf] for tf in ("D1", "H4", "H1", "M15") if not normalized.get(tf, pd.DataFrame()).empty}
    source_artifacts, provenance_errors = _source_artifacts(source_files)
    computed_hashes = {item["tf"]: item["sha256"] for item in source_artifacts}
    supplied_hashes = {str(tf): str(value) for tf, value in (source_hashes or {}).items()}
    for tf, supplied in supplied_hashes.items():
        actual = computed_hashes.get(tf)
        if actual is not None and supplied != actual:
            provenance_errors.append(f"{tf}:hash_mismatch")
    resolved_hashes = {**computed_hashes, **supplied_hashes}
    if source_files:
        provenance_status = "BLOCKED" if provenance_errors else "PASS"
    else:
        provenance_status = "NOT_RUN"

    context_state = None
    if tt is not None and mtf_frames:
        context_state = MTFNavigator(
            mtf_frames,
            NavigatorConfig(precompute_sequences=False, sequence_tf="H1"),
        ).navigate(decision_time=tt, exec_tf="M15")

    canonical = build_ltf_canonical_feed(
        normalized,
        decision_time=tt,
        exec_tf="M15",
        sequence_tf="H1",
        symbol=symbol,
        include_sequence=True,
    ) if tt is not None else {"zones": {"M15": []}, "sequence": {"available": False, "refs": [], "depth": 0}}
    wyckoff = build_wyckoff_snapshot(
        mtf_frames,
        decision_time=tt,
        context_state=context_state,
        authority_tf="D1",
        layers=("D1", "H4", "H1", "M15"),
    ) if tt is not None else None
    object_state = build_object_market_state(normalized, tt, symbol=symbol) if tt is not None else ObjectMarketState()
    daily = build_daily_motor_snapshot(
        normalized,
        decision_time=tt,
        context_state=context_state,
        canonical_zones=canonical.get("zones"),
        sequence_snapshot=canonical.get("sequence"),
        wyckoff_snapshot=wyckoff,
    )
    status = "BLOCKED" if missing else "READY"
    if provenance_errors:
        status = "BLOCKED"
    return _safe({
        "schema_version": "MT5_OPERATIONAL_SNAPSHOT_V1",
        "source": "MT5_LOCAL",
        "symbol": symbol,
        "decision_time": tt,
        "missing_timeframes": missing,
        "asof_times_by_tf": {
            tf: (normalized[tf]["time"].max() if tf in normalized and not normalized[tf].empty else None)
            for tf in required_tfs
        },
        "source_files": dict(source_files or {}),
        "source_hashes": resolved_hashes,
        "source_artifacts": source_artifacts,
        "provenance": {
            "status": provenance_status,
            "provider": "MetaTrader5 local terminal",
            "dataset_id": f"{symbol}_MT5_LOCAL_PARQUET",
            "instrument": symbol,
            "timezone_policy": "UTC",
            "bar_boundary_semantics": "MT5 period start; closed-only cutoff applied upstream",
            "volume_semantics": "TICK_VOLUME_RELATIVE_IF_PRESENT",
            "open_interest_status": "UNAVAILABLE",
            "lookahead_policy": "closed_bar_prefix_only",
            "errors": provenance_errors,
        },
        "generator_commit": generator_commit,
        "context_state": context_state.to_dict() if context_state is not None else None,
        "object_market_state": object_state.to_dict(),
        "object_projection": [obj.to_dict() for obj in object_state.objects_existing_at(tt)] if tt is not None else [],
        "canonical_zones": {
            tf: [obj.to_dict() for obj in objects]
            for tf, objects in canonical.get("zones", {}).items()
        },
        "relations": canonical.get("relations", []),
        "sequence": canonical.get("sequence", {}),
        "wyckoff": wyckoff.to_dict() if wyckoff is not None else None,
        "daily_motor": daily,
        "status": status,
        "policy": "OBSERVE_ONLY_NO_ORDER",
        "entry_authorized": False,
    })


__all__ = ["REQUIRED_TFS", "OBJECT_TFS", "build_object_market_state", "build_mt5_operational_snapshot"]
