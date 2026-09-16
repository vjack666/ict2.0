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
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/v_jac/Desktop/ICT SYSTEM")
OUT_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1"
REPORT_DIR = ROOT / "reports/audits/experiments/ai"
REPORT_MD = REPORT_DIR / "setup_grammar_dataset_v1.md"
REPORT_JSON = REPORT_DIR / "setup_grammar_dataset_v1.json"

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


def po3_phase(stages: set[str]) -> str:
    if {"SWEEP", "DISPLACEMENT", "STRUCTURE", "RETEST"}.issubset(stages) and ("FVG" in stages or "OB" in stages):
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


def pd_array_zone(stages: set[str]) -> str:
    if "FVG" in stages or "OB" in stages:
        return "USABLE_UNGRADED"
    return "NO_ZONE"


def retest_entry(stages: set[str]) -> str:
    if "RETEST" in stages:
        return "RETESTED"
    if "FVG" in stages or "OB" in stages:
        return "WAIT_RETEST"
    return "MISSING_ZONE_FEATURE"


def poi_quality(row: dict[str, Any], zone_label: str) -> str:
    h4_location = str(((row.get("features_at_t") or {}).get("context_inputs") or {}).get("h4_location", "MISSING")).upper()
    direction = int(row.get("direction", 0))
    correct_zone = (direction > 0 and h4_location == "DISCOUNT") or (direction < 0 and h4_location == "PREMIUM")
    if zone_label == "NO_ZONE":
        return "MISSING_PD_ARRAY_ZONE"
    if correct_zone and htf_narrative(row) == "HTF_OK":
        return "T2_CANDIDATE_UNVERIFIED"
    if h4_location in {"PREMIUM", "DISCOUNT", "EQUILIBRIUM"}:
        return "SKIP_OR_LOW_QUALITY"
    return "MISSING_LOCATION_EVIDENCE"


def exec_tf_integrity(row: dict[str, Any]) -> str:
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
        ("MISSING_ZONE_FEATURE", "retest_entry"),
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
    if labels["pd_array_zone"] == "NO_ZONE" or labels["retest_entry"].startswith("MISSING"):
        return "ABSTAIN"
    if labels["retest_entry"] == "WAIT_RETEST":
        return "WAIT"
    if labels["poi_quality"] == "SKIP_OR_LOW_QUALITY":
        return "ABSTAIN"
    if labels["exec_tf_integrity"].startswith("MISSING"):
        return "ABSTAIN"
    return "PASS"


def materialize_row(row: dict[str, Any]) -> dict[str, Any]:
    stages = sequence_set(row)
    labels = {
        "htf_narrative": htf_narrative(row),
        "po3_phase": po3_phase(stages),
        "liquidity_sweep": liquidity_sweep(stages),
        "displacement_quality": displacement_quality(stages),
        "structure_confirmation": structure_confirmation(stages),
        "pd_array_zone": pd_array_zone(stages),
        "retest_entry": retest_entry(stages),
        "exec_tf_integrity": exec_tf_integrity(row),
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
        "grammar_labels": labels,
        "source_time_by_feature": {key: row.get("event_time") for key in labels},
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
    if labels["pd_array_zone"] == "NO_ZONE":
        output["diagnostics"].append("PD_ARRAY_ZONE_NOT_MATERIALIZED")
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
        "PD_ARRAY_ZONE_NOT_MATERIALIZED",
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
            "Current corpus contains H1 sequence context, not full exec-TF replay.",
            "PD Array zone, retest entry, POI stacking, and exec TF are partially unavailable and explicitly labelled as missing.",
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
        "La materializacion queda bloqueada para entrenamiento estricto porque el usuario no acepta `UNKNOWN` ni huecos como clases entrenables. El corpus actual no trae replay de exec TF y no trae PD Array/retest completos para todas las filas. Eso queda como evidencia faltante, no como etiqueta aceptada.",
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
        "Materializar primero replay de exec TF y zona PD Array/retest completa. No entrenar `setup_quality_v1` mientras existan faltantes bloqueantes.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [materialize_row(row) for row in load_rows()]
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
