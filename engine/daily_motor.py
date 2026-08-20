"""Composición segura del motor diario con observación LTF/EXEC.

Esta capa une el contexto top-down existente con el LTF del perfil diario.
Es un adaptador observacional: consume estructura, navegación, zonas y
Sequence canónicas cuando se le entregan, pero no crea una segunda estrategia,
FSM o detector de FVG/OB. Nunca emite órdenes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

from engine.market_object import MarketObject, ObjectState, ObjectType
from engine.plan import build_context_stack, ltf_structure_at, top_down_allows_trade


_TERMINAL_ZONE_STATES = {
    ObjectState.INVALIDATED.value,
    ObjectState.EXPIRED.value,
    ObjectState.CONSUMED.value,
}
_OBSERVABLE_ZONE_STATES = {
    ObjectState.ACTIVE.value,
    ObjectState.PARTIALLY_MITIGATED.value,
    ObjectState.MITIGATED.value,
}


@dataclass(frozen=True)
class DailyMotorConfig:
    """Perfil temporal explícito para la lectura diaria intradía."""

    profile_id: str = "DAILY_D1_H4_H1_M15_READING"
    htf: str = "D1"
    itf: str = "H4"
    context_tf: str = "H1"
    exec_tf: str = "M15"
    require_d1: bool = True
    require_itf: bool = True
    require_context: bool = True
    require_pd: bool = True

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id es obligatorio")
        tfs = (self.htf, self.itf, self.context_tf, self.exec_tf)
        if any(not tf or not tf.strip() for tf in tfs):
            raise ValueError("htf, itf, context_tf y exec_tf son obligatorios")
        if len(set(tfs)) != len(tfs):
            raise ValueError("El perfil LTF requiere roles temporales distintos")

    @property
    def tfs(self) -> tuple[str, ...]:
        return (self.htf, self.itf, self.context_tf, self.exec_tf)


def _safe_value(value: Any) -> Any:
    """Convierte valores pandas/numpy en una estructura JSON determinista."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return None if pd.isna(value) else value
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): _safe_value(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, set):
        return [_safe_value(v) for v in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _safe_value(value.item())
        except (ValueError, TypeError):
            pass
    return str(value)


def _timestamp(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    result = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(result) else result


def _timestamp_text(value: Any) -> str | None:
    result = _timestamp(value)
    return result.isoformat() if result is not None else None


def _asof_time(frames: Mapping[str, pd.DataFrame], tf: str) -> pd.Timestamp | None:
    df = frames.get(tf)
    if df is None or df.empty or "time" not in df.columns:
        return None
    times = pd.to_datetime(df["time"], utc=True, errors="coerce").dropna()
    return times.max() if not times.empty else None


def _closed_time(frame: pd.DataFrame | None, decision_time: Any) -> pd.Timestamp | None:
    if frame is None or frame.empty or "time" not in frame.columns:
        return None
    tt = _timestamp(decision_time)
    if tt is None:
        return None
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce").dropna()
    past = times[times <= tt]
    return past.max() if not past.empty else None


def _direction_value(value: Any) -> int:
    if isinstance(value, str):
        value = value.upper()
        return 1 if value in {"BULLISH", "LONG", "UP", "+1"} else -1 if value in {"BEARISH", "SHORT", "DOWN", "-1"} else 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return 1 if number > 0 else -1 if number < 0 else 0


def _direction_from_stack(stack: Mapping[str, Any], config: DailyMotorConfig) -> int:
    for tf in (config.htf, config.itf, config.context_tf):
        trend = str((stack.get(tf) or {}).get("trend", "RANGING")).upper()
        if trend == "BULLISH":
            return 1
        if trend == "BEARISH":
            return -1
    return 0


def _coerce_market_object(value: Any) -> MarketObject | None:
    if isinstance(value, MarketObject):
        return value
    if isinstance(value, Mapping):
        try:
            return MarketObject.from_dict(dict(value))
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _lineage_refs(obj: MarketObject) -> list[str]:
    refs: list[str] = []
    if obj.parent_object:
        refs.append(str(obj.parent_object))
    refs.extend(str(ref) for ref in obj.related_objects if ref)
    meta_refs = obj.meta.get("lineage_refs", []) if isinstance(obj.meta, Mapping) else []
    if isinstance(meta_refs, (str, bytes)):
        meta_refs = [meta_refs]
    if isinstance(meta_refs, Sequence):
        refs.extend(str(ref) for ref in meta_refs if ref)
    return sorted(set(refs))


def _zone_ref(obj: MarketObject) -> dict[str, Any]:
    return {
        "zone_id": str(obj.id),
        "zone_type": obj.type.value if isinstance(obj.type, ObjectType) else str(obj.type),
        "origin_tf": str(obj.origin_tf),
        "candidate_time": _timestamp_text(obj.candidate_time),
        "confirmation_time": _timestamp_text(obj.confirmation_time),
        "tradable_time": _timestamp_text(obj.tradable_time),
        "parent_refs": [str(obj.parent_object)] if obj.parent_object else [],
        "lineage_refs": _lineage_refs(obj),
        "state": obj.state.value if isinstance(obj.state, ObjectState) else str(obj.state),
        "direction": int(obj.direction),
    }


def _canonical_zone_state(
    canonical_zones: Mapping[str, Sequence[Any]] | None,
    exec_tf: str,
    direction: int,
    decision_time: pd.Timestamp,
) -> dict[str, Any]:
    """Consume canonical zones; arbitrary DataFrame flags never promote state."""
    if not canonical_zones or direction == 0:
        return {"zone_refs": [], "retest_state": "NO_ZONE", "retest_time": None, "lineage_refs": [], "zone_present": False, "retest_observed": False}

    raw_objects = canonical_zones.get(exec_tf, ())
    objects: list[MarketObject] = []
    for raw in raw_objects or ():
        obj = _coerce_market_object(raw)
        if obj is None or obj.origin_tf != exec_tf:
            continue
        if obj.state.value in _TERMINAL_ZONE_STATES or obj.state.value not in _OBSERVABLE_ZONE_STATES:
            continue
        if obj.direction not in (0, direction):
            continue
        tradable = _timestamp(obj.tradable_time or obj.confirmation_time)
        if tradable is None or tradable > decision_time:
            continue
        objects.append(obj)

    objects.sort(key=lambda obj: (str(_timestamp_text(obj.tradable_time or obj.confirmation_time)), str(obj.id)))
    refs = [_zone_ref(obj) for obj in objects]
    lineage = sorted({ref for obj in objects for ref in _lineage_refs(obj)})
    retests: list[tuple[pd.Timestamp, str]] = []
    for obj in objects:
        touch = _timestamp(obj.first_touch_time)
        tradable = _timestamp(obj.tradable_time or obj.confirmation_time)
        if touch is not None and tradable is not None and tradable <= touch <= decision_time and obj.touch_count >= 1:
            retests.append((touch, str(obj.id)))
    retests.sort(key=lambda item: (item[0], item[1]))
    retest_time = retests[-1][0].isoformat() if retests else None
    return {
        "zone_refs": refs,
        "retest_state": "OBSERVED" if retests else "WAITING",
        "retest_time": retest_time,
        "lineage_refs": lineage,
        "zone_present": bool(refs),
        "retest_observed": bool(retests),
    }


def _annotation_state(frame: pd.DataFrame | None, decision_time: pd.Timestamp) -> dict[str, Any]:
    """Expose legacy annotations for diagnostics, never as canonical truth."""
    if frame is None or frame.empty or "time" not in frame.columns:
        return {"legacy_zone_marker": False, "legacy_retest_marker": False}
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    past = frame.loc[times <= decision_time]
    if past.empty:
        return {"legacy_zone_marker": False, "legacy_retest_marker": False}
    row = past.iloc[-1]
    fvg_state = str(row.get("fvg_state", "NONE") or "NONE").upper()
    ob_dir = str(row.get("ob_direction", row.get("ob_dir", "-")) or "-").upper()
    zone_marker = fvg_state not in {"", "NONE", "NAN", "NULL"} or ob_dir not in {"", "-", "NONE", "NAN", "NULL"}
    retest_marker = any(
        token in " ".join(str(row.get(key, "")).upper() for key in ("retest_observed", "retest", "zone_touched"))
        for token in ("TOUCHED", "RETEST", "MITIGATED", "FILLED")
    )
    return {
        "legacy_zone_marker": bool(zone_marker),
        "legacy_retest_marker": bool(retest_marker),
        "legacy_fvg_state": fvg_state,
        "legacy_ob_direction": ob_dir,
    }


def _navigation_payload(navigation_snapshot: Any, config: DailyMotorConfig) -> dict[str, Any]:
    raw = navigation_snapshot.to_dict() if hasattr(navigation_snapshot, "to_dict") else navigation_snapshot
    raw = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "available": bool(raw),
        "state": raw.get("state"),
        "active_tf": raw.get("active_tf", config.context_tf),
        "parent_state": raw.get("parent_state"),
        "transition_event": raw.get("transition_event", raw.get("last_event")),
        "transition_time": raw.get("transition_time", raw.get("decision_time")),
        "invalidation_reason": raw.get("invalidation_reason"),
    }


def _sequence_payload(sequence_snapshot: Any) -> dict[str, Any]:
    raw = sequence_snapshot.to_dict() if hasattr(sequence_snapshot, "to_dict") else sequence_snapshot
    if isinstance(raw, Mapping):
        refs = raw.get("refs", raw.get("sequence_refs", [])) or []
        depth = raw.get("depth", raw.get("sequence_depth", 0)) or 0
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        refs, depth = raw, 0
    else:
        refs, depth = [], 0
    return {"available": bool(raw), "refs": sorted({str(ref) for ref in refs}), "depth": int(depth)}


def build_daily_motor_snapshot(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any = None,
    config: DailyMotorConfig | None = None,
    *,
    canonical_zones: Mapping[str, Sequence[Any]] | None = None,
    sequence_snapshot: Any = None,
    navigation_snapshot: Any = None,
    context_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a closed-only, canonical daily context + LTF snapshot.

    The optional inputs are read-only outputs from authoritative engines. This
    adapter does not run another detector or hierarchical FSM. Legacy
    DataFrame annotations remain visible under ``ltf.legacy_*`` but cannot
    promote a setup.
    """
    config = config or DailyMotorConfig()
    frames = frames or {}
    if decision_time is None:
        decision_time = _asof_time(frames, config.exec_tf)
    tt = _timestamp(decision_time)
    empty = {
        "policy": "OBSERVE_ONLY_NO_ORDER",
        "profile_id": config.profile_id,
        "htf_tf": config.htf,
        "itf_tf": config.itf,
        "context_tf": config.context_tf,
        "exec_tf": config.exec_tf,
        "entry_authorized": False,
        "status": "NO_LTF_DATA",
        "decision_time": _timestamp_text(tt),
        "asof_times_by_tf": {tf: _timestamp_text(_closed_time(frames.get(tf), tt)) if tt is not None else None for tf in config.tfs},
        "navigation": _navigation_payload(navigation_snapshot, config),
        "context": {"allowed": False, "reason": "invalid_decision_time", "stack": {}},
        "sequence": _sequence_payload(sequence_snapshot),
        "lineage_refs": [],
        "ltf": {"tf": config.exec_tf, "available": False, "zone_refs": [], "retest_state": "NO_ZONE"},
    }
    if tt is None:
        return _safe_value(empty)

    stack = build_context_stack(frames, tt, tfs=config.tfs)
    fallback_direction = _direction_from_stack(stack, config)
    supplied_context = dict(context_snapshot or {})
    direction = _direction_value(supplied_context.get("direction_hint", fallback_direction))
    gate_allowed, gate_reason = (
        top_down_allows_trade(
            stack,
            direction,
            require_d1=config.require_d1,
            require_h4=config.require_itf,
            require_h1=config.require_context,
            require_pd=config.require_pd,
            require_ltf=False,
        )
        if direction
        else (False, "no_htf_direction")
    )

    navigation = _navigation_payload(navigation_snapshot, config)
    nav_state = str(navigation.get("state") or "")
    if nav_state in {"WAIT_D1", "WAIT_H4", "WAIT_H1"}:
        gate_allowed, gate_reason = False, f"navigation_{nav_state}"

    structure = ltf_structure_at(frames, config.exec_tf, tt)
    ltf_available = bool(structure.get("available"))
    want = "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "RANGING"
    opposite = "BEARISH" if direction > 0 else "BULLISH"
    explicit_opposition = bool(
        direction
        and (
            structure.get("trend") == opposite
            or int(structure.get("bos_dir", 0) or 0) == -direction
        )
    )
    structure_confirmed = bool(
        direction
        and not explicit_opposition
        and (
            structure.get("trend") == want
            or int(structure.get("bos_dir", 0) or 0) == direction
            or int(structure.get("momentum", 0) or 0) == direction
        )
    )
    zone = _canonical_zone_state(canonical_zones, config.exec_tf, direction, tt)
    annotations = _annotation_state(frames.get(config.exec_tf), tt)

    if not ltf_available:
        status = "NO_LTF_DATA"
    elif not gate_allowed:
        status = "WAIT_CONTEXT"
    elif not structure_confirmed:
        status = "WAIT_LTF_CONFIRMATION"
    elif not zone["zone_present"]:
        status = "WAIT_LTF_ZONE"
    elif not zone["retest_observed"]:
        status = "WAIT_RETEST"
    else:
        status = "OBSERVABLE_SETUP"

    regime_stack = supplied_context.get(
        "regime_stack",
        {tf: (stack.get(tf) or {}).get("trend", "RANGING") for tf in config.tfs if tf in stack},
    )
    location = supplied_context.get(
        "location",
        {
            "htf": (stack.get(config.htf) or {}).get("pd_side", "UNKNOWN"),
            "itf": (stack.get(config.itf) or {}).get("pd_side", "UNKNOWN"),
        },
    )
    constraints = supplied_context.get(
        "constraints",
        {"top_down_allowed": bool(gate_allowed), "reason": gate_reason},
    )
    poi_refs = sorted({str(ref) for ref in supplied_context.get("poi_refs", []) or []})
    sequence = _sequence_payload(sequence_snapshot or supplied_context.get("sequence"))
    lineage_refs = sorted(set(zone["lineage_refs"]) | {str(ref) for ref in supplied_context.get("lineage_refs", []) or []})
    confirmation_state = "NO_DATA" if not ltf_available else "CONFIRMED" if structure_confirmed else "WAITING"
    ltf = {
        "tf": config.exec_tf,
        "available": ltf_available,
        "asof_time": structure.get("time"),
        "structure": {
            "trend": structure.get("trend", "RANGING"),
            "bos_dir": int(structure.get("bos_dir", 0) or 0),
            "momentum": int(structure.get("momentum", 0) or 0),
            "bars": int(structure.get("bars", 0) or 0),
        },
        "trend": structure.get("trend", "RANGING"),
        "bos_dir": int(structure.get("bos_dir", 0) or 0),
        "momentum": int(structure.get("momentum", 0) or 0),
        "structure_confirmed": structure_confirmed,
        "direction_compatible": bool(structure_confirmed),
        "confirmation_state": confirmation_state,
        **zone,
        **annotations,
    }
    snapshot = {
        "policy": "OBSERVE_ONLY_NO_ORDER",
        "profile_id": config.profile_id,
        "htf_tf": config.htf,
        "itf_tf": config.itf,
        "context_tf": config.context_tf,
        "exec_tf": config.exec_tf,
        "entry_authorized": False,
        "status": status,
        "decision_time": _timestamp_text(tt),
        "asof_times_by_tf": {tf: _timestamp_text(_closed_time(frames.get(tf), tt)) for tf in config.tfs},
        "navigation": navigation,
        "direction": direction,
        "direction_label": want,
        "context": {
            "state": supplied_context.get("state", "DERIVED_STACK"),
            "allowed": bool(gate_allowed),
            "reason": gate_reason,
            "direction_hint": direction,
            "location": location,
            "regime_stack": regime_stack,
            "constraints": constraints,
            "poi_refs": poi_refs,
            "stack": stack,
        },
        "sequence": sequence,
        "lineage_refs": lineage_refs,
        "ltf": ltf,
    }
    return _safe_value(snapshot)


__all__ = ["DailyMotorConfig", "build_daily_motor_snapshot"]
