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
from engine.mechanical_signal_assessment import assess_mechanical_signal
from engine.ltf_canonical_feed import build_canonical_objects, build_ltf_canonical_feed
from engine.lineage import build_six_tf_lineage_spine
from engine.market_state import MarketState as ObjectMarketState
from engine.mtf_navigation import MTFNavigator, NavigatorConfig
from engine.plan import build_context_stack, ltf_confirms


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
        pending = sorted(
            (
                obj for obj in market_state.all_objects()
                if obj.authority_tf == tf and not bool(obj.meta.get("lineage_layer_anchor"))
            ),
            key=lambda obj: (str(obj.tradable_time), str(obj.id)),
        )
        if not pending:
            continue
        live: list[Any] = []
        next_object = 0
        for _, row in frame.iterrows():
            bar = row.to_dict()
            bar["tf"] = tf
            while next_object < len(pending):
                tradable = _utc(pending[next_object].tradable_time)
                if tradable is None or row["time"] <= tradable:
                    break
                live.append(pending[next_object])
                next_object += 1
            if not live:
                continue
            survivors: list[Any] = []
            for obj in live:
                tradable = _utc(obj.tradable_time)
                if tradable is None or row["time"] <= tradable:
                    survivors.append(obj)
                    continue
                # ``advance_bar`` delegates the transition to lifecycle and
                # records only official changes in the event-sourced history.
                market_state.advance_bar(obj.id, bar)
                # Terminal objects can never change again, so removing them
                # preserves the exact lifecycle result while avoiding a
                # quadratic scan over the remaining bars.
                if not obj.is_terminal:
                    survivors.append(obj)
            live = survivors


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
    event_objects = [deepcopy(obj) for obj in assembled["objects"]]
    for obj in event_objects:
        state.ingest(obj)

    # Espina temporal obligatoria D1→H4→H1→M15→M5→M1. Los anchors nacen
    # en el cierre real de cada TF y solo referencian, de forma observacional,
    # los eventos ya existentes de su propia capa. No reescriben el linaje de
    # nacimiento de FVG/OB ni introducen padres futuros en esos objetos.
    anchors, _layers = build_six_tf_lineage_spine(
        frames,
        decision_time,
        symbol=symbol,
    )
    event_ids_by_tf: dict[str, list[str]] = {}
    for obj in event_objects:
        event_ids_by_tf.setdefault(str(obj.origin_tf), []).append(str(obj.id))
    for anchor in anchors:
        anchor.related_objects = sorted(event_ids_by_tf.get(str(anchor.origin_tf), []))
        anchor.meta["lineage_refs"] = list(anchor.related_objects)
        state.ingest(anchor)

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
        # Object MarketState below is the single lifecycle projection for the
        # snapshot. Avoid replaying the same M15 objects a second time in the
        # LTF adapter; the public feed keeps its historical default=True.
        touch_lifecycle=False,
    ) if tt is not None else {"zones": {"M15": []}, "sequence": {"available": False, "refs": [], "depth": 0}}
    wyckoff = build_wyckoff_snapshot(
        mtf_frames,
        decision_time=tt,
        context_state=context_state,
        authority_tf="D1",
        layers=("D1", "H4", "H1", "M15"),
    ) if tt is not None else None
    object_state = build_object_market_state(normalized, tt, symbol=symbol) if tt is not None else ObjectMarketState()
    object_projection = object_state.objects_existing_at(tt) if tt is not None else []
    # Reuse the authoritative event-sourced M15 projection for the daily
    # consumer. Detection/relations remain canonical in ltf_canonical_feed;
    # lifecycle is owned only by Object MarketState in this assembler.
    if tt is not None:
        by_id = {obj.id: obj for obj in object_projection}
        canonical["zones"]["M15"] = [
            by_id.get(obj.id, obj) for obj in canonical.get("zones", {}).get("M15", [])
        ]
    daily = build_daily_motor_snapshot(
        normalized,
        decision_time=tt,
        context_state=context_state,
        canonical_zones=canonical.get("zones"),
        sequence_snapshot=canonical.get("sequence"),
        wyckoff_snapshot=wyckoff,
        lineage_objects=object_projection,
        require_valid_lineage=True,
        require_full_six_tf_lineage=True,
    )
    # Publish the same canonical micro confirmation used by the daily brief.
    # The viewer consumes this result; it must never infer it from candles.
    micro_stack = build_context_stack(normalized, tt, tfs=REQUIRED_TFS) if tt is not None else {}
    micro_structure = {tf: micro_stack[tf] for tf in ("M5", "M1") if tf in micro_stack}
    micro_confirmation = ltf_confirms(micro_structure, int(daily.get("direction", 0) or 0))
    status = "BLOCKED" if missing else "READY"
    if provenance_errors:
        status = "BLOCKED"
    lineage_gate = daily.get("lineage", {}) if isinstance(daily, Mapping) else {}
    if not bool(lineage_gate.get("valid", False)):
        status = "BLOCKED"
    snapshot = _safe({
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
        "object_projection": [obj.to_dict() for obj in object_projection],
        "canonical_zones": {
            tf: [obj.to_dict() for obj in objects]
            for tf, objects in canonical.get("zones", {}).items()
        },
        "relations": canonical.get("relations", []),
        "sequence": canonical.get("sequence", {}),
        "wyckoff": wyckoff.to_dict() if wyckoff is not None else None,
        "daily_motor": daily,
        "lineage_gate": lineage_gate,
        "micro_structure": micro_structure,
        "micro_confirmation": micro_confirmation,
        "status": status,
        "policy": "OBSERVE_ONLY_NO_ORDER",
        "entry_authorized": False,
        "can_trade": False,
    })
    # Diagnostic-only.  There is deliberately no fallback that turns context,
    # a zone, or a score into a mechanical BUY/SELL contract.
    snapshot["mechanical_signal_assessment"] = assess_mechanical_signal(snapshot)
    return snapshot


__all__ = ["REQUIRED_TFS", "OBJECT_TFS", "build_object_market_state", "build_mt5_operational_snapshot"]
