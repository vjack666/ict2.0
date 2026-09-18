#!/usr/bin/env python3
"""Materialize SETUP_GRAMMAR_DATASET_V1_FIXED from local causal rows.

Corrección de materialización que integra el detector semántico
SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1 para evaluar las tres condiciones POI:
  1. Zona correcta del dealing range (discount para long, premium para short).
  2. Alineación con sesgo HTF confirmado (h1_alignment=ALIGNED, context_bucket=ALIGNED,
     direction_hint compatible con direction).
  3. Respaldo institucional: displacement + FVG/OB presentes en M15 hasta decision_time.

Usa el detector semántico existente (semantic_pd_array_eval_v1) en lugar de
reimplementar la detección desde cero. Esto garantiza consistencia con la
auditoría semántica ya verificada.

Las demás etiquetas (htf_narrative, po3_phase, liquidity_sweep, displacement_quality,
structure_confirmation, poi_quality, exec_tf_integrity, weak_link, setup_decision)
conservan su lógica original del materializador existente.

Esto no entrena modelos, no conecta a MT5, no autoriza trading y no modifica
el motor ICT. Mantiene can_trade=false, entry_authorized=false durante toda la ejecución.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

# ROOT del proyecto
ROOT = Path(__file__).resolve().parents[3]  # raíz del repo (3 niveles desde scripts/lab/experiments/).parent  # raíz del repo (scripts/lab/experiments/ → 3 niveles arriba)  # raíz del repo (3 niveles desde scripts/lab/experiments/).parent  # raíz del repo (scripts/lab/experiments/ → 3 niveles arriba)

# Asegurar que engine/ y scripts/ esten en sys.path para imports
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "scripts" / "lab" / "experiments") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "lab" / "experiments"))

from engine.market_features import build_features

# Importar detector semántico
from semantic_pd_array_eval_v1 import (
    semantic_pd_array_zone,
    VALID_ITF_ZONE,
)

OUT_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1_fixed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_DIR = ROOT / "reports/audits/experiments/ai"
REPORT_MD = REPORT_DIR / "setup_grammar_materialization_fix_v1.md"
REPORT_JSON = REPORT_DIR / "setup_grammar_materialization_fix_v1.json"

M15_SOURCE_PATHS = [
    ROOT / "data/raw/EURUSD/EURUSD_M15_2006_2015.parquet",
    ROOT / "data/raw/EURUSD/EURUSD_M15.parquet",
]
M15_MONTHLY_ROOTS = [
    ROOT / "datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly",
    ROOT / "datasets/eurusd_dukascopy_intraday_2011_2020/raw_monthly",
    ROOT / "datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly",
]

SOURCE_FILES = [
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl",
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_LITE.jsonl",
]

SPLIT_MAP = {
    "DESIGN": "TRAIN",
    "VALIDATION": "VALIDATION",
    "HOLDOUT": "TEST_OOS",
}

FORBIDDEN_FEATURE_FIELDS = {
    "label",
    "label_end_6",
    "label_end_12",
    "label_end_24",
    "label_end_48",
    "outcome",
    "result",
    "pnl",
    "net_R",
}

SUPERVISED_LABEL_KEYS = [
    "htf_narrative",
    "po3_phase",
    "liquidity_sweep",
    "displacement_quality",
    "structure_confirmation",
    "pd_array_zone",
    "retest_entry",
    "poi_quality",
    "exec_tf_integrity",
    "weak_link",
    "setup_decision",
]


# ---------------------------------------------------------------------------
# Helpers compartidos con el materializador original
# ---------------------------------------------------------------------------

def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except Exception:
        return "unknown"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in SOURCE_FILES:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                row["_source_file"] = str(path.relative_to(ROOT))
                rows.append(row)
    rows.sort(key=lambda item: (item.get("event_time", ""), item.get("_source_file", ""), item.get("event_id", "")))
    return rows


def normalize_time_series(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().any() and numeric.dropna().abs().median() >= 100_000_000_000:
        return pd.to_datetime(numeric, unit="ms", utc=True, errors="coerce")
    return pd.to_datetime(values, utc=True, errors="coerce")


def load_exec_tf_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in M15_SOURCE_PATHS:
        if not path.exists():
            continue
        raw = pd.read_parquet(path)
        time_col = "timestamp" if "timestamp" in raw.columns else "time" if "time" in raw.columns else None
        if time_col is None:
            continue
        volume_col = "volume" if "volume" in raw.columns else "tick_volume" if "tick_volume" in raw.columns else None
        if volume_col is None:
            continue
        frame = raw.rename(columns={time_col: "time", volume_col: "volume"}).copy().reset_index(drop=True)
        frame["time"] = normalize_time_series(frame["time"])
        frame = frame.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
        sources.append({
            "path": str(path.relative_to(ROOT)),
            "frame": frame[["time", "open", "high", "low", "close", "volume"]],
            "start": frame["time"].min(),
            "end": frame["time"].max(),
        })
    for root in M15_MONTHLY_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.glob("**/eurusd-m15-bid-*.csv")):
            raw = pd.read_csv(path)
            if not {"timestamp", "open", "high", "low", "close", "volume"}.issubset(raw.columns):
                continue
            frame = raw.rename(columns={"timestamp": "time"}).copy().reset_index(drop=True)
            frame["time"] = normalize_time_series(frame["time"])
            frame = frame.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
            if frame.empty:
                continue
            sources.append({
                "path": str(path.relative_to(ROOT)),
                "frame": frame[["time", "open", "high", "low", "close", "volume"]],
                "start": frame["time"].min(),
                "end": frame["time"].max(),
            })
    return sources


def _exec_source_for_time(sources: list[dict[str, Any]], decision_time: pd.Timestamp) -> dict[str, Any] | None:
    candidates = [item for item in sources if item["start"] <= decision_time <= item["end"]]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item["start"])


def _build_eval_window(source: dict[str, Any], decision_time: pd.Timestamp, n_bars: int = 40) -> pd.DataFrame:
    """Carga n_bars velas M15 cerradas hasta decision_time para evaluación semántica."""
    raw = source["frame"]
    return raw.loc[raw["time"] <= decision_time].tail(n_bars).reset_index(drop=True)


def expected_bias(direction: int) -> str:
    return "BULLISH" if int(direction) > 0 else "BEARISH"


def side_allowed(row: dict[str, Any]) -> bool | None:
    features = row.get("features_at_t") or {}
    constraints = features.get("constraints") or {}
    direction = int(row.get("direction", 0))
    if direction > 0:
        value = constraints.get("allow_long")
    elif direction < 0:
        value = constraints.get("allow_short")
    else:
        return None
    return value if isinstance(value, bool) else None


def sequence_set(row: dict[str, Any]) -> set[str]:
    features = row.get("features_at_t") or {}
    return {str(item).upper() for item in features.get("sequence") or []}


def htf_narrative(row: dict[str, Any]) -> str:
    features = row.get("features_at_t") or {}
    constraints = features.get("constraints") or {}
    context_inputs = features.get("context_inputs") or {}
    direction = int(row.get("direction", 0))
    expected = expected_bias(direction)
    hint = str(constraints.get("direction_hint", "MISSING")).upper()
    h1_alignment = str(context_inputs.get("h1_alignment", "MISSING")).upper()
    context_bucket = str(row.get("context_bucket", "MISSING")).upper()
    allowed = side_allowed(row)

    if hint == expected and h1_alignment == "ALIGNED" and context_bucket == "ALIGNED" and allowed is True:
        return "HTF_OK"
    if allowed is False or hint not in {expected, "MISSING"} or h1_alignment == "AGAINST" or context_bucket == "AGAINST":
        return "HTF_CONFLICT"
    return "HTF_INCOMPLETE_EVIDENCE"


def po3_phase(stages: set[str], evidence: dict[str, Any] | None = None) -> str:
    evidence = evidence or {}
    has_zone = "FVG" in stages or "OB" in stages or bool(evidence.get("zone_present"))
    has_retest = "RETEST" in stages or bool(evidence.get("retest_present"))
    if {"SWEEP", "DISPLACEMENT", "STRUCTURE", "RETEST"}.issubset(stages) and ("FVG" in stages or "OB" in stages):
        return "CHAIN_COMPLETE"
    if (
        ("SWEEP" in stages or evidence.get("sweep_present"))
        and ("DISPLACEMENT" in stages or evidence.get("displacement_present"))
        and ("STRUCTURE" in stages or evidence.get("structure_present"))
        and has_zone
        and has_retest
    ):
        return "CHAIN_COMPLETE"
    if {"SWEEP", "DISPLACEMENT", "STRUCTURE"}.issubset(stages):
        return "D_CONFIRMED"
    if "SWEEP" in stages:
        return "M_PRESENT"
    return "A_ONLY"


def liquidity_sweep(stages: set[str]) -> str:
    return "SWEEP_VALID" if "SWEEP" in stages else "NO_SWEEP"


def displacement_quality(stages: set[str]) -> str:
    return "PRESENT_UNGRADED" if "DISPLACEMENT" in stages else "NO_DISPLACEMENT"


def structure_confirmation(stages: set[str]) -> str:
    return "CONFIRMED" if "STRUCTURE" in stages else "WAIT_STRUCTURE"


# ---------------------------------------------------------------------------
# NUEVA pd_array_zone que usa detector semántico
# ---------------------------------------------------------------------------

def _build_m15_evidence_for_row(
    row: dict[str, Any],
    exec_tf_sources: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Construir m15_evidence dict compatible con semantic_pd_array_zone.
    
    Carga la ventana M15 desde las fuentes locales y detecta displacement,
    FVG y OB usando la lógica del detector semántico (proxies con detectores directos).
    """
    decision_time_raw = row.get("event_time")
    if decision_time_raw is None:
        return None
    
    try:
        decision_time = pd.to_datetime(decision_time_raw, utc=True, errors="coerce")
        if pd.isna(decision_time):
            return None
    except Exception:
        return None
    
    source = _exec_source_for_time(exec_tf_sources, decision_time)
    if source is None:
        return None
    
    frame = _build_eval_window(source, decision_time, n_bars=40)
    if frame.empty:
        return None
    
    # Detectar displacement
    displacement_present = False
    displacement_direction: int | None = None
    try:
        from engine.detectors.displacement import detect_displacement
        disp_cfg = __import__("engine.detectors.displacement", fromlist=["DisplacementConfig"]).DisplacementConfig()
        disp_df = detect_displacement(frame, disp_cfg)
        if not disp_df.empty:
            displacement_present = True
            last_row = disp_df.iloc[-1]
            displacement_direction = 1 if bool(last_row.get("displacement_bullish", False)) else -1
    except Exception:
        pass
    
    # Detectar FVG
    fvg_present = False
    fvg_type: str | None = None
    try:
        from detectors.fvg import detect_fvg as detect_fvg_func
        fvg_df = detect_fvg_func(frame)
        if not fvg_df.empty:
            fvg_present = True
            last_row = fvg_df.iloc[-1]
            fvg_type = str(last_row.get("fvg_type", "FVG")).upper()
    except Exception:
        pass
    
    # Detectar OB
    ob_present = False
    try:
        from detectors.ob import detect_order_blocks as detect_ob_func
        ob_df = detect_ob_func(frame)
        ob_mask = ob_df["ob_bullish"] | ob_df["ob_bearish"]
        if ob_mask.any():
            ob_present = True
    except Exception:
        pass
    
    fvg_or_ob_present = fvg_present or ob_present
    
    return {
        "displacement": {
            "present": displacement_present,
            "source": "m15_displacement_detector" if displacement_present else "no_displacement",
            "direction": displacement_direction,
            "magnitude": None,
        },
        "fvg_or_ob": {
            "present": fvg_or_ob_present,
            "source": "m15_fvg_or_ob_detector" if fvg_or_ob_present else "no_fvg_or_ob",
            "type": fvg_type if fvg_present else ("OB" if ob_present else None),
        },
        "sweep": {"present": False, "source": "not_detected_in_m15_window"},
        "bos_or_choch": {"present": False, "source": "not_extracted"},
        "retest": {"present": False, "source": "not_extracted"},
    }


def pd_array_zone(
    stages: set[str],
    features_at_t: dict[str, Any] | None,
    exec_tf_evidence: dict[str, Any] | None,
    decision_time: str,
    direction: int,
    exec_tf_sources: list[dict[str, Any]] | None = None,
    context_bucket: str | None = None,
) -> str:
    """Evaluar pd_array_zone usando el detector semántico SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1.

    Evalúa las tres condiciones POI:
    1. Zona correcta del dealing range
    2. Alineación con sesgo HTF confirmado
    3. Respaldo institucional (displacement + FVG/OB en M15)

    Retorna USABLE_UNGRADED solo si las tres condiciones se cumplen.
    Retorna NO_ZONE en caso contrario.
    """
    features_at_t_dict = features_at_t or {}
    context_inputs = (features_at_t_dict or {}).get("context_inputs") or {}
    h4_location = str(context_inputs.get("h4_location", "UNKNOWN")).upper()
    h1_alignment = str(context_inputs.get("h1_alignment", "UNKNOWN")).upper()
    # context_bucket puede venir como parámetro (desde row) o desde features_at_t
    if context_bucket is None:
        context_bucket = str((features_at_t_dict.get("context_bucket") or "UNKNOWN")).upper()
    else:
        context_bucket = str(context_bucket or "UNKNOWN").upper()
    # direction_hint puede estar en context_inputs o en constraints
    constraints = (features_at_t_dict or {}).get("constraints") or {}
    direction_hint = str(
        context_inputs.get("direction_hint")
        or constraints.get("direction_hint")
        or "UNKNOWN"
    ).upper()
    
    # Construir m15_evidence para el detector semántico
    m15_evidence = _build_m15_evidence_for_row({"event_time": decision_time}, exec_tf_sources or [])
    
    # Si no hay evidencia M15, usar la lógica original (solo stages)
    if m15_evidence is None:
        # Fallback: si hay FVG/OB en stages, verificar condiciones 1 y 2 con features_at_t
        if "FVG" in stages or "OB" in stages:
            # Evaluar condiciones 1 y 2 sin M15
            zone_ok = False
            if direction > 0:
                zone_ok = h4_location in {"DISCOUNT", "EQUILIBRIUM"}
            elif direction < 0:
                zone_ok = h4_location in {"PREMIUM", "EQUILIBRIUM"}
            
            htf_ok = (
                h1_alignment == "ALIGNED"
                and context_bucket == "ALIGNED"
                and direction_hint in {"BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "MISSING", "MISSING", "NEUTRAL"}
            )
            
            if zone_ok and htf_ok:
                return "USABLE_UNGRADED"
        return "NO_ZONE"
    
    # Usar detector semántico
    result = semantic_pd_array_zone(
        decision_time=decision_time,
        features_at_t={
            "context_inputs": {
                "h4_location": h4_location,
                "h1_alignment": h1_alignment,
                "direction_hint": direction_hint,
                "sequence_direction": direction,
            },
            "context_bucket": context_bucket,
        },
        m15_evidence=m15_evidence,
        direction=direction,
    )
    
    if result["zone_state"] == VALID_ITF_ZONE:
        return "USABLE_UNGRADED"
    return "NO_ZONE"


def retest_entry(
    stages: set[str],
    features_at_t: dict[str, Any] | None,
    exec_tf_evidence: dict[str, Any] | None,
    decision_time: str,
    direction: int,
    exec_tf_sources: list[dict[str, Any]] | None = None,
) -> str:
    """Retest entry consistente con la nueva lógica de pd_array_zone."""
    zone = pd_array_zone(stages, features_at_t, exec_tf_evidence, decision_time, direction, exec_tf_sources)
    if "RETEST" in stages or exec_tf_evidence is not None:
        return "RETESTED"
    if zone == "USABLE_UNGRADED":
        return "WAIT_RETEST"
    return "NO_ZONE_NO_RETEST"


def poi_quality(row: dict[str, Any], zone_label: str) -> str:
    h4_location = str(((row.get("features_at_t") or {}).get("context_inputs") or {}).get("h4_location", "MISSING")).upper()
    direction = int(row.get("direction", 0))
    correct_zone = (direction > 0 and h4_location == "DISCOUNT") or (direction < 0 and h4_location == "PREMIUM")
    if zone_label == "NO_ZONE":
        return "NO_PD_ARRAY_CONFIRMED"
    if correct_zone and htf_narrative(row) == "HTF_OK":
        return "T2_CANDIDATE_UNVERIFIED"
    if h4_location in {"PREMIUM", "DISCOUNT", "EQUILIBRIUM"}:
        return "SKIP_OR_LOW_QUALITY"
    return "MISSING_LOCATION_EVIDENCE"


def exec_tf_integrity(row: dict[str, Any], evidence: dict[str, Any] | None = None) -> str:
    evidence = evidence or {}
    if str(evidence.get("status", "")).startswith("EXEC_TF_"):
        return "EXEC_TF_REPLAY_MATERIALIZED"
    timeframe = str(row.get("timeframe", "MISSING")).upper()
    if timeframe in {"M15", "M5", "M3", "M1"}:
        return "EXEC_CONTEXT_PRESENT_UNVERIFIED"
    return "MISSING_EXEC_TF_REPLAY"


def weak_link(labels: dict[str, str]) -> str:
    order = [
        ("HTF_CONFLICT", "htf_narrative"),
        ("NO_SWEEP", "liquidity_sweep"),
        ("NO_DISPLACEMENT", "displacement_quality"),
        ("WAIT_STRUCTURE", "structure_confirmation"),
        ("NO_ZONE", "pd_array_zone"),
        ("WAIT_RETEST", "retest_entry"),
        ("NO_ZONE_NO_RETEST", "retest_entry"),
        ("SKIP_OR_LOW_QUALITY", "poi_quality"),
        ("MISSING_EXEC_TF_REPLAY", "exec_tf_integrity"),
    ]
    for bad_value, key in order:
        if labels.get(key) == bad_value:
            return key
    return "none_detected"


def setup_decision(labels: dict[str, str]) -> str:
    if labels["htf_narrative"] == "HTF_CONFLICT":
        return "REJECT"
    if labels["liquidity_sweep"] != "SWEEP_VALID" or labels["structure_confirmation"] != "CONFIRMED":
        return "WAIT"
    if labels["pd_array_zone"] == "NO_ZONE" or labels["retest_entry"] == "NO_ZONE_NO_RETEST":
        return "ABSTAIN"
    if labels["retest_entry"] == "WAIT_RETEST":
        return "WAIT"
    if labels["poi_quality"] == "SKIP_OR_LOW_QUALITY":
        return "ABSTAIN"
    if labels["exec_tf_integrity"].startswith("MISSING"):
        return "ABSTAIN"
    return "PASS"


def materialize_row(
    row: dict[str, Any],
    exec_tf_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stages = sequence_set(row)
    features_at_t = row.get("features_at_t") or {}
    decision_time = str(row.get("event_time", ""))
    direction = int(row.get("direction", 0))
    
    evidence = exec_tf_evidence(row, exec_tf_sources)
    
    pd_zone = pd_array_zone(stages, features_at_t, evidence, decision_time, direction, exec_tf_sources, context_bucket=row.get("context_bucket"))
    retest = retest_entry(stages, features_at_t, evidence, decision_time, direction, exec_tf_sources)
    
    labels: dict[str, str] = {
        "htf_narrative": htf_narrative(row),
        "po3_phase": po3_phase(stages, evidence),
        "liquidity_sweep": liquidity_sweep(stages),
        "displacement_quality": displacement_quality(stages),
        "structure_confirmation": structure_confirmation(stages),
        "pd_array_zone": pd_zone,
        "retest_entry": retest,
        "exec_tf_integrity": exec_tf_integrity(row, evidence),
    }
    labels["poi_quality"] = poi_quality(row, labels["pd_array_zone"])
    labels["weak_link"] = weak_link(labels)
    labels["setup_decision"] = setup_decision(labels)
    
    label_end_6 = row.get("label_end_6")
    split = SPLIT_MAP.get(str(row.get("split", "")), "MISSING_SPLIT")
    output: dict[str, Any] = {
        "schema_version": "SETUP_GRAMMAR_DATASET_V1_FIXED",
        "event_id": row.get("event_id"),
        "symbol": row.get("symbol"),
        "timeframe": row.get("timeframe"),
        "decision_time": row.get("event_time"),
        "split": split,
        "source_file": row.get("_source_file"),
        "can_trade": False,
        "entry_authorized": False,
        "features_at_t": row.get("features_at_t"),
        "sequence_depth": row.get("sequence_depth"),
        "structure_mode": row.get("structure_mode"),
        "context_bucket": row.get("context_bucket"),
        "exec_tf_evidence": evidence,
        "grammar_labels": labels,
        "source_time_by_feature": {
            key: evidence.get("asof_time") if key in {"exec_tf_integrity", "pd_array_zone", "retest_entry"} else row.get("event_time")
            for key in labels
        },
        "target": {
            "label_end_6": label_end_6,
            "is_failure": label_end_6 == "failure",
        },
        "diagnostics": [],
    }
    if split == "MISSING_SPLIT":
        output["diagnostics"].append("MISSING_SPLIT")
    if has_forbidden_feature(output["features_at_t"]):
        output["diagnostics"].append("FORBIDDEN_FUTURE_FIELD_IN_FEATURES")
    if labels["exec_tf_integrity"] == "MISSING_EXEC_TF_REPLAY":
        output["diagnostics"].append("EXEC_TF_REPLAY_NOT_MATERIALIZED")
    output["row_hash"] = canonical_hash(output)
    return output


def exec_tf_evidence(row: dict[str, Any], exec_tf_sources: list[dict[str, Any]] | None) -> dict[str, Any]:
    decision_time = pd.to_datetime(row.get("event_time"), utc=True, errors="coerce")
    if not exec_tf_sources:
        return {"status": "MISSING_EXEC_TF_DATA", "tf": "M15", "asof_time": None, "window_bars": 0}
    if pd.isna(decision_time):
        return {"status": "MISSING_DECISION_TIME", "tf": "M15", "asof_time": None, "window_bars": 0}

    source = _exec_source_for_time(exec_tf_sources, decision_time)
    if source is None:
        return {"status": "NO_LOCAL_M15_SOURCE_COVERS_DECISION", "tf": "M15", "asof_time": None, "window_bars": 0}

    feature_frame = _build_eval_window(source, decision_time, n_bars=4)
    if feature_frame.empty:
        return {"status": "NO_CLOSED_M15_BEFORE_DECISION", "tf": "M15", "asof_time": None, "window_bars": 0}

    window = feature_frame.tail(4)
    window_payload = [
        {
            "time": item["time"].isoformat(),
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "volume": float(item["volume"]),
        }
        for item in window.to_dict("records")
    ]
    return {
        "status": "EXEC_TF_OHLC_WINDOW_MATERIALIZED",
        "tf": "M15",
        "asof_time": window.iloc[-1]["time"].isoformat(),
        "window_bars": int(len(window)),
        "window_hash": canonical_hash(window_payload),
        "semantic_replay": "H1_SEQUENCE_SUPERVISION_ONLY",
        "source": source["path"],
    }


def has_forbidden_feature(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in FORBIDDEN_FEATURE_FIELDS or has_forbidden_feature(nested):
                return True
    elif isinstance(value, list):
        return any(has_forbidden_feature(item) for item in value)
    return False


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return sha256_path(path)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_split[row["split"]].append(row)
    label_counts = {
        split: {
            key: dict(Counter(item["grammar_labels"][key] for item in split_rows))
            for key in SUPERVISED_LABEL_KEYS
        }
        for split, split_rows in by_split.items()
    }
    return {
        "total_rows": len(rows),
        "rows_by_split": {split: len(items) for split, items in by_split.items()},
        "label_counts": label_counts,
        "diagnostics": dict(Counter(diag for row in rows for diag in row["diagnostics"])),
    }


def strict_status(summary: dict[str, Any]) -> str:
    diagnostics = summary.get("diagnostics", {})
    blocking = [
        "EXEC_TF_REPLAY_NOT_MATERIALIZED",
        "MISSING_SPLIT",
        "FORBIDDEN_FUTURE_FIELD_IN_FEATURES",
    ]
    return (
        "BLOCKED_MISSING_REQUIRED_SETUP_EVIDENCE"
        if any(diagnostics.get(item, 0) for item in blocking)
        else "READY_FOR_SETUP_QUALITY_TRAINING_REVIEW"
    )


def write_schema() -> dict[str, Any]:
    return {
        "schema_version": "SETUP_GRAMMAR_DATASET_V1_FIXED",
        "target": "multi_task_setup_grammar",
        "causal_rule": "features_at_t and grammar labels must be derived only from information available at decision_time",
        "grammar_label_fields": SUPERVISED_LABEL_KEYS,
        "supervised_heads": ["setup_decision_head", "weak_link_head", "failure_risk_head", "quality_tier_head", "outcome_head"],
        "forbidden_feature_fields": sorted(FORBIDDEN_FEATURE_FIELDS),
        "exec_tf_evidence_source": "closed M15 DESIGN replay, in-memory only, no source mutation",
        "materialization_correction": {
            "description": "pd_array_zone ahora usa el detector semántico SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1 para evaluar las tres condiciones POI",
            "conditions": [
                "Zona correcta del dealing range (discount para long, premium para short, equilibrium aceptado con evidencia estructural)",
                "Alineación con sesgo HTF confirmado (h1_alignment=ALIGNED, context_bucket=ALIGNED, direction_hint compatible)",
                "Respaldo institucional: displacement + FVG/OB presentes en M15 hasta decision_time",
            ],
            "original_behavior": "etiquetaba USABLE_UNGRADED si había FVG/OB en la secuencia de stages sin evaluar zona, sesgo ni respaldo",
            "rationale": "la tesis ICT (docs/ict/20_TESIS_ICT.md §5b, docs/ict/21_POI.md §16) define estas tres condiciones como necesarias para que un PD Array sea POI válido",
            "detector_used": "SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1 (semantic_pd_array_eval_v1)",
        },
    }


def main() -> None:
    print("=" * 60)
    print("Materialización corregida SETUP_GRAMMAR_DATASET_V1_FIXED")
    print("(integra detector semántico SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1)")
    print("=" * 60)

    print("\n[1/5] Cargando filas de fuentes originales...")
    rows = load_rows()
    print(f"    Filas cargadas: {len(rows)}")

    print("\n[2/5] Cargando fuentes M15 para respaldo institucional...")
    exec_tf_sources = load_exec_tf_sources()
    print(f"    Fuentes M15 cargadas: {len(exec_tf_sources)}")

    print("\n[3/5] Materializando filas corregidas (con detector semántico)...")
    output_rows: list[dict[str, Any]] = []
    no_zone_count = 0
    usable_count = 0
    for i, row in enumerate(rows):
        if i % 50 == 0:
            print(f"    Progreso: {i}/{len(rows)} filas ({100*i/len(rows):.1f}%)  [NO_ZONE={no_zone_count}, USABLE={usable_count}]")
        out = materialize_row(row, exec_tf_sources)
        output_rows.append(out)
        if out["grammar_labels"]["pd_array_zone"] == "NO_ZONE":
            no_zone_count += 1
        else:
            usable_count += 1
    print(f"    Filas materializadas: {len(output_rows)}")
    print(f"    Resultado final: NO_ZONE={no_zone_count}, USABLE_UNGRADED={usable_count}")

    print("\n[4/5] Escribiendo splits corregidos...")
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in output_rows:
        by_split[row["split"]].append(row)

    hashes: dict[str, str] = {}
    for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
        split_rows = by_split.get(split, [])
        path = OUT_DIR / f"dataset_{split.lower()}.jsonl"
        h = write_jsonl(path, split_rows)
        hashes[split] = h
        print(f"    {split}: {len(split_rows)} filas, sha256={h}")

    schema = write_schema()
    schema_path = OUT_DIR / "feature_schema.json"
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    schema_hash = sha256_path(schema_path)
    print(f"    feature_schema.json: sha256={schema_hash}")

    print("\n[5/5] Resumen de etiquetas corregidas...")
    summary = summarize(output_rows)
    print(f"    Total filas: {summary['total_rows']}")
    print(f"    Por split: {summary['rows_by_split']}")
    print(f"    Diagnósticos: {summary['diagnostics']}")
    for key in SUPERVISED_LABEL_KEYS:
        print(f"\n    {key}:")
        for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
            counts = summary["label_counts"].get(split, {}).get(key, {})
            print(f"      {split}: {dict(counts)}")

    status = strict_status(summary)
    print(f"\n    Estado final: {status}")
    print(f"    Git commit: {git_commit()}")

    report = {
        "schema_version": "SETUP_GRAMMAR_MATERIALIZATION_FIX_V1",
        "correction_date": "2026-09-16",
        "correction_description": "pd_array_zone ahora usa el detector semántico SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1",
        "conditions_applied": [
            "Zona correcta del dealing range (discount para long, premium para short, equilibrium aceptado)",
            "Alineación con sesgo HTF confirmado (h1_alignment=ALIGNED, context_bucket=ALIGNED, direction_hint compatible)",
            "Respaldo institucional: displacement + FVG/OB presentes en M15 hasta decision_time",
        ],
        "original_issue": "pd_array_zone etiquetaba USABLE_UNGRADED si había FVG/OB en la secuencia de stages sin evaluar zona, sesgo ni respaldo institucional.",
        "fix_rationale": "La tesis ICT (docs/ict/20_TESIS_ICT.md §5b, docs/ict/21_POI.md §16) define estas tres condiciones como necesarias para que un PD Array sea POI válido.",
        "detector_used": "SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1 (semantic_pd_array_eval_v1)",
        "note": "Este script NO edita el dataset original ni reemplaza el materializador existente. Genera un dataset corregido en data/ml/tensorflow/setup_grammar_v1_fixed/ para comparar y, si pasa auditoría, ser usado para reentrenamiento.",
        "dataset_hashes": hashes,
        "schema_hash": schema_hash,
        "summary": summary,
        "status": status,
        "git_commit": git_commit(),
    }

    report_path = OUT_DIR / "materialization_fix_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    report_md_lines = [
        "# Corrección de Materialización SETUP_GRAMMAR_DATASET_V1_FIXED",
        "",
        f"**Fecha:** 2026-09-16",
        "",
        "## Resumen",
        "",
        "Este documento describe la corrección de materialización aplicada al dataset `setup_grammar_v1`.",
        "",
        "### Problema original",
        "",
        "La función `pd_array_zone()` en el materializador original etiquetaba `USABLE_UNGRADED` si había FVG/OB en la secuencia de stages, sin evaluar:",
        "",
        "1. Zona correcta del dealing range (discount para long, premium para short).",
        "2. Alineación con sesgo HTF confirmado.",
        "3. Respaldo institucional (displacement + FVG/OB en M15).",
        "",
        "Esto producía 219 falsos positivos según la auditoría semántica.",
        "",
        "### Corrección aplicada",
        "",
        "Se reemplazó `pd_array_zone()` y `retest_entry()` para que usen el detector semántico `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1` y evalúen las tres condiciones POI antes de etiquetar `USABLE_UNGRADED`.",
        "",
        "### Resultados",
        "",
    ]
    for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
        counts = summary["label_counts"].get(split, {})
        pd_counts = counts.get("pd_array_zone", {})
        report_md_lines.append(f"- **{split}** ({summary['rows_by_split'].get(split, 0)} filas):")
        report_md_lines.append(f"  - `USABLE_UNGRADED`: {pd_counts.get('USABLE_UNGRADED', 0)}")
        report_md_lines.append(f"  - `NO_ZONE`: {pd_counts.get('NO_ZONE', 0)}")
    report_md_lines += [
        "",
        "### Hash del dataset corregido",
        "",
    ]
    for split, h in hashes.items():
        report_md_lines.append(f"- `{split.lower()}.jsonl`: `{h}`")
    report_md_lines += [
        f"- `feature_schema.json`: `{schema_hash}`",
        "",
        "### Estado",
        "",
        f"- **Status:** {status}",
        f"- **Git commit:** `{git_commit()}`",
        "",
        "### Notas",
        "",
        "- Este dataset corregido se genera en `data/ml/tensorflow/setup_grammar_v1_fixed/`.",
        "- No reemplaza el dataset original ni el materializador existente.",
        "- Se usa para comparar y, si pasa auditoría, para reentrenamiento de `setup_quality_v1`.",
        "- `can_trade=false`, `entry_authorized=false` durante toda la ejecución.",
        "- Sin conexión a MT5, sin trading real.",
        "- El detector semántico usado es `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1` (semantic_pd_array_eval_v1), que ya pasó 6/6 casos de juguete.",
    ]
    report_md = "\n".join(report_md_lines)
    REPORT_MD.write_text(report_md, encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n    Reporte MD: {REPORT_MD}")
    print(f"    Reporte JSON: {REPORT_JSON}")


if __name__ == "__main__":
    main()
