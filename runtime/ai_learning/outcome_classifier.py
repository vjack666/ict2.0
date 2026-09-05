"""Clasificador supervisado de outcomes para la primera IA de ICT.

La implementación es un baseline multinomial determinista (softmax) que
consume el contrato ``TrainingPipeline`` y no conoce órdenes ni PnL. Solo puede
entrenar cuando el llamador presenta una autorización científica explícita:
``status=PASS`` y ``verdict=TRAINING_ELIGIBLE``. La predicción siempre sale en
Shadow Mode y pasa por la política de abstención INF-7.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .abstention import evaluate_abstention
from .training_pipeline import TrainingPipeline


OUTCOME_CLASSIFIER_SCHEMA_VERSION = "1.0"
OUTCOME_CLASSES = ("continuation", "reversal", "failure")
FEATURE_NAMES = (
    "direction",
    "sequence_depth",
    "context_bucket=ALIGNED",
    "context_bucket=NEUTRAL",
    "context_bucket=AGAINST",
    "h1_alignment=ALIGNED",
    "h1_alignment=NEUTRAL",
    "h1_alignment=AGAINST",
    "d1_bias=BULLISH",
    "d1_bias=BEARISH",
    "d1_bias=UNKNOWN",
    "d1_bias=MIXED",
    "h4_location=DISCOUNT",
    "h4_location=PREMIUM",
    "h4_location=EQUILIBRIUM",
    "h4_location=MID",
    "h4_location=UNKNOWN",
    "sequence_has=LIQUIDITY_POOL",
    "sequence_has=SWEEP",
    "sequence_has=DISPLACEMENT",
    "sequence_has=STRUCTURE",
    "sequence_has=OB",
    "sequence_has=FVG",
    "sequence_has=CONFLUENCE",
)
INTRADAY_PHASES = (
    "ACCUMULATION", "MARKUP", "DISTRIBUTION", "MARKDOWN",
    "RANGE_UNCLASSIFIED", "TRANSITION", "UNKNOWN",
)
INTRADAY_EVENTS = (
    "SPRING", "UPTHRUST", "UTAD", "SOS", "SOW", "LPS", "LPSY",
    "TEST", "FAILED_TEST", "RANGE_BREAK", "EFFORT_RESULT_DIVERGENCE",
)
# Same deterministic softmax trainer, with an explicit causal feature profile
# for the Wyckoff H1 -> M15 research line.  The original ICT profile remains
# byte-for-byte compatible for existing artifacts.
INTRADAY_BASE_FEATURE_NAMES = ("direction", "sequence_depth")
INTRADAY_ICT_FEATURE_NAMES = (
    "ict_m15_bos_bullish", "ict_m15_bos_bearish",
    "ict_m15_choch_bullish", "ict_m15_choch_bearish",
    "ict_m15_displacement_bullish", "ict_m15_displacement_bearish",
    "ict_m15_fvg_bullish", "ict_m15_fvg_bearish",
    "ict_m15_sweep_up", "ict_m15_sweep_down",
)
INTRADAY_WYCKOFF_FEATURE_NAMES = (
    *(f"wyckoff_h1_phase={value}" for value in INTRADAY_PHASES),
    *(f"wyckoff_m15_phase={value}" for value in INTRADAY_PHASES),
    *(f"wyckoff_h1_event={value}" for value in INTRADAY_EVENTS),
    *(f"wyckoff_m15_event={value}" for value in INTRADAY_EVENTS),
)
INTRADAY_ICT_ONLY_FEATURE_NAMES = INTRADAY_BASE_FEATURE_NAMES + INTRADAY_ICT_FEATURE_NAMES
INTRADAY_WYCKOFF_ONLY_FEATURE_NAMES = INTRADAY_BASE_FEATURE_NAMES + INTRADAY_WYCKOFF_FEATURE_NAMES
INTRADAY_FEATURE_NAMES = (
    INTRADAY_BASE_FEATURE_NAMES
    + INTRADAY_ICT_FEATURE_NAMES
    + INTRADAY_WYCKOFF_FEATURE_NAMES
)
INTRADAY_FEATURE_PROFILES = {
    "ICT_ONLY": INTRADAY_ICT_ONLY_FEATURE_NAMES,
    "WYCKOFF_ONLY": INTRADAY_WYCKOFF_ONLY_FEATURE_NAMES,
    "WYCKOFF_ICT_COMBINED": INTRADAY_FEATURE_NAMES,
}

# === v2 registry (ai-outcome-v2): add sibling registry, do not mutate v1 tuples ===
V2_CONTEXT_LAYERS = ("D1", "H4", "H1")
V2_CONTEXT_STATUSES = ("OK", "INCOMPLETE", "BLOCKED")
V2_DIRECTION_HINTS = ("BULLISH", "BEARISH", "MIXED", "UNKNOWN")
V2_REGIME_LABELS = (
    "TREND_BULL", "TREND_BEAR", "RANGE", "EXPANSION",
    "RETRACEMENT", "COMPRESSION", "UNKNOWN",
)
V2_LIFECYCLE_STAGES = (
    "SETUP", "ELIGIBLE", "BLOCKED", "SUPERSEDED", "OUT_OF_CONTEXT",
)
V2_M1_RETEST_STATES = ("RETEST", "NO_RETEST", "UNKNOWN")
# REASONS list (from engine/episodes.py REASONS, plus ACCEPTED marker)
V2_REASONS = (
    "MISSING_SNAPSHOT", "MISSING_IDENTITY", "MISSING_REQUIRED_COMPONENT",
    "OUT_OF_CONTEXT", "SETUP_BLOCKED", "SETUP_SUPERSEDED", "INVALID_AUTHORITY",
    "TEMPORAL_ORDER", "FUTURE_DATA", "MISSING_LINEAGE", "INVALID_LINEAGE",
    "DUPLICATE_EVENT", "DUPLICATE_SETUP", "CONFIG_MISMATCH",
)

V2_CARDINAL = (
    "direction", "sequence_depth",
    "zone_poi_count", "zone_bsl_count", "zone_ssl_count",
    "zone_proximity", "lineage_depth", "lineage_count",
)

# V2_A == baseline replica (must equal INTRADAY_FEATURE_NAMES exactly)
V2_A = INTRADAY_FEATURE_NAMES

# B = A + context_state + direction_hint + regime_stack
V2_B_ADD = (
    *(f"context_{layer}={status}" for layer in V2_CONTEXT_LAYERS for status in V2_CONTEXT_STATUSES),
    *(f"direction_hint={value}" for value in V2_DIRECTION_HINTS),
    *(f"regime_{layer}={regime}" for layer in V2_CONTEXT_LAYERS for regime in V2_REGIME_LABELS),
)
V2_B = V2_A + V2_B_ADD

# C = B + BOS HTF layer bools + lifecycle one-hot
V2_C_ADD = (
    "bos_d1_bullish", "bos_d1_bearish",
    "bos_h4_bullish", "bos_h4_bearish",
    "bos_h1_bullish", "bos_h1_bearish",
    *(f"lifecycle={stage}" for stage in V2_LIFECYCLE_STAGES),
)
V2_C = V2_B + V2_C_ADD

# D = C + M5 micro (2-state bools)
V2_D_ADD = (
    "m5_bos_bullish", "m5_bos_bearish",
    "m5_displacement_bullish", "m5_displacement_bearish",
    "m5_fvg_bullish", "m5_fvg_bearish",
)
V2_D = V2_C + V2_D_ADD

# E = D + M1 micro
V2_E_ADD = (
    "m1_trigger_bullish", "m1_trigger_bearish",
    *(f"m1_retest={state}" for state in V2_M1_RETEST_STATES),
)
V2_E = V2_D + V2_E_ADD

# F = E + permissions tri-state + reason_codes one-hot
V2_F_ADD = (
    "allow_long_allow", "allow_long_block", "allow_long_no_opinion",
    "allow_short_allow", "allow_short_block", "allow_short_no_opinion",
    *(f"reason_{code}" for code in V2_REASONS),
    "reason_ACCEPTED",
)
V2_F = V2_E + V2_F_ADD

V2_FEATURE_PROFILES = {
    "V2_A": V2_A, "V2_B": V2_B, "V2_C": V2_C,
    "V2_D": V2_D, "V2_E": V2_E, "V2_F": V2_F,
}
_V2_FEATURE_TUPLES = tuple(V2_FEATURE_PROFILES.values())
_CATEGORIES = {
    "context_bucket": ("ALIGNED", "NEUTRAL", "AGAINST"),
    "h1_alignment": ("ALIGNED", "NEUTRAL", "AGAINST"),
    "d1_bias": ("BULLISH", "BEARISH", "UNKNOWN", "MIXED"),
    "h4_location": ("DISCOUNT", "PREMIUM", "EQUILIBRIUM", "MID", "UNKNOWN"),
}
_MIN_ROWS = {"train": 30, "validation": 10, "test": 10}


class OutcomeClassifierError(ValueError):
    """Error de contrato, datos o entrenamiento del clasificador."""


class TrainingAuthorizationError(OutcomeClassifierError):
    """La evidencia científica no autoriza entrenamiento real."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise OutcomeClassifierError(f"{field} debe ser numérico")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise OutcomeClassifierError(f"{field} debe ser numérico") from exc
    if not math.isfinite(result):
        raise OutcomeClassifierError(f"{field} debe ser finito")
    return result


def _intraday_features(
    row: Mapping[str, Any],
    feature_names: Sequence[str] = INTRADAY_FEATURE_NAMES,
) -> np.ndarray:
    raw = row.get("features_at_t", row)
    if not isinstance(raw, Mapping):
        raise OutcomeClassifierError("features_at_t debe ser un objeto")
    context = raw.get("context_inputs", {})
    intraday = raw.get("intraday", {})
    if not isinstance(context, Mapping) or not isinstance(intraday, Mapping):
        raise OutcomeClassifierError("features_at_t intradía incompleto")
    ict = intraday.get("ict_m15", {})
    wyckoff = intraday.get("wyckoff", {})
    if not isinstance(ict, Mapping) or not isinstance(wyckoff, Mapping):
        raise OutcomeClassifierError("features_at_t intradía inválido")

    def flag(name: str) -> float:
        return 1.0 if bool(ict.get(name, False)) else 0.0

    def layer(name: str) -> Mapping[str, Any]:
        value = wyckoff.get(name, {})
        return value if isinstance(value, Mapping) else {}

    def event_set(layer_payload: Mapping[str, Any]) -> set[str]:
        events = layer_payload.get("events", ())
        if not isinstance(events, (list, tuple)):
            return set()
        result: set[str] = set()
        for event in events:
            if isinstance(event, Mapping):
                value = event.get("event_type", event.get("type", ""))
            else:
                value = event
            result.add(str(value).upper())
        return result

    h1 = layer("H1")
    m15 = layer("M15")
    h1_phase = str(h1.get("phase", "UNKNOWN")).upper()
    m15_phase = str(m15.get("phase", "UNKNOWN")).upper()
    h1_events = event_set(h1)
    m15_events = event_set(m15)
    values_by_name: dict[str, float] = {
        "direction": _finite(
            context.get("sequence_direction", row.get("direction", 0)), "direction"
        ),
        "sequence_depth": _finite(row.get("sequence_depth", 0), "sequence_depth"),
    }
    values_by_name.update({
        f"ict_m15_{name}": flag(name)
        for name in (
            "bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish",
            "displacement_bullish", "displacement_bearish", "fvg_bullish",
            "fvg_bearish", "sweep_up", "sweep_down",
        )
    })
    values_by_name.update({
        f"wyckoff_h1_phase={value}": 1.0 if h1_phase == value else 0.0
        for value in INTRADAY_PHASES
    })
    values_by_name.update({
        f"wyckoff_m15_phase={value}": 1.0 if m15_phase == value else 0.0
        for value in INTRADAY_PHASES
    })
    values_by_name.update({
        f"wyckoff_h1_event={value}": 1.0 if value in h1_events else 0.0
        for value in INTRADAY_EVENTS
    })
    values_by_name.update({
        f"wyckoff_m15_event={value}": 1.0 if value in m15_events else 0.0
        for value in INTRADAY_EVENTS
    })
    unknown = sorted(set(feature_names).difference(values_by_name))
    if unknown:
        raise OutcomeClassifierError(f"perfil intradía contiene features desconocidas: {unknown}")
    result = np.asarray([values_by_name[name] for name in feature_names], dtype=float)
    if len(result) != len(feature_names) or not np.isfinite(result).all():
        raise OutcomeClassifierError("vector de features intradía inválido")
    return result


# === v2 feature vector builder (ai-outcome-v2, Finding 2 + Finding 4) ===
def _v2_features(
    row: Mapping[str, Any],
    feature_names: Sequence[str] = V2_FEATURE_PROFILES["V2_A"],
) -> np.ndarray:
    """
    Build feature vector from v2 payload (schema_group=engine_v2).
    Uses flat-column mapping per design §5.4 with explicit is True/is False/is None.
    Supports V2_A (baseline replica), V2_B through V2_F.

    Tri-state permissions (allow_long/allow_short) are encoded as EXACTLY three
    one-hot columns per feature: _allow, _block, _no_opinion.
    """
    raw = row.get("features_at_t", row)
    if not isinstance(raw, Mapping):
        raise OutcomeClassifierError("features_at_t debe ser un objeto")

    # V2_A path: read from intraday_v2 block (Finding 2)
    if tuple(feature_names) == V2_A:
        return _v2_features_A(row, feature_names)

    # B-F path: read from v2 native blocks
    return _v2_features_B_to_F(row, feature_names)


def _v2_features_A(
    row: Mapping[str, Any],
    feature_names: Sequence[str],
) -> np.ndarray:
    """V2_A: route through intraday_v2 block to reproduce baseline 48-feature vector."""
    raw = row.get("features_at_t", row)
    intraday_v2 = raw.get("intraday_v2", {})

    # Pull direction/sequence_depth from top-level (v2-native, identical semantics)
    direction = _finite(raw.get("direction", 0), "direction")
    seq_depth = _finite(raw.get("sequence_depth", 0), "sequence_depth")

    # ict_m15 booleans
    ict = intraday_v2.get("ict_m15", {})

    def flag(name: str) -> float:
        v = ict.get(name)
        return 1.0 if v is True else 0.0

    # Wyckoff H1/M15
    wyckoff = intraday_v2.get("wyckoff", {})

    def layer(name: str) -> Mapping[str, Any]:
        return wyckoff.get(name, {}) if isinstance(wyckoff, Mapping) else {}

    def event_set(layer_payload: Mapping[str, Any]) -> set[str]:
        events = layer_payload.get("events", ())
        if not isinstance(events, (list, tuple)):
            return set()
        result: set[str] = set()
        for event in events:
            if isinstance(event, Mapping):
                value = event.get("event_type", event.get("type", ""))
            else:
                value = event
            result.add(str(value).upper())
        return result

    h1 = layer("H1")
    m15 = layer("M15")
    h1_phase = str(h1.get("phase", "UNKNOWN")).upper()
    m15_phase = str(m15.get("phase", "UNKNOWN")).upper()
    h1_events = event_set(h1)
    m15_events = event_set(m15)

    values_by_name: dict[str, float] = {
        "direction": direction,
        "sequence_depth": seq_depth,
    }
    values_by_name.update({
        f"ict_m15_{name}": flag(name)
        for name in (
            "bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish",
            "displacement_bullish", "displacement_bearish", "fvg_bullish",
            "fvg_bearish", "sweep_up", "sweep_down",
        )
    })
    values_by_name.update({
        f"wyckoff_h1_phase={value}": 1.0 if h1_phase == value else 0.0
        for value in INTRADAY_PHASES
    })
    values_by_name.update({
        f"wyckoff_m15_phase={value}": 1.0 if m15_phase == value else 0.0
        for value in INTRADAY_PHASES
    })
    values_by_name.update({
        f"wyckoff_h1_event={value}": 1.0 if value in h1_events else 0.0
        for value in INTRADAY_EVENTS
    })
    values_by_name.update({
        f"wyckoff_m15_event={value}": 1.0 if value in m15_events else 0.0
        for value in INTRADAY_EVENTS
    })

    unknown = sorted(set(feature_names).difference(values_by_name))
    if unknown:
        raise OutcomeClassifierError(f"perfil v2-A contiene features desconocidas: {unknown}")
    result = np.asarray([values_by_name[name] for name in feature_names], dtype=float)
    if len(result) != len(feature_names) or not np.isfinite(result).all():
        raise OutcomeClassifierError("vector v2-A de features inválido")
    return result


def _v2_features_B_to_F(
    row: Mapping[str, Any],
    feature_names: Sequence[str],
) -> np.ndarray:
    """
    V2_B through V2_F: flat-column mapping from v2 payload per design §5.4.
    Explicit is True / is False / is None — never truthiness.
    """
    raw = row.get("features_at_t", row)

    def _get(payload: Mapping, *keys: str, default=None):
        """Navigate nested dict safely."""
        cur = payload
        for k in keys:
            if not isinstance(cur, Mapping):
                return default
            cur = cur.get(k, default)
        return cur

    values: dict[str, float] = {}

    # --- Cardinal (numeric passthrough) ---
    values["direction"] = _finite(raw.get("direction", 0), "direction")
    values["sequence_depth"] = _finite(raw.get("sequence_depth", 0), "sequence_depth")
    zones = _get(raw, "zones") or {}
    values["zone_poi_count"] = _finite(_get(zones, "poi", "count") or 0, "zone_poi_count")
    values["zone_bsl_count"] = _finite(_get(zones, "bsl", "count") or 0, "zone_bsl_count")
    values["zone_ssl_count"] = _finite(_get(zones, "ssl", "count") or 0, "zone_ssl_count")
    values["zone_proximity"] = _finite(_get(zones, "proximity") or 0.0, "zone_proximity")
    lineage = _get(raw, "lineage") or {}
    values["lineage_depth"] = _finite(_get(lineage, "depth") or 0, "lineage_depth")
    values["lineage_count"] = _finite(_get(lineage, "count") or 0, "lineage_count")

    # --- context_state: layer_status (B+) ---
    cs = _get(raw, "context_state") or {}
    for layer in ("D1", "H4", "H1"):
        status = str(_get(cs, "layer_status", layer) or "UNKNOWN").upper()
        for s in ("OK", "INCOMPLETE", "BLOCKED"):
            values[f"context_{layer}={s}"] = 1.0 if status == s else 0.0

    # --- direction_hint (B+) ---
    dh = str(_get(cs, "direction_hint") or "UNKNOWN").upper()
    for hint in ("BULLISH", "BEARISH", "MIXED", "UNKNOWN"):
        values[f"direction_hint={hint}"] = 1.0 if dh == hint else 0.0

    # --- regime_stack (B+) ---
    regime_stack = _get(cs, "regime_stack") or {}
    for layer in ("D1", "H4", "H1"):
        regime = str(regime_stack.get(layer) or "UNKNOWN").upper()
        for r in V2_REGIME_LABELS:
            values[f"regime_{layer}={r}"] = 1.0 if regime == r else 0.0

    # --- BOS HTF (C+) ---
    bos_htf = _get(raw, "bos_htf") or {}
    for layer in ("D1", "H4", "H1"):
        for direction in ("bullish", "bearish"):
            v = bos_htf.get(layer, {}).get(direction)
            values[f"bos_{layer.lower()}_{direction}"] = 1.0 if v is True else 0.0

    # --- lifecycle (C+) ---
    lifecycle = _get(raw, "lifecycle") or {}
    stage = str(_get(lifecycle, "stage") or "SETUP").upper()
    for s in V2_LIFECYCLE_STAGES:
        values[f"lifecycle={s}"] = 1.0 if stage == s else 0.0

    # --- M5 micro (D+) ---
    m5 = _get(raw, "M5") or {}
    for key in ("m5_bos", "m5_displacement", "m5_fvg"):
        for direction in ("bullish", "bearish"):
            v = _get(m5, key, direction)
            values[f"{key}_{direction}"] = 1.0 if v is True else 0.0

    # --- M1 micro (E+) ---
    m1 = _get(raw, "M1") or {}
    v_trigger = m1.get("m1_trigger")
    values["m1_trigger_bullish"] = 1.0 if v_trigger is True else 0.0
    values["m1_trigger_bearish"] = 1.0 if v_trigger is False else 0.0
    retest = str(_get(m1, "m1_retest") or "UNKNOWN").upper()
    for state in V2_M1_RETEST_STATES:
        values[f"m1_retest={state}"] = 1.0 if retest == state else 0.0

    # --- Permissions tri-state (F+) — NO bool(None)->False collapse ---
    perms = _get(raw, "permissions") or {}
    for key in ("allow_long", "allow_short"):
        v = perms.get(key)
        values[f"{key}_allow"] = 1.0 if v is True else 0.0
        values[f"{key}_block"] = 1.0 if v is False else 0.0
        values[f"{key}_no_opinion"] = 1.0 if v is None else 0.0
    # sum==1 guard
    for key in ("allow_long", "allow_short"):
        s = (values[f"{key}_allow"] + values[f"{key}_block"] + values[f"{key}_no_opinion"])
        if abs(s - 1.0) > 1e-9:
            raise OutcomeClassifierError(
                f"permiso {key} tri-state sum != 1: {s} (TRI_STATE_COLLAPSED)"
            )

    # --- reason_codes one-hot (F+) ---
    reason_codes = _get(raw, "reason_codes") or []
    for code in V2_REASONS:
        values[f"reason_{code}"] = 1.0 if code in reason_codes else 0.0
    values["reason_ACCEPTED"] = 1.0 if "ACCEPTED" in reason_codes or not reason_codes else 0.0

    # --- Intrinsic A-features from intraday_v2 (when present) ---
    intraday_v2 = _get(raw, "intraday_v2") or {}
    ict = intraday_v2.get("ict_m15", {})
    for name in (
        "bos_bullish", "bos_bearish", "choch_bullish", "choch_bearish",
        "displacement_bullish", "displacement_bearish", "fvg_bullish",
        "fvg_bearish", "sweep_up", "sweep_down",
    ):
        if f"ict_m15_{name}" in feature_names:
            v = ict.get(name)
            values.setdefault(f"ict_m15_{name}", 1.0 if v is True else 0.0)
    wyckoff = intraday_v2.get("wyckoff", {})
    for layer in ("H1", "M15"):
        lp = wyckoff.get(layer, {}) if isinstance(wyckoff, Mapping) else {}
        phase = str(lp.get("phase", "UNKNOWN")).upper()
        for val in INTRADAY_PHASES:
            k = f"wyckoff_{layer.lower()}_phase={val}"
            if k in feature_names:
                values.setdefault(k, 1.0 if phase == val else 0.0)
        events = lp.get("events", ())
        evt_set = set()
        if isinstance(events, (list, tuple)):
            for e in events:
                if isinstance(e, Mapping):
                    evt_set.add(str(e.get("event_type", e.get("type", ""))).upper())
                else:
                    evt_set.add(str(e).upper())
        for val in INTRADAY_EVENTS:
            k = f"wyckoff_{layer.lower()}_event={val}"
            if k in feature_names:
                values.setdefault(k, 1.0 if val in evt_set else 0.0)

    # Assemble vector
    unknown = sorted(set(feature_names).difference(values))
    if unknown:
        raise OutcomeClassifierError(f"perfil v2-B..F contiene features desconocidas: {unknown}")
    result = np.asarray([values[name] for name in feature_names], dtype=float)
    if len(result) != len(feature_names) or not np.isfinite(result).all():
        raise OutcomeClassifierError("vector v2-B..F de features inválido")
    return result


def _features(
    row: Mapping[str, Any],
    feature_names: Sequence[str] = FEATURE_NAMES,
) -> np.ndarray:
    if tuple(feature_names) in INTRADAY_FEATURE_PROFILES.values():
        return _intraday_features(row, feature_names)
    if tuple(feature_names) in _V2_FEATURE_TUPLES:
        return _v2_features(row, feature_names)
    raw = row.get("features_at_t", row)
    if not isinstance(raw, Mapping):
        raise OutcomeClassifierError("features_at_t debe ser un objeto")
    context = raw.get("context_inputs", {})
    if not isinstance(context, Mapping):
        raise OutcomeClassifierError("features_at_t.context_inputs debe ser un objeto")
    sequence = raw.get("sequence", ())
    if not isinstance(sequence, (list, tuple)):
        raise OutcomeClassifierError("features_at_t.sequence debe ser una lista")
    values = [
        _finite(context.get("sequence_direction", row.get("direction", 0)), "direction"),
        _finite(row.get("sequence_depth", 0), "sequence_depth"),
    ]
    for field, categories in _CATEGORIES.items():
        actual = str(context.get(field, "UNKNOWN")).upper()
        values.extend(1.0 if actual == category else 0.0 for category in categories)
    stages = {str(stage).upper() for stage in sequence}
    values.extend(1.0 if stage in stages else 0.0 for stage in (
        "LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE", "OB", "FVG", "CONFLUENCE"
    ))
    result = np.asarray(values, dtype=float)
    if len(result) != len(FEATURE_NAMES) or not np.isfinite(result).all():
        raise OutcomeClassifierError("vector de features inválido")
    return result


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exponent = np.exp(np.clip(shifted, -700.0, 700.0))
    return exponent / exponent.sum(axis=1, keepdims=True)


def _rows(
    rows: Sequence[Mapping[str, Any]],
    target: str,
    feature_names: Sequence[str] = FEATURE_NAMES,
) -> tuple[np.ndarray, np.ndarray]:
    if not rows:
        raise OutcomeClassifierError("no hay filas para entrenar/evaluar")
    labels: list[int] = []
    matrix: list[np.ndarray] = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("can_trade") is not False:
            raise OutcomeClassifierError("todas las filas deben conservar can_trade=false")
        label = str(row.get(target, "")).lower()
        if label not in OUTCOME_CLASSES:
            raise OutcomeClassifierError(f"etiqueta {target} inválida: {label!r}")
        matrix.append(_features(row, feature_names))
        labels.append(OUTCOME_CLASSES.index(label))
    return np.vstack(matrix), np.asarray(labels, dtype=int)


def _metrics(probabilities: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    predicted = np.argmax(probabilities, axis=1)
    clipped = np.clip(probabilities[np.arange(len(labels)), labels], 1e-15, 1.0)
    counts = {name: int(np.sum(labels == index)) for index, name in enumerate(OUTCOME_CLASSES)}
    return {
        "rows": int(len(labels)),
        "accuracy": float(np.mean(predicted == labels)),
        "log_loss": float(-np.mean(np.log(clipped))),
        "class_counts": counts,
    }


@dataclass(frozen=True)
class OutcomeClassifierArtifact:
    """Modelo serializable, trazable y sin autoridad de trading."""

    model_id: str
    model_version: str
    target: str
    snapshot_id: str
    dataset_hash: str
    schema_hash: str
    source_code_commit: str
    experiment_id: str
    feature_names: tuple[str, ...]
    classes: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    weights: tuple[tuple[float, ...], ...]
    bias: tuple[float, ...]
    metrics: Mapping[str, Any]
    seed: int
    shadow_mode: bool = True
    can_trade: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OutcomeClassifierArtifact":
        """Rehidrata un artefacto serializado sin entrenar ni conceder autoridad.

        La carga verifica la identidad del artefacto y conserva las barreras de
        Shadow Mode. Se usa para evaluar un candidato congelado; nunca ajusta
        pesos ni escribe en el registry productivo.
        """
        if not isinstance(payload, Mapping):
            raise OutcomeClassifierError("el artefacto debe ser un objeto")
        body = dict(payload)
        expected_hash = body.pop("artifact_hash", None)
        if expected_hash is not None:
            actual_hash = hashlib.sha256(_canonical_json(body)).hexdigest()
            if str(expected_hash) != actual_hash:
                raise OutcomeClassifierError("artifact_hash no coincide con el contenido")
        if body.get("schema_version") != OUTCOME_CLASSIFIER_SCHEMA_VERSION:
            raise OutcomeClassifierError("schema_version de artefacto no soportada")
        if tuple(body.get("classes", ())) != OUTCOME_CLASSES:
            raise OutcomeClassifierError("clases del artefacto no coinciden con el contrato")
        feature_names = tuple(str(value) for value in body.get("feature_names", ()))
        if feature_names not in INTRADAY_FEATURE_PROFILES.values() and feature_names != FEATURE_NAMES:
            raise OutcomeClassifierError("perfil de features del artefacto no está registrado")
        try:
            mean = tuple(_finite(value, "mean") for value in body["mean"])
            scale = tuple(_finite(value, "scale") for value in body["scale"])
            weights = tuple(
                tuple(_finite(value, "weights") for value in row)
                for row in body["weights"]
            )
            bias = tuple(_finite(value, "bias") for value in body["bias"])
        except (KeyError, TypeError) as exc:
            raise OutcomeClassifierError("parámetros numéricos incompletos") from exc
        dimension = len(feature_names)
        if len(mean) != dimension or len(scale) != dimension:
            raise OutcomeClassifierError("mean/scale no coinciden con feature_names")
        if any(value == 0.0 for value in scale):
            raise OutcomeClassifierError("scale no puede contener cero")
        if len(weights) != len(OUTCOME_CLASSES) or any(len(row) != dimension for row in weights):
            raise OutcomeClassifierError("weights no coincide con clases/features")
        if len(bias) != len(OUTCOME_CLASSES):
            raise OutcomeClassifierError("bias no coincide con clases")
        if body.get("can_trade") is not False or body.get("shadow_mode") is not True:
            raise OutcomeClassifierError("un artefacto evaluable debe permanecer en Shadow Mode")
        return cls(
            model_id=str(body["model_id"]),
            model_version=str(body["model_version"]),
            target=str(body["target"]),
            snapshot_id=str(body["snapshot_id"]),
            dataset_hash=str(body["dataset_hash"]),
            schema_hash=str(body["schema_hash"]),
            source_code_commit=str(body["source_code_commit"]),
            experiment_id=str(body["experiment_id"]),
            feature_names=feature_names,
            classes=tuple(str(value) for value in body["classes"]),
            mean=mean,
            scale=scale,
            weights=weights,
            bias=bias,
            metrics=body.get("metrics", {}),
            seed=int(body["seed"]),
            shadow_mode=True,
            can_trade=False,
        )

    def _probabilities(self, features: Mapping[str, Any]) -> np.ndarray:
        vector = _features(features, self.feature_names)
        mean = np.asarray(self.mean, dtype=float)
        scale = np.asarray(self.scale, dtype=float)
        weights = np.asarray(self.weights, dtype=float)
        bias = np.asarray(self.bias, dtype=float)
        return _softmax(((vector - mean) / scale).reshape(1, -1) @ weights.T + bias)[0]

    def predict(self, features: Mapping[str, Any], *, in_domain: bool | None = None) -> dict[str, Any]:
        probabilities = self._probabilities(features)
        feature_vector = _features(features, self.feature_names)
        confidence = float(np.max(probabilities))
        index = int(np.argmax(probabilities))
        abstention = evaluate_abstention(
            {name: float(value) for name, value in zip(self.feature_names, feature_vector)},
            confidence,
            in_domain,
            required_features=("direction", "sequence_depth"),
        )
        return {
            "schema_version": OUTCOME_CLASSIFIER_SCHEMA_VERSION,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "target": self.target,
            "lineage": {
                "snapshot_id": self.snapshot_id,
                "dataset_hash": self.dataset_hash,
                "schema_hash": self.schema_hash,
                "source_code_commit": self.source_code_commit,
                "experiment_id": self.experiment_id,
            },
            "prediction": self.classes[index],
            "probabilities": {name: float(probabilities[i]) for i, name in enumerate(self.classes)},
            "confidence": confidence,
            "abstention": abstention.to_dict(),
            "shadow_mode": True,
            "can_trade": False,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": OUTCOME_CLASSIFIER_SCHEMA_VERSION,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "target": self.target,
            "snapshot_id": self.snapshot_id,
            "dataset_hash": self.dataset_hash,
            "schema_hash": self.schema_hash,
            "source_code_commit": self.source_code_commit,
            "experiment_id": self.experiment_id,
            "feature_names": list(self.feature_names),
            "classes": list(self.classes),
            "mean": list(self.mean),
            "scale": list(self.scale),
            "weights": [list(row) for row in self.weights],
            "bias": list(self.bias),
            "metrics": json.loads(json.dumps(self.metrics, sort_keys=True)),
            "seed": self.seed,
            "shadow_mode": True,
            "can_trade": False,
        }
        payload["artifact_hash"] = hashlib.sha256(_canonical_json(payload)).hexdigest()
        return payload

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination


def train_outcome_classifier(
    pipeline: TrainingPipeline,
    *,
    research_gate: Mapping[str, Any],
    target: str = "label_end_6",
    min_class_rows: int = 5,
    iterations: int = 500,
    learning_rate: float = 0.05,
    l2: float = 1e-4,
    feature_names: Sequence[str] = FEATURE_NAMES,
) -> OutcomeClassifierArtifact:
    """Entrena el baseline únicamente con autorización científica explícita."""
    plan = pipeline.plan()
    if not isinstance(research_gate, Mapping):
        raise TrainingAuthorizationError("research_gate requerido")
    if research_gate.get("status") != "PASS" or research_gate.get("verdict") != "TRAINING_ELIGIBLE":
        raise TrainingAuthorizationError("el experimento no está TRAINING_ELIGIBLE")
    if research_gate.get("dataset_hash") != plan.dataset_hash:
        raise TrainingAuthorizationError("research_gate.dataset_hash no coincide")
    if target not in plan.labels:
        raise OutcomeClassifierError(f"target no registrado en labels: {target}")
    if isinstance(min_class_rows, bool) or not isinstance(min_class_rows, int) or min_class_rows < 1:
        raise OutcomeClassifierError("min_class_rows debe ser entero positivo")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise OutcomeClassifierError("iterations debe ser entero positivo")
    feature_names = tuple(feature_names)
    if feature_names not in (FEATURE_NAMES, *INTRADAY_FEATURE_PROFILES.values(), *_V2_FEATURE_TUPLES):
        raise OutcomeClassifierError("perfil de features no registrado")
    lr = _finite(learning_rate, "learning_rate")
    penalty = _finite(l2, "l2")
    if lr <= 0 or penalty < 0:
        raise OutcomeClassifierError("learning_rate/l2 fuera de rango")

    train_rows, validation_rows, test_rows = plan.split.train, plan.split.validation, plan.split.test
    for name, rows in (("train", train_rows), ("validation", validation_rows), ("test", test_rows)):
        if len(rows) < _MIN_ROWS[name]:
            raise TrainingAuthorizationError(f"{name} no alcanza el mínimo de {_MIN_ROWS[name]} filas")
    x_train, y_train = _rows(train_rows, target, feature_names)
    x_validation, y_validation = _rows(validation_rows, target, feature_names)
    x_test, y_test = _rows(test_rows, target, feature_names)
    counts = np.bincount(y_train, minlength=len(OUTCOME_CLASSES))
    if np.any(counts < min_class_rows):
        raise TrainingAuthorizationError("TRAIN no contiene soporte mínimo para las tres clases")

    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale = np.where(scale > 0.0, scale, 1.0)
    normalized_train = (x_train - mean) / scale
    rng = np.random.default_rng(plan.seed)
    weights = rng.normal(0.0, 0.01, size=(len(OUTCOME_CLASSES), x_train.shape[1]))
    bias = np.zeros(len(OUTCOME_CLASSES), dtype=float)
    one_hot = np.eye(len(OUTCOME_CLASSES))[y_train]
    for _ in range(iterations):
        probabilities = _softmax(normalized_train @ weights.T + bias)
        error = probabilities - one_hot
        weights -= lr * ((error.T @ normalized_train) / len(y_train) + penalty * weights)
        bias -= lr * error.mean(axis=0)

    def evaluate(rows: Sequence[Mapping[str, Any]], x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
        normalized = (x - mean) / scale
        return _metrics(_softmax(normalized @ weights.T + bias), y)

    metrics = {
        "model_training_executed": True,
        "algorithm": "deterministic_multinomial_softmax",
        "target": target,
        "classes": list(OUTCOME_CLASSES),
        "train": evaluate(train_rows, x_train, y_train),
        "validation": evaluate(validation_rows, x_validation, y_validation),
        "test_oos": evaluate(test_rows, x_test, y_test),
        "selection_scope": "TRAIN only for fitting; VALIDATION for reporting",
        "oos_scope": "TEST_OOS never used for fitting",
        "calibration_status": "NOT_CALIBRATED",
        "policy": "SHADOW_ONLY_NO_ORDER",
    }
    return OutcomeClassifierArtifact(
        model_id=plan.model_id,
        model_version=plan.model_version,
        target=target,
        snapshot_id=plan.snapshot_id,
        dataset_hash=plan.dataset_hash,
        schema_hash=plan.schema_hash,
        source_code_commit=pipeline.registry.get_model(plan.model_id, plan.model_version).git_commit,
        experiment_id=pipeline.registry.get_model(plan.model_id, plan.model_version).experiment_id,
        feature_names=feature_names,
        classes=OUTCOME_CLASSES,
        mean=tuple(float(value) for value in mean),
        scale=tuple(float(value) for value in scale),
        weights=tuple(tuple(float(value) for value in row) for row in weights),
        bias=tuple(float(value) for value in bias),
        metrics=metrics,
        seed=plan.seed,
    )


__all__ = [
    "FEATURE_NAMES",
    "INTRADAY_BASE_FEATURE_NAMES",
    "INTRADAY_FEATURE_PROFILES",
    "INTRADAY_ICT_FEATURE_NAMES",
    "INTRADAY_ICT_ONLY_FEATURE_NAMES",
    "INTRADAY_FEATURE_NAMES",
    "INTRADAY_WYCKOFF_FEATURE_NAMES",
    "INTRADAY_WYCKOFF_ONLY_FEATURE_NAMES",
    "OUTCOME_CLASSES",
    "OUTCOME_CLASSIFIER_SCHEMA_VERSION",
    "OutcomeClassifierArtifact",
    "OutcomeClassifierError",
    "TrainingAuthorizationError",
    "train_outcome_classifier",
]
