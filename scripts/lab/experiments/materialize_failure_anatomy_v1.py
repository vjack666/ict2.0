#!/usr/bin/env python3
"""
Materialize Failure Anatomy v1.

Creates a diagnostic dataset for learning failure risk from already persisted
SEQ_CTX_01 rows. Source datasets are read-only; generated artifacts live under
data/ml/tensorflow/failure_anatomy_v1.

Diagnostic research only:
  can_trade=false
  shadow_mode=true
  no production, no orders, no promotion
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/v_jac/Desktop/ICT SYSTEM")
RUN_ID = "failure_anatomy_v1"
OUT_DIR = ROOT / "data/ml/tensorflow" / RUN_ID
CORPUS_FILES = [
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl",
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_LITE.jsonl",
]
LABEL = "label_end_6"
FAILURE_LABEL = "failure"
LOW_SUPPORT_MIN_TRAIN = 5

DRIVERS = [
    "HTF_CONFLICT",
    "ADVERSE_CONTEXT",
    "IMMATURE_SEQUENCE",
    "CONSTRAINT_CONTRADICTION",
    "WEAK_STRUCTURE",
    "LOW_SUPPORT_REGIME",
    "DIRECTIONAL_AMBIGUITY",
    "UNKNOWN",
]


def git(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, cwd=str(ROOT)).decode().strip()
    except Exception:
        return "unknown"


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in CORPUS_FILES:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                row["_source_file"] = path.name
                rows.append(row)
    rows.sort(key=lambda r: (r["event_time"], r["_source_file"], r["event_id"]))
    return rows


def split_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "TRAIN": [r for r in rows if r["split"] == "DESIGN"],
        "VALIDATION": [r for r in rows if r["split"] == "VALIDATION"],
        "TEST_OOS": [r for r in rows if r["split"] == "HOLDOUT"],
    }


def at(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("features_at_t", {})


def constraints(row: dict[str, Any]) -> dict[str, Any]:
    return at(row).get("constraints", {})


def context_inputs(row: dict[str, Any]) -> dict[str, Any]:
    return at(row).get("context_inputs", {})


def context_layers(row: dict[str, Any]) -> dict[str, Any]:
    return at(row).get("context_layers", {})


def norm(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return str(value).upper()


def sequence_direction(row: dict[str, Any]) -> int:
    raw = context_inputs(row).get("sequence_direction", row.get("direction", 0))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def htf_values(row: dict[str, Any]) -> dict[str, str]:
    layers = context_layers(row)
    inputs = context_inputs(row)
    return {
        "d1_bias": norm(inputs.get("d1_bias", layers.get("D1", {}).get("bias"))),
        "h1_bias": norm(layers.get("H1", {}).get("bias")),
        "h1_alignment": norm(inputs.get("h1_alignment", layers.get("H1", {}).get("alignment"))),
        "h4_bias": norm(layers.get("H4", {}).get("bias")),
        "h4_location": norm(inputs.get("h4_location", layers.get("H4", {}).get("location"))),
        "direction_hint": norm(constraints(row).get("direction_hint")),
        "context_bucket": norm(row.get("context_bucket")),
        "structure_mode": norm(row.get("structure_mode")),
    }


def regime_key(row: dict[str, Any]) -> tuple[str, ...]:
    htf = htf_values(row)
    return (
        htf["structure_mode"],
        htf["context_bucket"],
        htf["d1_bias"],
        htf["h1_alignment"],
        htf["h4_location"],
        htf["direction_hint"],
    )


def build_train_regime_counts(train: list[dict[str, Any]]) -> Counter[tuple[str, ...]]:
    return Counter(regime_key(row) for row in train)


def derive_drivers(row: dict[str, Any], train_regimes: Counter[tuple[str, ...]]) -> list[str]:
    htf = htf_values(row)
    seq_dir = sequence_direction(row)
    seq = set(row.get("features_at_t", {}).get("sequence", []))
    seq_depth = int(row.get("sequence_depth", len(seq) or 0))
    allow_long = bool(constraints(row).get("allow_long"))
    allow_short = bool(constraints(row).get("allow_short"))
    drivers: list[str] = []

    bearish_htf = any(htf[name] == "BEARISH" for name in ("d1_bias", "h1_bias", "h4_bias"))
    bullish_htf = any(htf[name] == "BULLISH" for name in ("d1_bias", "h1_bias", "h4_bias"))
    if (seq_dir > 0 and bearish_htf) or (seq_dir < 0 and bullish_htf) or htf["h1_alignment"] == "AGAINST":
        drivers.append("HTF_CONFLICT")

    if htf["context_bucket"] == "AGAINST" or htf["h1_alignment"] == "AGAINST":
        drivers.append("ADVERSE_CONTEXT")

    if seq_depth < 4:
        drivers.append("IMMATURE_SEQUENCE")

    if (seq_dir > 0 and (not allow_long or htf["direction_hint"] == "BEARISH")) or (
        seq_dir < 0 and (not allow_short or htf["direction_hint"] == "BULLISH")
    ):
        drivers.append("CONSTRAINT_CONTRADICTION")

    if "DISPLACEMENT" not in seq or "STRUCTURE" not in seq:
        drivers.append("WEAK_STRUCTURE")

    if train_regimes[regime_key(row)] < LOW_SUPPORT_MIN_TRAIN:
        drivers.append("LOW_SUPPORT_REGIME")

    directional_values = [htf["d1_bias"], htf["h1_bias"], htf["h4_bias"], htf["direction_hint"]]
    has_ambiguous = any(value in {"UNKNOWN", "MIXED", "NEUTRAL"} for value in directional_values)
    has_bullish = any(value == "BULLISH" for value in directional_values)
    has_bearish = any(value == "BEARISH" for value in directional_values)
    if has_ambiguous or (has_bullish and has_bearish) or seq_dir == 0:
        drivers.append("DIRECTIONAL_AMBIGUITY")

    if not drivers:
        drivers.append("UNKNOWN")
    return drivers


def materialize_row(row: dict[str, Any], train_regimes: Counter[tuple[str, ...]]) -> dict[str, Any]:
    drivers = derive_drivers(row, train_regimes)
    htf = htf_values(row)
    seq = row.get("features_at_t", {}).get("sequence", [])
    out = {
        "event_id": row["event_id"],
        "event_time": row["event_time"],
        "symbol": row.get("symbol"),
        "timeframe": row.get("timeframe"),
        "source_file": row["_source_file"],
        "source_dataset_id": row.get("dataset_id"),
        "source_dataset_sha256": row.get("dataset_sha256"),
        "split_source": row["split"],
        "split": "TRAIN" if row["split"] == "DESIGN" else ("TEST_OOS" if row["split"] == "HOLDOUT" else row["split"]),
        "target_label": row[LABEL],
        "is_failure": row[LABEL] == FAILURE_LABEL,
        "failure_drivers": drivers,
        "features": {
            "sequence_direction": sequence_direction(row),
            "sequence_depth": int(row.get("sequence_depth", len(seq) or 0)),
            "allow_long": bool(constraints(row).get("allow_long")),
            "allow_short": bool(constraints(row).get("allow_short")),
            "structure_mode": htf["structure_mode"],
            "context_bucket": htf["context_bucket"],
            "d1_bias": htf["d1_bias"],
            "h1_bias": htf["h1_bias"],
            "h1_alignment": htf["h1_alignment"],
            "h4_bias": htf["h4_bias"],
            "h4_location": htf["h4_location"],
            "direction_hint": htf["direction_hint"],
            "sequence_stages": seq,
            "regime_train_support": int(train_regimes[regime_key(row)]),
        },
        "driver_flags": {driver: driver in drivers for driver in DRIVERS},
        "can_trade": False,
    }
    return out


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            line = json.dumps(row, sort_keys=True, separators=(",", ":"))
            f.write(line + "\n")
            h.update((line + "\n").encode("utf-8"))
    return h.hexdigest()


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts = Counter("failure" if row["is_failure"] else "non_failure" for row in rows)
    driver_counts = Counter(driver for row in rows for driver in row["failure_drivers"])
    by_source = Counter(row["source_file"] for row in rows)
    return {
        "n": len(rows),
        "label_counts": dict(sorted(label_counts.items())),
        "driver_counts": dict(sorted(driver_counts.items())),
        "source_counts": dict(sorted(by_source.items())),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    splits = split_rows(rows)
    train_regimes = build_train_regime_counts(splits["TRAIN"])

    materialized = {
        split: [materialize_row(row, train_regimes) for row in rows_for_split]
        for split, rows_for_split in splits.items()
    }

    dataset_hashes = {}
    for split, rows_for_split in materialized.items():
        dataset_hashes[split] = write_jsonl(OUT_DIR / f"dataset_{split.lower()}.jsonl", rows_for_split)

    all_features = [
        "sequence_direction",
        "sequence_depth",
        "allow_long",
        "allow_short",
        "structure_mode",
        "context_bucket",
        "d1_bias",
        "h1_bias",
        "h1_alignment",
        "h4_bias",
        "h4_location",
        "direction_hint",
        "sequence_stages",
        "regime_train_support",
    ]
    feature_schema = {
        "run_id": RUN_ID,
        "target": "is_failure",
        "target_source": LABEL,
        "features": all_features,
        "driver_flags": DRIVERS,
        "fit_scope": "TRAIN/DESIGN only for regime support",
        "causal_rule": "features and drivers derive only from features_at_t and pre-outcome metadata",
        "forbidden_as_features": ["label_end_6", "label_end_12", "label_end_24", "label_end_48"],
    }
    write_json(OUT_DIR / "feature_schema.json", feature_schema)

    split_manifest = {
        "run_id": RUN_ID,
        "split_mapping": {"DESIGN": "TRAIN", "VALIDATION": "VALIDATION", "HOLDOUT": "TEST_OOS"},
        "splits": {split: summarize(rows_for_split) for split, rows_for_split in materialized.items()},
        "dataset_hashes": dataset_hashes,
    }
    write_json(OUT_DIR / "split_manifest.json", split_manifest)

    driver_manifest = {
        "run_id": RUN_ID,
        "taxonomy_contract": "docs/contratos/FAILURE_TAXONOMY_V1.md",
        "low_support_min_train": LOW_SUPPORT_MIN_TRAIN,
        "drivers": {
            "HTF_CONFLICT": "sequence direction conflicts with HTF bias or H1 alignment",
            "ADVERSE_CONTEXT": "context bucket or H1 alignment is against the sequence",
            "IMMATURE_SEQUENCE": "sequence_depth is below 4",
            "CONSTRAINT_CONTRADICTION": "direction contradicts allow_long/allow_short or direction_hint",
            "WEAK_STRUCTURE": "DISPLACEMENT or STRUCTURE stage is absent",
            "LOW_SUPPORT_REGIME": "context regime count in TRAIN is below threshold",
            "DIRECTIONAL_AMBIGUITY": "directional inputs are unknown, mixed, neutral, or mutually opposed",
            "UNKNOWN": "no v1 driver activated",
        },
        "driver_counts_all": dict(
            sorted(Counter(driver for rows_ in materialized.values() for row in rows_ for driver in row["failure_drivers"]).items())
        ),
    }
    write_json(OUT_DIR / "failure_driver_manifest.json", driver_manifest)

    source_manifest = {
        "run_id": RUN_ID,
        "dataset_id": "SEQ_CTX_01_CANONICAL_BOS_PLUS_LITE",
        "source_files": [
            {"path": str(path), "sha256": sha256_path(path), "bytes": path.stat().st_size}
            for path in CORPUS_FILES
        ],
        "source_rows": len(rows),
        "git_commit": git("git rev-parse HEAD"),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "can_trade": False,
        "shadow_mode": True,
    }
    write_json(OUT_DIR / "source_manifest.json", source_manifest)

    audit = {
        "status": "READY_FOR_TRAINING_REVIEW",
        "run_id": RUN_ID,
        "can_trade": False,
        "shadow_mode": True,
        "source_data_modified": False,
        "features_use_future_outcomes": False,
        "target_uses_label_end_6": True,
        "merge_with_tf_outcome_v1_003": "DEFERRED",
        "dataset_hashes": dataset_hashes,
        "split_counts": {split: len(rows_) for split, rows_ in materialized.items()},
        "failure_counts": {
            split: int(sum(1 for row in rows_ if row["is_failure"])) for split, rows_ in materialized.items()
        },
        "taxonomy_hash": sha256_text((ROOT / "docs/contratos/FAILURE_TAXONOMY_V1.md").read_text(encoding="utf-8")),
    }
    write_json(OUT_DIR / "audit.json", audit)

    report = "\n".join(
        [
            "# Failure Anatomy v1 materialization",
            "",
            f"Status: `{audit['status']}`",
            "",
            "Splits:",
            "",
            *[
                f"- {split}: n={len(rows_)}, failure={audit['failure_counts'][split]}, sha256={dataset_hashes[split]}"
                for split, rows_ in materialized.items()
            ],
            "",
            "Policy: `can_trade=false`, `shadow_mode=true`. No source datasets were modified.",
            "",
        ]
    )
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")

    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
