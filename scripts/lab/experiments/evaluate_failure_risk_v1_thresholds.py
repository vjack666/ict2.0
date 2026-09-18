#!/usr/bin/env python3
"""
Evaluate thresholding and abstention for failure_risk_v1.

Loop policy:
  - Candidate redesigns are evaluated and selected only on VALIDATION.
  - TEST_OOS is used once for final evaluation of the selected candidate.
  - If TEST_OOS fails, the result is REVIEW/FAIL; do not tune using TEST_OOS.
  - Diagnostic research only: can_trade=false, shadow_mode=true.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


ROOT = Path(__file__).resolve().parent.parent  # raíz del repo
RUN_DIR = ROOT / "data/ml/tensorflow/failure_risk_v1"
REPORT_DIR = ROOT / "reports/audits/experiments/ai"
PREDICTIONS_PATH = RUN_DIR / "predictions.json"
OUT_JSON = RUN_DIR / "thresholding_v1.json"
REPORT_PATH = REPORT_DIR / "failure_risk_v1_thresholding.md"
FIG_PATH = REPORT_DIR / "failure_risk_v1_thresholding_curve.png"

THRESHOLDS = [round(x, 2) for x in np.arange(0.05, 0.76, 0.05)]
LOW_THRESHOLDS = [0.10, 0.15, 0.20, 0.25, 0.30]
HIGH_THRESHOLDS = [0.35, 0.40, 0.45, 0.50, 0.55]

MIN_VALIDATION_RECALL = 0.50
MIN_VALIDATION_PRECISION = 0.30
MIN_VALIDATION_F1 = 0.38
MIN_TEST_RECALL = 0.30
MIN_TEST_PRECISION = 0.30
MIN_TEST_F1 = 0.40
MAX_ABSTENTION_RATE = 0.60


@dataclass
class Candidate:
    loop_iteration: int
    design: str
    probability_source: str
    threshold: float | None = None
    low_threshold: float | None = None
    high_threshold: float | None = None


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


def clip_probs(p: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)


def logit(p: np.ndarray) -> np.ndarray:
    p = clip_probs(p)
    return np.log(p / (1 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def load_predictions() -> dict[str, dict[str, np.ndarray]]:
    raw = json.loads(PREDICTIONS_PATH.read_text(encoding="utf-8"))
    return {
        split: {
            "y": np.asarray(payload["true_labels"], dtype=int),
            "raw": clip_probs(np.asarray(payload["predicted_probs"], dtype=float)),
        }
        for split, payload in raw.items()
    }


def fit_calibrated_sources(data: dict[str, dict[str, np.ndarray]]) -> dict[str, dict[str, np.ndarray]]:
    y_val = data["VALIDATION"]["y"]
    p_val = data["VALIDATION"]["raw"]
    platt = LogisticRegression(solver="lbfgs", C=1e6, max_iter=1000, random_state=0)
    platt.fit(logit(p_val).reshape(-1, 1), y_val)
    isotonic = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    isotonic.fit(p_val, y_val)
    # Fixed from calibration_v1 selection result; fitted on VALIDATION.
    temperature, bias = 2.075, -1.075
    out: dict[str, dict[str, np.ndarray]] = {}
    for split, payload in data.items():
        raw = payload["raw"]
        out[split] = {
            "raw": raw,
            "platt": clip_probs(platt.predict_proba(logit(raw).reshape(-1, 1))[:, 1]),
            "isotonic": clip_probs(isotonic.predict(raw)),
            "temperature": clip_probs(sigmoid((logit(raw) / temperature) + bias)),
        }
    return out


def binary_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, Any]:
    pred = np.asarray(pred, dtype=int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y)),
        "predicted_positive": int(np.sum(pred)),
        "coverage": float(np.mean(pred == 1)),
        "abstention_rate": 0.0,
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "failure_precision": float(precision_score(y, pred, zero_division=0)),
        "failure_recall": float(recall_score(y, pred, zero_division=0)),
        "failure_f1": float(f1_score(y, pred, zero_division=0)),
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) else 0.0,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def abstention_metrics(y: np.ndarray, p: np.ndarray, low: float, high: float) -> dict[str, Any]:
    y = np.asarray(y, dtype=int)
    p = clip_probs(p)
    high_mask = p >= high
    low_mask = p <= low
    decision_mask = high_mask | low_mask
    pred = np.full(len(y), -1, dtype=int)
    pred[high_mask] = 1
    pred[low_mask] = 0

    if np.any(decision_mask):
        decided = binary_metrics(y[decision_mask], pred[decision_mask])
    else:
        decided = {
            "accuracy": None,
            "balanced_accuracy": None,
            "failure_precision": 0.0,
            "failure_recall": 0.0,
            "failure_f1": 0.0,
            "false_positive_rate": None,
            "false_negative_rate": None,
            "confusion_matrix": [[0, 0], [0, 0]],
        }
    high_failures = int(np.sum((y == 1) & high_mask))
    total_failures = int(np.sum(y == 1))
    low_failures = int(np.sum((y == 1) & low_mask))
    return {
        "n": int(len(y)),
        "coverage": float(np.mean(decision_mask)),
        "coverage_high_risk": float(np.mean(high_mask)),
        "coverage_low_risk": float(np.mean(low_mask)),
        "abstention_rate": float(1 - np.mean(decision_mask)),
        "failure_recall": float(high_failures / total_failures) if total_failures else 0.0,
        "failure_precision": float(high_failures / np.sum(high_mask)) if np.sum(high_mask) else 0.0,
        "failure_f1": float(
            2
            * (high_failures / np.sum(high_mask))
            * (high_failures / total_failures)
            / ((high_failures / np.sum(high_mask)) + (high_failures / total_failures))
        )
        if np.sum(high_mask) and total_failures and ((high_failures / np.sum(high_mask)) + (high_failures / total_failures))
        else 0.0,
        "missed_failures_low_risk": low_failures,
        "decided_metrics": decided,
    }


def evaluate_candidate(candidate: Candidate, y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    if candidate.design == "binary_threshold":
        assert candidate.threshold is not None
        pred = (p >= candidate.threshold).astype(int)
        return binary_metrics(y, pred)
    if candidate.design == "abstention_band":
        assert candidate.low_threshold is not None and candidate.high_threshold is not None
        return abstention_metrics(y, p, candidate.low_threshold, candidate.high_threshold)
    raise ValueError(candidate.design)


def passes_validation(candidate: Candidate, metrics: dict[str, Any]) -> bool:
    if candidate.design == "binary_threshold":
        return (
            metrics["failure_recall"] >= MIN_VALIDATION_RECALL
            and metrics["failure_precision"] >= MIN_VALIDATION_PRECISION
            and metrics["failure_f1"] >= MIN_VALIDATION_F1
        )
    return (
        metrics["failure_recall"] >= MIN_VALIDATION_RECALL
        and metrics["failure_precision"] >= MIN_VALIDATION_PRECISION
        and metrics["abstention_rate"] <= MAX_ABSTENTION_RATE
        and metrics["missed_failures_low_risk"] == 0
    )


def passes_test(metrics: dict[str, Any]) -> bool:
    return (
        metrics["failure_recall"] >= MIN_TEST_RECALL
        and metrics["failure_precision"] >= MIN_TEST_PRECISION
        and metrics["failure_f1"] >= MIN_TEST_F1
    )


def candidate_score(metrics: dict[str, Any]) -> tuple[float, float, float]:
    return (metrics["failure_f1"], metrics["failure_precision"], metrics["failure_recall"])


def build_candidates() -> list[Candidate]:
    candidates: list[Candidate] = []
    # Loop 1: raw binary thresholds.
    for t in THRESHOLDS:
        candidates.append(Candidate(1, "binary_threshold", "raw", threshold=t))
    # Loop 2: raw abstention bands.
    for low in LOW_THRESHOLDS:
        for high in HIGH_THRESHOLDS:
            if low < high:
                candidates.append(Candidate(2, "abstention_band", "raw", low_threshold=low, high_threshold=high))
    # Loop 3: calibrated binary thresholds for comparison, still selected on VALIDATION only.
    for source in ["platt", "isotonic", "temperature"]:
        for t in THRESHOLDS:
            candidates.append(Candidate(3, "binary_threshold", source, threshold=t))
    return candidates


def plot_thresholds(validation_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], selected: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "figure.facecolor": "#0f1117",
        "axes.facecolor": "#161a22",
        "axes.edgecolor": "#2d3340",
        "axes.labelcolor": "#c9d1d9",
        "xtick.color": "#8b949e",
        "ytick.color": "#8b949e",
        "text.color": "#e6edf3",
        "grid.color": "#2d3340",
    })
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, rows, title in [(axes[0], validation_rows, "VALIDATION"), (axes[1], test_rows, "TEST_OOS")]:
        raw_binary = [r for r in rows if r["candidate"]["design"] == "binary_threshold" and r["candidate"]["probability_source"] == "raw"]
        raw_binary.sort(key=lambda r: r["candidate"]["threshold"])
        thresholds = [r["candidate"]["threshold"] for r in raw_binary]
        ax.plot(thresholds, [r["metrics"]["failure_recall"] for r in raw_binary], marker="o", label="recall", color="#58a6ff")
        ax.plot(thresholds, [r["metrics"]["failure_precision"] for r in raw_binary], marker="o", label="precision", color="#3fb950")
        ax.plot(thresholds, [r["metrics"]["failure_f1"] for r in raw_binary], marker="o", label="F1", color="#f0883e")
        if selected["candidate"]["design"] == "binary_threshold" and selected["candidate"]["probability_source"] == "raw":
            ax.axvline(selected["candidate"]["threshold"], color="#f85149", linestyle="--", linewidth=1.5, label="selected")
        ax.set_title(title)
        ax.set_xlabel("raw threshold")
        ax.set_ylabel("metric")
        ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("failure_risk_v1 thresholding loop — raw probability")
    fig.text(0.5, 0.01, "Threshold selected on VALIDATION only. TEST_OOS is final evaluation. can_trade=false.", ha="center", fontsize=8, color="#8b949e")
    fig.tight_layout(rect=[0, 0.04, 1, 0.93])
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight", facecolor="#0f1117")
    plt.close(fig)


def main() -> int:
    base = load_predictions()
    probs = fit_calibrated_sources(base)
    candidates = build_candidates()
    validation_rows = []
    for candidate in candidates:
        metrics = evaluate_candidate(candidate, base["VALIDATION"]["y"], probs["VALIDATION"][candidate.probability_source])
        row = {
            "candidate": asdict(candidate),
            "metrics": metrics,
            "passes_validation": passes_validation(candidate, metrics),
        }
        validation_rows.append(row)

    passing = [r for r in validation_rows if r["passes_validation"]]
    loop_status = "VALIDATION_PASS" if passing else "VALIDATION_FAIL_REDESIGN_REQUIRED"
    if passing:
        selected = max(passing, key=lambda r: candidate_score(r["metrics"]))
    else:
        # Failure loop outcome: pick best diagnostic row for reporting only, not PASS.
        selected = max(validation_rows, key=lambda r: candidate_score(r["metrics"]))

    candidate = Candidate(**selected["candidate"])
    test_metrics = evaluate_candidate(candidate, base["TEST_OOS"]["y"], probs["TEST_OOS"][candidate.probability_source])
    test_pass = bool(passing and passes_test(test_metrics))

    if test_pass:
        final_status = "PASS_DIAGNOSTIC_THRESHOLD"
    elif passing:
        final_status = "REVIEW_THRESHOLD_UNSTABLE"
    else:
        final_status = "FAIL_NO_STABLE_VALIDATION_THRESHOLD"

    test_rows = [
        {
            "candidate": asdict(Candidate(1, "binary_threshold", "raw", threshold=t)),
            "metrics": evaluate_candidate(Candidate(1, "binary_threshold", "raw", threshold=t), base["TEST_OOS"]["y"], probs["TEST_OOS"]["raw"]),
        }
        for t in THRESHOLDS
    ]

    payload: dict[str, Any] = {
        "run_id": "failure_risk_v1_thresholding_v1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit": git("git rev-parse HEAD"),
        "can_trade": False,
        "shadow_mode": True,
        "source_predictions": str(PREDICTIONS_PATH),
        "source_predictions_sha256": sha256_path(PREDICTIONS_PATH),
        "selection_split": "VALIDATION",
        "evaluation_split": "TEST_OOS",
        "minimums": {
            "validation_recall": MIN_VALIDATION_RECALL,
            "validation_precision": MIN_VALIDATION_PRECISION,
            "validation_f1": MIN_VALIDATION_F1,
            "test_recall": MIN_TEST_RECALL,
            "test_precision": MIN_TEST_PRECISION,
            "test_f1": MIN_TEST_F1,
            "max_abstention_rate": MAX_ABSTENTION_RATE,
        },
        "loop_status": loop_status,
        "final_status": final_status,
        "selected": selected,
        "test_oos_selected_metrics": test_metrics,
        "validation_candidates": validation_rows,
        "test_oos_raw_threshold_curve": test_rows,
        "shadow_fusion_review_eligible": final_status == "PASS_DIAGNOSTIC_THRESHOLD",
        "automatic_fusion_allowed": False,
        "notes": [
            "Candidate selection used VALIDATION only.",
            "TEST_OOS was evaluated once after selection.",
            "If TEST_OOS fails, no redesign is performed using TEST_OOS.",
        ],
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    plot_thresholds(validation_rows, test_rows, selected)

    c = selected["candidate"]
    vm = selected["metrics"]
    tm = test_metrics
    report = [
        "# Dictamen — failure_risk_v1 thresholding v1",
        "",
        "**Fecha:** 2026-09-15",
        f"**Estado:** `{final_status}`",
        "**Politica:** `can_trade=false`, `shadow_mode=true`, `merge_with_tf_outcome_v1_003=DEFERRED`",
        "",
        "## Regla del loop",
        "",
        "El loop puede redisenar candidatos usando solo `VALIDATION`. `TEST_OOS` se usa una sola vez para evaluacion final del candidato seleccionado. Si TEST_OOS falla, no se ajusta el umbral mirando OOS.",
        "",
        "## Minimos",
        "",
        "```text",
        f"VALIDATION recall >= {MIN_VALIDATION_RECALL}",
        f"VALIDATION precision >= {MIN_VALIDATION_PRECISION}",
        f"VALIDATION F1 >= {MIN_VALIDATION_F1}",
        f"TEST_OOS recall >= {MIN_TEST_RECALL}",
        f"TEST_OOS precision >= {MIN_TEST_PRECISION}",
        f"TEST_OOS F1 >= {MIN_TEST_F1}",
        "```",
        "",
        "## Candidato seleccionado en VALIDATION",
        "",
        "```json",
        json.dumps(c, indent=2),
        "```",
        "",
        "| Split | Recall | Precision | F1 | FPR | FNR | Coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| VALIDATION | {vm['failure_recall']:.4f} | {vm['failure_precision']:.4f} | {vm['failure_f1']:.4f} | {vm.get('false_positive_rate', 0):.4f} | {vm.get('false_negative_rate', 0):.4f} | {vm['coverage']:.4f} |",
        f"| TEST_OOS | {tm['failure_recall']:.4f} | {tm['failure_precision']:.4f} | {tm['failure_f1']:.4f} | {tm.get('false_positive_rate', 0):.4f} | {tm.get('false_negative_rate', 0):.4f} | {tm['coverage']:.4f} |",
        "",
        "## Veredicto",
        "",
    ]
    if final_status == "PASS_DIAGNOSTIC_THRESHOLD":
        report.extend([
            "El candidato cumple los minimos de VALIDATION y no colapsa en TEST_OOS. Queda aprobado solo como umbral diagnostico de laboratorio.",
            "",
            "No autoriza trading ni fusion automatica. El siguiente paso es congelar contrato `FAILURE_RISK_THRESHOLD_V1` y abrir revision de fusion sombra.",
        ])
    elif final_status == "REVIEW_THRESHOLD_UNSTABLE":
        report.extend([
            "El candidato cumple VALIDATION pero no sostiene los minimos en TEST_OOS. Se congela como `REVIEW_THRESHOLD_UNSTABLE`.",
            "",
            "No se redisenara usando TEST_OOS. La siguiente accion es redisenar con mas datos, nuevo holdout o modelo mas simple.",
        ])
    else:
        report.extend([
            "Ningun candidato cumple los minimos en VALIDATION. Se activa ruta de rediseno.",
            "",
            "Rutas sugeridas: logistic baseline + drivers, small model, abstention-only o mas OOS.",
        ])
    report.extend([
        "",
        "## Artefactos",
        "",
        f"- `{OUT_JSON.relative_to(ROOT)}`",
        f"- `{FIG_PATH.relative_to(ROOT)}`",
        "",
        "## Confirmaciones",
        "",
        "- `can_trade=false` intacto.",
        "- No se activo MT5, DEMO, paper ni produccion.",
        "- No se fusiono con `tf_outcome_v1_003`.",
        "- `TEST_OOS` no se uso para seleccionar ni redisenar umbrales.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({
        "final_status": final_status,
        "selected": c,
        "validation": vm,
        "test_oos": tm,
        "artifacts": [str(OUT_JSON), str(REPORT_PATH), str(FIG_PATH)],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
