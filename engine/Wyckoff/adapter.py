"""Adaptador read-only de Wyckoff al snapshot ICT/MTF/LTF."""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .classifier import classify_alignment
from .effort_result import measure_effort_result
from .events import detect_events
from .phases import build_range_ref, classify_phase
from .types import WyckoffEvent, WyckoffPhase, WyckoffSnapshot, VolumeMode


def _prefix(frame: pd.DataFrame | None, decision_time: Any) -> pd.DataFrame:
    if frame is None or frame.empty or "time" not in frame.columns:
        return pd.DataFrame()
    tt = pd.to_datetime(decision_time, utc=True, errors="coerce")
    times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    if pd.isna(tt):
        return pd.DataFrame()
    return frame.loc[times <= tt].copy().reset_index(drop=True)


def _context_direction(context_state: Any) -> int:
    raw = context_state.to_dict() if hasattr(context_state, "to_dict") else context_state
    if not isinstance(raw, Mapping):
        return 0
    constraints = raw.get("constraints")
    if not isinstance(constraints, Mapping):
        return 0
    value = str(constraints.get("direction_hint", "UNKNOWN")).upper()
    return 1 if value == "BULLISH" else -1 if value == "BEARISH" else 0


def _layer_snapshot(frame: pd.DataFrame | None, *, tf: str, decision_time: Any) -> dict[str, Any]:
    prefix = _prefix(frame, decision_time)
    phase = classify_phase(prefix)
    events = detect_events(prefix, tf=tf)
    effort, volume_mode = measure_effort_result(prefix)
    range_ref = build_range_ref(prefix, tf=tf, decision_time=decision_time)
    asof = pd.to_datetime(prefix["time"], utc=True, errors="coerce").max() if not prefix.empty else None
    return {
        "tf": tf,
        "available": not prefix.empty,
        "authority_tf": tf,
        "phase": phase.value,
        "events": [event.to_dict() for event in events],
        "range_ref": range_ref,
        "effort_result": effort,
        "volume_mode": volume_mode.value,
        "evidence_refs": sorted({ref for event in events for ref in (event.source_ref, *event.evidence_refs)}),
        "asof_time": asof.isoformat() if not pd.isna(asof) else None,
    }, phase, events, effort, volume_mode


def build_wyckoff_snapshot(
    frames: Mapping[str, pd.DataFrame],
    decision_time: Any,
    *,
    context_state: Any = None,
    ict_direction: int | None = None,
    authority_tf: str = "D1",
    layers: tuple[str, ...] = ("D1", "H4", "H1", "M15"),
) -> WyckoffSnapshot:
    """Construye un snapshot Wyckoff closed-only y subordinado a ICT."""
    authority_tf = authority_tf.upper()
    layer_payloads: dict[str, dict[str, Any]] = {}
    layer_phases: dict[str, WyckoffPhase] = {}
    layer_events: dict[str, tuple[WyckoffEvent, ...]] = {}
    layer_effort: dict[str, dict[str, Any]] = {}
    layer_volume: dict[str, VolumeMode] = {}
    for tf in tuple(dict.fromkeys(tf.upper() for tf in layers)):
        payload, phase, events, effort, volume_mode = _layer_snapshot(frames.get(tf), tf=tf, decision_time=decision_time)
        layer_payloads[tf] = payload
        layer_phases[tf] = phase
        layer_events[tf] = events
        layer_effort[tf] = effort
        layer_volume[tf] = volume_mode

    primary_phase = layer_phases.get(authority_tf, WyckoffPhase.UNKNOWN)
    primary_events = layer_events.get(authority_tf, ())
    direction = _context_direction(context_state) if ict_direction is None else int(ict_direction)
    phase_state, alignment, conflict, explanation = classify_alignment(primary_phase, direction, primary_events)
    primary_payload = layer_payloads.get(authority_tf, {})
    primary_volume = layer_volume.get(authority_tf, VolumeMode.UNAVAILABLE)
    refs = sorted({ref for payload in layer_payloads.values() for ref in payload.get("evidence_refs", [])})
    effort = dict(layer_effort.get(authority_tf, {}))
    if primary_volume is VolumeMode.UNAVAILABLE and any(mode is not VolumeMode.UNAVAILABLE for mode in layer_volume.values()):
        primary_volume = VolumeMode.RELATIVE_ONLY
    return WyckoffSnapshot(
        phase=primary_phase,
        phase_state=phase_state,
        authority_tf=authority_tf,
        range_ref=primary_payload.get("range_ref", {}),
        events=primary_events,
        evidence_refs=tuple(refs),
        effort_result=effort,
        volume_mode=primary_volume,
        ict_alignment=alignment,
        conflict=conflict,
        explanation=explanation,
        layers=layer_payloads,
        decision_time=pd.to_datetime(decision_time, utc=True, errors="coerce").isoformat(),
    )


__all__ = ["build_wyckoff_snapshot"]
