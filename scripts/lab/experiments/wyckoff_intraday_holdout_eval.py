"""Evalúa el candidato C10 congelado sobre HOLDOUT 2021--2025.

Este runner no importa ni llama entrenamiento. Construye las observaciones del
holdout con el mismo productor causal, carga solamente los pesos serializados
del candidato C10 y calcula métricas fuera de muestra. El corpus permanece en
investigación Dukascopy, separado de MT5. Las anomalías de fuente no se reparan
ni se eliminan: requieren ``--allow-source-anomalies`` y mantienen el dictamen
formal en ``BLOCKED`` hasta resolver provenance/licencia.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.ai_learning.outcome_classifier import (  # noqa: E402
    OUTCOME_CLASSES,
    OutcomeClassifierArtifact,
    OutcomeClassifierError,
)
from scripts.lab.experiments.wyckoff_intraday_diagnostic_train import (  # noqa: E402
    HORIZON,
    _load_h1,
    build_rows,
)


DEFAULT_DATA = ROOT / "datasets" / "eurusd_dukascopy_intraday_2021_2025" / "raw_monthly"
DEFAULT_H1 = ROOT / "datasets" / "eurusd_dukascopy_20y" / "EURUSD_H1.csv"
DEFAULT_MODEL = (
    ROOT / "reports" / "audits" / "experiments" / "ai"
    / "wyckoff_intraday_2006_2010_optimization_postcommit_18bb22e"
    / "candidate_10_wyckoff_ict_combined_lr0.02_l20.001.json"
)
DEFAULT_OUTPUT_ROOT = ROOT / "reports" / "audits" / "experiments" / "ai"
HOLDOUT_START = pd.Timestamp("2021-01-01", tz="UTC")
HOLDOUT_END = pd.Timestamp("2026-01-01", tz="UTC")
EXPECTED_MONTHS = pd.period_range("2021-01", "2026-01", freq="M")
TARGET = "label_end_12"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _expected_file_keys() -> set[str]:
    return {f"{period.year:04d}-{period.month:02d}" for period in EXPECTED_MONTHS}


def _load_m15_with_audit(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    files = sorted(root.glob("*/eurusd-m15-bid-*.csv"))
    if not files:
        raise SystemExit(f"No hay M15 mensuales en {root}")
    file_keys = {path.name.split("-bid-")[1][:7] for path in files}
    missing_months = sorted(_expected_file_keys() - file_keys)
    unexpected_months = sorted(file_keys - _expected_file_keys())
    if missing_months or unexpected_months:
        raise SystemExit(
            f"cobertura mensual inválida: missing={missing_months}, unexpected={unexpected_months}"
        )

    frames: list[pd.DataFrame] = []
    manifest: list[dict[str, Any]] = []
    anomaly_rows: list[dict[str, Any]] = []
    hard_errors: list[str] = []
    for path in files:
        frame = pd.read_csv(path)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            hard_errors.append(f"{path.name}: missing columns {missing}")
            continue
        frame = frame.rename(columns={"volume": "tick_volume"})
        frame["time"] = pd.to_datetime(frame.pop("timestamp"), unit="ms", utc=True)
        if frame["time"].duplicated().any():
            hard_errors.append(f"{path.name}: duplicate timestamps")
        if not frame["time"].is_monotonic_increasing:
            hard_errors.append(f"{path.name}: timestamps not monotonic")
        hard = frame[["open", "high", "low", "close", "tick_volume"]].isna().any(axis=1) | (frame["tick_volume"] < 0)
        if hard.any():
            hard_errors.append(f"{path.name}: {int(hard.sum())} null/negative rows")
        ohlc = (
            (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        )
        if ohlc.any():
            bad_indices = frame.index[ohlc].tolist()
            anomaly_rows.append({
                "file": _relative(path),
                "row_indices": bad_indices,
                "count": len(bad_indices),
                "kind": "OHLC_INCONSISTENT",
            })
        manifest.append({
            "path": _relative(path),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "rows": len(frame),
            "min_time": frame["time"].min().isoformat(),
            "max_time": frame["time"].max().isoformat(),
        })
        frames.append(frame[["time", "open", "high", "low", "close", "tick_volume"]])
    if hard_errors:
        raise SystemExit("; ".join(hard_errors))
    result = pd.concat(frames, ignore_index=True).sort_values("time").reset_index(drop=True)
    global_duplicates = int(result["time"].duplicated().sum())
    if global_duplicates:
        raise SystemExit(f"M15 contiene {global_duplicates} timestamps duplicados globales")
    if not result["time"].is_monotonic_increasing:
        raise SystemExit("M15 global no es monotónico")
    years = result.assign(year=result["time"].dt.year).groupby("year").size().to_dict()
    anomaly_count = sum(item["count"] for item in anomaly_rows)
    audit = {
        "source": "Dukascopy historical research download",
        "download_command": "dukascopy-node -i eurusd -t m15 -p bid -vu units -f csv, monthly 2021-01 through 2026-01",
        "path": _relative(root),
        "files": len(files),
        "rows": len(result),
        "min_time": result["time"].min().isoformat(),
        "max_time": result["time"].max().isoformat(),
        "rows_by_year": {str(key): int(value) for key, value in years.items()},
        "global_duplicate_timestamps": global_duplicates,
        "gaps_gt_15_minutes": int((result["time"].diff().dropna() > pd.Timedelta(minutes=15)).sum()),
        "ohlc_anomaly_rows": anomaly_count,
        "ohlc_anomalies": anomaly_rows,
        "manifest": manifest,
        "license_permitted_use": "UNKNOWN",
        "acquisition_time_recorded": False,
        # The source is mechanically hashed, but certification remains blocked
        # until permitted-use/licence and acquisition lineage are resolved.
        "mechanical_validation_status": "REVIEW" if anomaly_count else "PASS",
        "provenance_status": "BLOCKED",
        "mt5_used": False,
        "raw_source_preserved": True,
    }
    return result, audit


def _load_frozen_model(path: Path) -> tuple[OutcomeClassifierArtifact, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SystemExit("artefacto C10 inválido: objeto requerido")
    body = dict(payload)
    outer_hash = body.get("artifact_hash")
    body_without_hash = dict(body)
    body_without_hash.pop("artifact_hash", None)
    actual_outer_hash = hashlib.sha256(_canonical_json(body_without_hash)).hexdigest()
    if outer_hash != actual_outer_hash:
        raise SystemExit("artifact_hash exterior de C10 no coincide")
    try:
        model = OutcomeClassifierArtifact.from_dict(body["model"])
    except (KeyError, OutcomeClassifierError) as exc:
        raise SystemExit(f"modelo C10 inválido: {exc}") from exc
    if model.can_trade is not False or model.shadow_mode is not True:
        raise SystemExit("C10 no conserva Shadow Mode")
    if body.get("fit_executed") is not True:
        raise SystemExit("C10 no declara ajuste ejecutado")
    return model, {
        "path": _relative(path),
        "file_sha256": _sha256(path),
        "artifact_hash": str(outer_hash),
        "model_id": model.model_id,
        "source_code_commit": model.source_code_commit,
        "dataset_hash": model.dataset_hash,
        "feature_names": list(model.feature_names),
        "target": model.target,
        "frozen": True,
    }


def _score(model: OutcomeClassifierArtifact, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise SystemExit("holdout vacío después del filtro temporal")
    actual: list[str] = []
    predicted: list[str] = []
    log_losses: list[float] = []
    by_year: dict[str, dict[str, Any]] = {}
    for row in rows:
        label = str(row[TARGET]).lower()
        if label not in OUTCOME_CLASSES:
            raise SystemExit(f"label inválido en holdout: {label}")
        result = model.predict(row, in_domain=False)
        probability = float(result["probabilities"][label])
        actual.append(label)
        predicted.append(str(result["prediction"]))
        log_losses.append(-float(np.log(np.clip(probability, 1e-15, 1.0))))
        year = str(pd.Timestamp(row["event_time"]).year)
        bucket = by_year.setdefault(year, {"rows": 0, "correct": 0, "log_loss_sum": 0.0, "class_counts": {name: 0 for name in OUTCOME_CLASSES}})
        bucket["rows"] += 1
        bucket["correct"] += int(result["prediction"] == label)
        bucket["log_loss_sum"] += log_losses[-1]
        bucket["class_counts"][label] += 1
    class_counts = {name: actual.count(name) for name in OUTCOME_CLASSES}
    majority = max(class_counts.values()) / len(actual)
    for bucket in by_year.values():
        bucket["accuracy"] = bucket.pop("correct") / bucket["rows"]
        bucket["log_loss"] = bucket.pop("log_loss_sum") / bucket["rows"]
    return {
        "rows": len(rows),
        "accuracy": sum(a == p for a, p in zip(actual, predicted)) / len(actual),
        "log_loss": sum(log_losses) / len(log_losses),
        "class_counts": class_counts,
        "predicted_class_counts": {name: predicted.count(name) for name in OUTCOME_CLASSES},
        "majority_baseline_accuracy": majority,
        "by_year": by_year,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--h1", type=Path, default=DEFAULT_H1)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-source-anomalies", action="store_true")
    args = parser.parse_args()
    m15, source_audit = _load_m15_with_audit(args.data_root.resolve())
    if source_audit["ohlc_anomaly_rows"] and not args.allow_source_anomalies:
        raise SystemExit(
            f"fuente bloqueada: {source_audit['ohlc_anomaly_rows']} anomalías OHLC; "
            "revisión explícita requerida con --allow-source-anomalies"
        )
    h1 = _load_h1(args.h1.resolve())
    model, model_lineage = _load_frozen_model(args.model.resolve())
    if model.target != TARGET:
        raise SystemExit(f"target C10 inesperado: {model.target}")
    rows, materialization = build_rows(m15, h1)
    holdout_rows = [
        row for row in rows
        if HOLDOUT_START <= pd.Timestamp(row["event_time"]) < HOLDOUT_END
    ]
    for index, row in enumerate(holdout_rows):
        row["episode_id"] = f"WYCKOFF_INTRADAY_HOLDOUT_2021_2025_M15_{index:06d}"
    scores = _score(model, holdout_rows)
    try:
        import subprocess
        runner_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        runner_commit = "UNKNOWN"
    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "1.0",
        "status": "HOLDOUT_EVALUATION_COMPLETED_BLOCKED_PROVENANCE",
        "mode": "FROZEN_CANDIDATE_EVALUATION_ONLY",
        "generated_at_utc": generated_at,
        "research_only": True,
        "fit_executed": False,
        "holdout_used_for_fit": False,
        "can_trade": False,
        "shadow_mode": True,
        "holdout": {
            "start": HOLDOUT_START.isoformat(),
            "end_exclusive": HOLDOUT_END.isoformat(),
            "label_horizon_m15_bars": HORIZON,
            "warmup_month": "2026-01",
            "rows": len(holdout_rows),
            "materialized_rows_before_filter": len(rows),
        },
        "model": model_lineage,
        "runner_code_commit": runner_commit,
        "source_audit": source_audit,
        "materialization": materialization,
        "metrics": scores,
        "next_action": "Resolver anomalías OHLC y provenance/licencia; después repetir exactamente sin reentrenar.",
    }
    report["report_sha256"] = hashlib.sha256(_canonical_json(report)).hexdigest()
    output_dir = args.output_dir.resolve() if args.output_dir else DEFAULT_OUTPUT_ROOT / f"wyckoff_intraday_holdout_2021_2025_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"salida no vacía; no se sobrescribe: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "holdout_evaluation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "report": _relative(output),
        "holdout_rows": len(holdout_rows),
        "metrics": scores,
        "source_ohlc_anomaly_rows": source_audit["ohlc_anomaly_rows"],
        "fit_executed": False,
        "can_trade": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
