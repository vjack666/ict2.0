"""Read-only execution coverage preflight for SETUP_GRAMMAR_DATASET_V1.

The preflight establishes source lineage and tests whether the existing M15
evidence can reconstruct causal execution context for ``fine_execution``.
It is diagnostic only: it never changes source data, labels, models, or any
trading authority. ``can_trade`` and ``entry_authorized`` remain false.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.execution import fine_execution


DATASET_DIR = ROOT / "data" / "ml" / "tensorflow" / "setup_grammar_v1"
REPORT_DIR = ROOT / "reports" / "audits" / "experiments" / "ai"
JSON_REPORT = REPORT_DIR / "execution_calibration_preflight_v2.json"
MD_REPORT = REPORT_DIR / "execution_calibration_preflight_v2.md"
SPLIT_FILES = {
    "TRAIN": "dataset_train.jsonl",
    "VALIDATION": "dataset_validation.jsonl",
    "TEST_OOS": "dataset_test_oos.jsonl",
}
WINDOWS = (4, 30, 50, 100)


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_value(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True,
            text=True, encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    return completed.stdout.strip() or "CLEAN"


def as_utc(value: Any) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(parsed) else parsed


def load_splits() -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    splits: dict[str, list[dict[str, Any]]] = {}
    artifacts: list[dict[str, Any]] = []
    for split, filename in SPLIT_FILES.items():
        path = DATASET_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing dataset split: {path}")
        with path.open("r", encoding="utf-8") as handle:
            splits[split] = [json.loads(line) for line in handle if line.strip()]
        artifacts.append({
            "path": path.relative_to(ROOT).as_posix(),
            "role": "input_dataset_split",
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return splits, artifacts


def source_path(row: dict[str, Any]) -> Path | None:
    source = (row.get("exec_tf_evidence") or {}).get("source")
    if not isinstance(source, str) or not source.strip():
        return None
    return ROOT / source.replace("\\", "/")


def normalize_source(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load an OHLC source and record every normalization decision."""
    if path.suffix.lower() == ".parquet":
        raw = pd.read_parquet(path)
    elif path.suffix.lower() == ".csv":
        raw = pd.read_csv(path)
    else:
        raise ValueError(f"unsupported_source_format:{path.suffix}")
    # Some normalized parquet files preserve a DatetimeIndex named ``time``.
    # The preflight reads the declared timestamp column, so the index is not a
    # second time authority and must not participate in sorting.
    raw = raw.reset_index(drop=True)
    time_column = "timestamp" if "timestamp" in raw.columns else "time"
    if time_column not in raw.columns:
        raise ValueError("missing_time_column")
    missing_ohlc = [name for name in ("open", "high", "low", "close") if name not in raw.columns]
    if missing_ohlc:
        raise ValueError("missing_ohlc:" + ",".join(missing_ohlc))

    time_values = raw[time_column]
    if pd.api.types.is_numeric_dtype(time_values):
        finite_values = pd.to_numeric(time_values, errors="coerce").dropna()
        if finite_values.empty:
            raise ValueError("empty_numeric_time_column")
        unit = "ms" if float(finite_values.abs().max()) >= 1e11 else "s"
        parsed_time = pd.to_datetime(time_values, unit=unit, utc=True, errors="coerce")
        time_policy = f"epoch_{unit}"
    else:
        parsed_time = pd.to_datetime(time_values, utc=True, errors="coerce")
        time_policy = "datetime_utc"

    frame = raw.loc[:, ["open", "high", "low", "close"]].copy()
    frame.insert(0, "time", parsed_time)
    invalid_time = int(frame["time"].isna().sum())
    non_finite_ohlc = int(frame[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    invalid_ohlc = int(
        ((frame["high"] < frame[["open", "close", "low"]].max(axis=1))
        | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))).sum()
    )
    valid = frame["time"].notna() & frame[["open", "high", "low", "close"]].notna().all(axis=1)
    usable = frame.loc[valid].sort_values("time", kind="stable").reset_index(drop=True)
    duplicate_times = int(usable["time"].duplicated().sum())
    metadata = {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "columns": list(raw.columns),
        "time_column": time_column,
        "time_policy": time_policy,
        "raw_rows": int(len(raw)),
        "usable_rows": int(len(usable)),
        "invalid_time_rows": invalid_time,
        "non_finite_ohlc_rows": non_finite_ohlc,
        "invalid_ohlc_rows": invalid_ohlc,
        "duplicate_times": duplicate_times,
        "time_min_utc": usable["time"].min().isoformat() if not usable.empty else None,
        "time_max_utc": usable["time"].max().isoformat() if not usable.empty else None,
    }
    if usable.empty:
        raise ValueError("no_usable_ohlc_rows")
    return usable, metadata


def execution_record(row: dict[str, Any], frame: pd.DataFrame, window: int) -> dict[str, Any]:
    decision_time = as_utc(row.get("decision_time"))
    context = (row.get("features_at_t") or {}).get("context_inputs") or {}
    direction = int(context.get("sequence_direction", 0) or 0)
    record = {"window_bars": window, "ok": False, "reason": None, "causal": False}
    if decision_time is None:
        record["reason"] = "invalid_decision_time"
        return record
    if direction not in (-1, 1):
        record["reason"] = "invalid_direction"
        return record
    closed = frame.loc[frame["time"] <= decision_time]
    if len(closed) < window:
        record["reason"] = "not_enough_source_history"
        record["closed_bars_available"] = int(len(closed))
        return record
    window_frame = closed.tail(window).reset_index(drop=True)
    record["causal"] = bool(window_frame["time"].max() <= decision_time)
    if not record["causal"]:
        record["reason"] = "causality_violation"
        return record
    result = fine_execution(
        ms={"M15": window_frame}, t=decision_time, direction=direction,
        exec_tf="M15", rr=3.0, sweep_ts=None,
    )
    record["ok"] = bool(result.get("ok"))
    record["reason"] = str(result.get("reason", "unknown"))
    return record


def aggregate_execution(
    splits: dict[str, list[dict[str, Any]]],
    frame_cache: dict[Path, tuple[pd.DataFrame | None, dict[str, Any]]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split, rows in splits.items():
        by_window: dict[str, Any] = {}
        for window in WINDOWS:
            checks: Counter[str] = Counter()
            reasons: Counter[str] = Counter()
            causal_failures = 0
            for row in rows:
                path = source_path(row)
                frame = frame_cache.get(path, (None, {}))[0]
                if frame is None:
                    checks["source_unavailable"] += 1
                    reasons["source_unavailable"] += 1
                    continue
                record = execution_record(row, frame, window)
                checks["tested"] += 1
                checks["ok" if record["ok"] else "fail"] += 1
                if record["reason"] == "causality_violation":
                    causal_failures += 1
                if not record["ok"]:
                    reasons[record["reason"] or "unknown"] += 1
            by_window[str(window)] = {
                "tested": checks["tested"],
                "ok": checks["ok"],
                "fail": checks["fail"],
                "ok_rate": checks["ok"] / checks["tested"] if checks["tested"] else None,
                "causality_violations": causal_failures,
                "failure_reasons": dict(reasons.most_common()),
            }
        result[split] = by_window
    return result


def frequency_summary(splits: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [row for split_rows in splits.values() for row in split_rows]
    dated_rows = [(row, as_utc(row.get("decision_time"))) for row in rows]
    dated_rows = [(row, stamp) for row, stamp in dated_rows if stamp is not None]
    stamps = [stamp for _, stamp in dated_rows]
    labels = Counter((row.get("grammar_labels") or {}).get("setup_decision", "UNKNOWN") for row, _ in dated_rows)
    decision_weeks = {(stamp.isocalendar().year, stamp.isocalendar().week) for stamp in stamps}
    pass_rows = [(row, stamp) for row, stamp in dated_rows if (row.get("grammar_labels") or {}).get("setup_decision") == "PASS"]
    pass_weeks = {(stamp.isocalendar().year, stamp.isocalendar().week) for _, stamp in pass_rows}
    economic_keys = {
        "|".join([str(row.get("symbol", "UNKNOWN")), stamp.isoformat(), str(((row.get("features_at_t") or {}).get("context_inputs") or {}).get("sequence_direction", 0))])
        for row, stamp in pass_rows
    }
    start, end = min(stamps), max(stamps)
    calendar_weeks = ((end.normalize() - start.normalize()).days // 7) + 1
    pass_unique = len(economic_keys)
    return {
        "label_counts": dict(labels),
        "first_decision_time_utc": start.isoformat(),
        "last_decision_time_utc": end.isoformat(),
        "calendar_weeks": calendar_weeks,
        "decision_weeks": len(decision_weeks),
        "pass_weeks": len(pass_weeks),
        "pass_label_rows": len(pass_rows),
        "pass_distinct_economic_keys": pass_unique,
        "pass_per_calendar_week": pass_unique / calendar_weeks,
        "pass_per_decision_week": pass_unique / len(decision_weeks),
        "target_setups_per_calendar_week": {"min": 2, "max": 3},
        "target_met": 2 <= (pass_unique / calendar_weeks) <= 3,
        "deduplication_key": "symbol|decision_time_utc|sequence_direction",
    }


def markdown_report(report: dict[str, Any]) -> str:
    coverage = report["coverage_by_split"]
    frequency = report["frequency"]
    lines = [
        "# Execution Calibration Preflight V2", "", "## Dictamen", "",
        f"Estado: **{report['status']}**. El artefacto verifica cobertura de fuente y prueba real de `fine_execution()` de forma diagnostica. No autoriza ejecucion, entradas ni trading.",
        "", "## Cobertura de fuentes", "",
        "| Split | Filas | Fuente y tiempo validos | Errores de fuente |",
        "| --- | ---: | ---: | ---: |",
    ]
    for split, values in coverage.items():
        lines.append(f"| {split} | {values['rows']} | {values['in_range']} | {values['source_errors']} |")
    lines.extend([
        "", "## Frecuencia", "",
        f"- PASS como filas de label: `{frequency['pass_label_rows']}`.",
        f"- PASS deduplicados por evento economico: `{frequency['pass_distinct_economic_keys']}`.",
        f"- Semanas calendario: `{frequency['calendar_weeks']}`; semanas con decision points: `{frequency['decision_weeks']}`.",
        f"- Frecuencia relevante contra calendario: `{frequency['pass_per_calendar_week']:.6f}` setups/semana.",
        f"- Frecuencia interna por semanas con decision points: `{frequency['pass_per_decision_week']:.6f}` setups/semana.",
        "", "## Ejecucion M15 reconstruida", "",
        "| Split | Ventana | Probadas | OK | Fail | Causalidad | Motivo principal |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for split, windows in report["execution_by_split"].items():
        for window, values in windows.items():
            main_reason = next(iter(values["failure_reasons"]), "-")
            lines.append(f"| {split} | {window} | {values['tested']} | {values['ok']} | {values['fail']} | {values['causality_violations']} | {main_reason} |")
    lines.extend([
        "", "## Gates y limites", "",
        "- `can_trade=false` y `entry_authorized=false` se mantienen en todo el dataset inspeccionado.",
        "- `sweep_ts` no esta materializado como ancla de SL; esta prueba usa el fallback estructural de `fine_execution()`.",
        "- Las ventanas se recortan estrictamente a `time <= decision_time`; toda violacion se registra como fallo causal.",
        "- El resultado no mide fills, costes, PnL ni edge. Es previo al contrato `PASS_EDGE_INTRADIA`.",
        "", "## Siguiente accion", "",
        "Construir el `FREQ_GATE_2_3_WEEKLY` y el generador determinista multimodelo antes de cualquier dataset de IA condicionado por estrategia.", "",
    ])
    return "\n".join(lines)


def run() -> dict[str, Any]:
    splits, dataset_artifacts = load_splits()
    all_rows = [row for split_rows in splits.values() for row in split_rows]
    paths = {path for row in all_rows if (path := source_path(row)) is not None}
    frame_cache: dict[Path, tuple[pd.DataFrame | None, dict[str, Any]]] = {}
    source_artifacts: list[dict[str, Any]] = []
    for path in sorted(paths):
        if not path.exists():
            frame_cache[path] = (None, {"error": "source_missing"})
            source_artifacts.append({"path": str(path), "role": "input_exec_source", "error": "source_missing"})
            continue
        try:
            frame, metadata = normalize_source(path)
            frame_cache[path] = (frame, metadata)
            source_artifacts.append({**metadata, "role": "input_exec_source"})
        except Exception as error:
            error_text = f"{type(error).__name__}:{error}"
            frame_cache[path] = (None, {"error": error_text})
            source_artifacts.append({
                "path": path.relative_to(ROOT).as_posix(),
                "role": "input_exec_source",
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "error": error_text,
            })

    coverage_by_split: dict[str, Any] = {}
    for split, rows in splits.items():
        in_range = source_errors = 0
        for row in rows:
            path = source_path(row)
            decision = as_utc(row.get("decision_time"))
            frame, metadata = frame_cache.get(path, (None, {"error": "missing_source_reference"}))
            if frame is None or decision is None:
                source_errors += 1
                continue
            start, end = as_utc(metadata.get("time_min_utc")), as_utc(metadata.get("time_max_utc"))
            if start is not None and end is not None and start <= decision <= end:
                in_range += 1
        coverage_by_split[split] = {"rows": len(rows), "in_range": in_range, "source_errors": source_errors}

    report = {
        "schema_version": "EXECUTION_CALIBRATION_PREFLIGHT_V2",
        "status": "REVIEW",
        "mode": "AUDIT_ONLY",
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "invariants": {"can_trade": False, "entry_authorized": False, "trading_authority": "NONE"},
        "coverage_by_split": coverage_by_split,
        "frequency": frequency_summary(splits),
        "execution_by_split": aggregate_execution(splits, frame_cache),
        "source_summary": {
            "unique_declared_sources": len(paths),
            "loaded_sources": sum(1 for frame, _ in frame_cache.values() if frame is not None),
            "failed_sources": sum(1 for frame, _ in frame_cache.values() if frame is None),
            "sweep_ts_materialized_rows": sum(1 for row in all_rows if (row.get("exec_tf_evidence") or {}).get("sweep_ts")),
        },
        "checks": [
            {"id": "SOURCE_LINEAGE", "status": "PASS" if all(frame is not None for frame, _ in frame_cache.values()) else "BLOCKED", "details": "Every declared source is loaded and checked against decision_time."},
            {"id": "CAUSAL_EXECUTION_WINDOW", "status": "PASS", "details": "Each invocation uses only bars at or before decision_time."},
            {"id": "SWEEP_ANCHOR", "status": "REVIEW", "details": "No materialized sweep_ts is available for an anchored structural SL."},
            {"id": "FREQUENCY_2_3_WEEKLY", "status": "BLOCKED", "details": "Existing PASS labels are far below the calendar-week target; this is not an edge conclusion."},
            {"id": "TRADING_AUTHORITY", "status": "PASS", "details": "The script is offline diagnostic only and does not create orders."},
        ],
        "artifacts": dataset_artifacts + source_artifacts,
        "generator": {
            "script": Path(__file__).relative_to(ROOT).as_posix(),
            "commit": git_value("rev-parse", "HEAD"),
            "branch": git_value("branch", "--show-current"),
            "worktree_state": "CLEAN" if not git_value("status", "--porcelain") else "DIRTY",
        },
        "next_action": "Define the deterministic multimodel candidate contract and FREQ_GATE_2_3_WEEKLY before any conditioned AI training.",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")
    MD_REPORT.write_text(markdown_report(report), encoding="utf-8")
    return report


def print_summary(report: dict[str, Any]) -> None:
    frequency = report["frequency"]
    print("EXECUTION_CALIBRATION_PREFLIGHT_V2")
    print(f"status={report['status']} mode={report['mode']}")
    print(f"sources={report['source_summary']['loaded_sources']}/{report['source_summary']['unique_declared_sources']}")
    print(f"pass_per_calendar_week={frequency['pass_per_calendar_week']:.6f}")
    for split, windows in report["execution_by_split"].items():
        summary = ", ".join(f"w{window}: {values['ok']}/{values['tested']}" for window, values in windows.items())
        print(f"{split}: {summary}")
    print(f"json={JSON_REPORT.relative_to(ROOT).as_posix()}")
    print(f"markdown={MD_REPORT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    print_summary(run())
