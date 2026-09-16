#!/usr/bin/env python3
"""Materialize SETUP_GRAMMAR_DATASET_V1 from local causal rows.

This script turns the local ICT thesis rubric into supervised intermediate
labels. It does not train a model, download data, run MT5, or authorize
trading. Missing evidence is kept explicit instead of fabricated.
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


ROOT = Path(r"C:/Users/v_jac/Desktop/ICT SYSTEM")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_features import build_features

OUT_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1"
REPORT_DIR = ROOT / "reports/audits/experiments/ai"
REPORT_MD = REPORT_DIR / "setup_grammar_dataset_v1.md"
REPORT_JSON = REPORT_DIR / "setup_grammar_dataset_v1.json"
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


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.STDOUT,
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


def _build_exec_window(source: dict[str, Any], decision_time: pd.Timestamp) -> pd.DataFrame:
    raw = source["frame"]
    return raw.loc[raw["time"] <= decision_time].tail(4).reset_index(drop=True)


def _deprecated_load_exec_tf_frame() -> pd.DataFrame | None:
    """Kept unused to document why full-frame M15 feature builds were avoided."""
    if not M15_SOURCE_PATHS[0].exists():
        return None
    raw = pd.read_parquet(M15_SOURCE_PATHS[0])
    time_col = "timestamp" if "timestamp" in raw.columns else "time" if "time" in raw.columns else None
    if time_col is None:
        return None
    frame = raw.rename(columns={time_col: "time"}).copy().reset_index(drop=True)
    frame["time"] = normalize_time_series(frame["time"])
    frame = frame.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    features = build_features(frame[["time", "open", "high", "low", "close", "volume"]], include_liquidity_zones=False)
    features["time"] = pd.to_datetime(features["time"], utc=True, errors="coerce")
    return features.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)


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


def _directional_flag(frame: pd.DataFrame, bull_col: str, bear_col: str, direction: int) -> bool:
    if frame.empty:
        return False
    if direction > 0:
        return bool(frame.get(bull_col, pd.Series(False, index=frame.index)).fillna(False).any())
    if direction < 0:
        return bool(frame.get(bear_col, pd.Series(False, index=frame.index)).fillna(False).any())
    return False


def exec_tf_evidence(row: dict[str, Any], exec_tf_sources: list[dict[str, Any]] | None) -> dict[str, Any]:
    decision_time = pd.to_datetime(row.get("event_time"), utc=True, errors="coerce")
    if not exec_tf_sources:
        return {"status": "MISSING_EXEC_TF_DATA", "tf": "M15", "asof_time": None, "window_bars": 0}
    if pd.isna(decision_time):
        return {"status": "MISSING_DECISION_TIME", "tf": "M15", "asof_time": None, "window_bars": 0}

    source = _exec_source_for_time(exec_tf_sources, decision_time)
    if source is None:
        return {"status": "NO_LOCAL_M15_SOURCE_COVERS_DECISION", "tf": "M15", "asof_time": None, "window_bars": 0}

    feature_frame = _build_exec_window(source, decision_time)
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


def pd_array_zone(stages: set[str], evidence: dict[str, Any] | None = None) -> str:
    evidence = evidence or {}
    if "FVG" in stages or "OB" in stages or evidence.get("zone_present"):
        return "USABLE_UNGRADED"
    return "NO_ZONE"


def retest_entry(stages: set[str], evidence: dict[str, Any] | None = None) -> str:
    evidence = evidence or {}
    if "RETEST" in stages or evidence.get("retest_present"):
        return "RETESTED"
    if "FVG" in stages or "OB" in stages or evidence.get("zone_present"):
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
    # Current corpus is H1 sequence context, not an exec-TF entry replay.
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


def materialize_row(row: dict[str, Any], exec_tf_sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    stages = sequence_set(row)
    evidence = exec_tf_evidence(row, exec_tf_sources)
    labels = {
        "htf_narrative": htf_narrative(row),
        "po3_phase": po3_phase(stages, evidence),
        "liquidity_sweep": liquidity_sweep(stages),
        "displacement_quality": displacement_quality(stages),
        "structure_confirmation": structure_confirmation(stages),
        "pd_array_zone": pd_array_zone(stages, evidence),
        "retest_entry": retest_entry(stages, evidence),
        "exec_tf_integrity": exec_tf_integrity(row, evidence),
    }
    labels["poi_quality"] = poi_quality(row, labels["pd_array_zone"])
    labels["weak_link"] = weak_link(labels)
    labels["setup_decision"] = setup_decision(labels)
    label_end_6 = row.get("label_end_6")
    split = SPLIT_MAP.get(str(row.get("split", "")), "MISSING_SPLIT")
    output = {
        "schema_version": "SETUP_GRAMMAR_DATASET_V1",
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
            for key in [
                "htf_narrative",
                "po3_phase",
                "pd_array_zone",
                "retest_entry",
                "poi_quality",
                "exec_tf_integrity",
                "setup_decision",
                "weak_link",
            ]
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


def write_schema() -> None:
    schema = {
        "schema_version": "SETUP_GRAMMAR_DATASET_V1",
        "target": "multi_task_setup_grammar",
        "causal_rule": "features_at_t and grammar labels must be derived only from information available at decision_time",
        "grammar_label_fields": [
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
        ],
        "supervised_heads": [
            "setup_decision_head",
            "weak_link_head",
            "failure_risk_head",
            "quality_tier_head",
            "outcome_head",
        ],
        "forbidden_feature_fields": sorted(FORBIDDEN_FEATURE_FIELDS),
        "exec_tf_evidence_source": "closed M15 DESIGN replay, in-memory only, no source mutation",
    }
    (OUT_DIR / "feature_schema.json").write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")


def write_reports(summary: dict[str, Any], artifact_hashes: dict[str, str]) -> None:
    status = strict_status(summary)
    payload = {
        "schema_version": "SETUP_GRAMMAR_DATASET_REPORT_V1",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": status,
        "training_eligible": status == "READY_FOR_SETUP_QUALITY_TRAINING_REVIEW",
        "unknown_labels_accepted": False,
        "can_trade": False,
        "entry_authorized": False,
        "git_commit": git_commit(),
        "source_files": [
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": sha256_path(path),
            }
            for path in SOURCE_FILES
        ],
        "artifacts": artifact_hashes,
        "summary": summary,
        "limitations": [
            "Current corpus starts from H1 sequence rows; exec-TF evidence is bridged from closed local M15 bars when available.",
            "NO_ZONE is treated as a confirmed negative setup class, not as UNKNOWN.",
            "This materializes supervision labels only; no model is trained in this step.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Setup Grammar Dataset v1",
        "",
        "**Fecha:** 2026-09-15",
        f"**Estado:** `{status}`",
        "**Trading:** `can_trade=false`",
        "",
        "## Que se materializo",
        "",
        "Se convirtio la tesis ICT en etiquetas intermedias para que la red aprenda la construccion del setup, no solo el outcome final.",
        "",
        "## Conteos",
        "",
        f"- Total filas: `{summary['total_rows']}`",
    ]
    for split, count in sorted(summary["rows_by_split"].items()):
        lines.append(f"- {split}: `{count}`")
    lines.extend([
        "",
        "## Diagnosticos importantes",
        "",
    ])
    for key, count in sorted(summary["diagnostics"].items()):
        lines.append(f"- `{key}`: `{count}`")
    lines.extend([
        "",
        "## Lectura honesta",
        "",
        "La materializacion usa ventanas M15 cerradas para eliminar `UNKNOWN` como clase entrenable. `NO_ZONE` queda como clase negativa valida; solo se bloquea si falta fuente M15, split o causalidad.",
        "",
        "## Artefactos",
        "",
    ])
    for path, digest in sorted(artifact_hashes.items()):
        lines.append(f"- `{path}` sha256 `{digest}`")
    lines.extend([
        "",
        "## Siguiente paso",
        "",
        "Revisar si los faltantes bloqueantes bajaron a cero. Solo entonces entrenar `setup_quality_v1`; si quedan faltantes, ampliar la ventana/ensamblador causal y repetir.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    exec_tf_sources = load_exec_tf_sources()
    rows = [materialize_row(row, exec_tf_sources) for row in load_rows()]
    by_split: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_split[row["split"]].append(row)
    artifact_hashes: dict[str, str] = {}
    for split in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        path = OUT_DIR / f"dataset_{split.lower()}.jsonl"
        artifact_hashes[str(path.relative_to(ROOT))] = write_jsonl(path, by_split.get(split, []))
    write_schema()
    artifact_hashes[str((OUT_DIR / "feature_schema.json").relative_to(ROOT))] = sha256_path(OUT_DIR / "feature_schema.json")
    summary = summarize(rows)
    write_reports(summary, artifact_hashes)
    status = strict_status(summary)
    print(json.dumps({
        "status": status,
        "training_eligible": status == "READY_FOR_SETUP_QUALITY_TRAINING_REVIEW",
        "unknown_labels_accepted": False,
        "summary": summary,
        "artifacts": artifact_hashes,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
