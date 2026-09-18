#!/usr/bin/env python3
"""
Calibrate failure_risk_v1 probabilities.

Calibration policy:
  - Fit calibration mappings only on VALIDATION predictions.
  - Evaluate TRAIN and TEST_OOS without fitting on them.
  - Do not alter model.keras, thresholds, datasets, or trading policy.
  - Diagnostic research only: can_trade=false, shadow_mode=true.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
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
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


ROOT = Path(__file__).resolve().parent.parent  # raíz del repo
RUN_DIR = ROOT / "data/ml/tensorflow/failure_risk_v1"
REPORT_DIR = ROOT / "reports/audits/experiments/ai"
PREDICTIONS_PATH = RUN_DIR / "predictions.json"
OUT_JSON = RUN_DIR / "calibration_v1.json"
REPORT_PATH = REPORT_DIR / "failure_risk_v1_calibration.md"
FIG_PATH = REPORT_DIR / "failure_risk_v1_calibration_curve.png"


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


def load_predictions() -> dict[str, dict[str, np.ndarray]]:
    raw = json.loads(PREDICTIONS_PATH.read_text(encoding="utf-8"))
    return {
        split: {
            "y": np.asarray(payload["true_labels"], dtype=int),
            "p": np.asarray(payload["predicted_probs"], dtype=float),
        }
        for split, payload in raw.items()
    }


def clip_probs(p: np.ndarray) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)


def logit(p: np.ndarray) -> np.ndarray:
    p = clip_probs(p)
    return np.log(p / (1 - p))


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> dict[str, Any]:
    y = np.asarray(y, dtype=float)
    p = clip_probs(p)
    value = 0.0
    details = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        mask = (p >= lo) & (p < hi if i < bins - 1 else p <= hi)
        n = int(np.sum(mask))
        if n == 0:
            details.append({"bin": i, "lo": lo, "hi": hi, "n": 0, "confidence": None, "observed_rate": None})
            continue
        confidence = float(np.mean(p[mask]))
        observed = float(np.mean(y[mask]))
        value += float(n / len(y)) * abs(confidence - observed)
        details.append({"bin": i, "lo": lo, "hi": hi, "n": n, "confidence": confidence, "observed_rate": observed})
    return {"ece": float(value), "bins": details}


def metrics(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    p = clip_probs(p)
    pred = (p >= 0.5).astype(int)
    out: dict[str, Any] = {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "failure_precision": float(precision_score(y, pred, zero_division=0)),
        "failure_recall": float(recall_score(y, pred, zero_division=0)),
        "failure_f1": float(f1_score(y, pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "log_loss": float(log_loss(y, p)),
        "brier_score": float(brier_score_loss(y, p)),
        "ece": ece(y, p)["ece"],
        "n_samples": int(len(y)),
        "n_failure": int(np.sum(y)),
        "prob_min": float(np.min(p)),
        "prob_mean": float(np.mean(p)),
        "prob_max": float(np.max(p)),
    }
    try:
        out["roc_auc"] = float(roc_auc_score(y, p))
    except ValueError:
        out["roc_auc"] = float("nan")
    try:
        out["pr_auc"] = float(average_precision_score(y, p))
    except ValueError:
        out["pr_auc"] = float("nan")
    return out


def fit_temperature(y_val: np.ndarray, p_val: np.ndarray) -> dict[str, float]:
    logits = logit(p_val)
    best = {"temperature": 1.0, "bias": 0.0, "log_loss": float("inf")}
    # Small data: deterministic grid is easier to audit than optimizer drift.
    for temperature in np.linspace(0.5, 5.0, 181):
        for bias in np.linspace(-2.0, 2.0, 161):
            calibrated = sigmoid((logits / temperature) + bias)
            loss = float(log_loss(y_val, clip_probs(calibrated)))
            if loss < best["log_loss"]:
                best = {"temperature": float(temperature), "bias": float(bias), "log_loss": loss}
    return best


def calibration_curve_points(y: np.ndarray, p: np.ndarray, bins: int = 6) -> list[dict[str, Any]]:
    details = ece(y, p, bins=bins)["bins"]
    return [d for d in details if d["n"] > 0]


def plot_curve(y: np.ndarray, raw: np.ndarray, calibrated: np.ndarray, method: str) -> None:
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
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot([0, 1], [0, 1], "--", color="#8b949e", label="Perfect calibration")
    for label, probs, color in [
        ("raw", raw, "#f85149"),
        (method, calibrated, "#3fb950"),
    ]:
        pts = calibration_curve_points(y, probs)
        ax.plot(
            [p["confidence"] for p in pts],
            [p["observed_rate"] for p in pts],
            marker="o",
            linewidth=2,
            color=color,
            label=label,
        )
        for p in pts:
            ax.text(p["confidence"], p["observed_rate"] + 0.025, str(p["n"]), ha="center", fontsize=8, color=color)
    ax.set_title("failure_risk_v1 calibration — TEST_OOS")
    ax.set_xlabel("Predicted failure probability")
    ax.set_ylabel("Observed failure rate")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.35)
    ax.legend()
    fig.text(0.5, 0.01, "Calibrator fitted on VALIDATION only. TEST_OOS is evaluation only. can_trade=false", ha="center", fontsize=8, color="#8b949e")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight", facecolor="#0f1117")
    plt.close(fig)


def main() -> int:
    data = load_predictions()
    y_val = data["VALIDATION"]["y"]
    p_val = clip_probs(data["VALIDATION"]["p"])

    platt = LogisticRegression(solver="lbfgs", C=1e6, max_iter=1000, random_state=0)
    platt.fit(logit(p_val).reshape(-1, 1), y_val)

    isotonic = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    isotonic.fit(p_val, y_val)

    temp = fit_temperature(y_val, p_val)

    def apply(method: str, p: np.ndarray) -> np.ndarray:
        if method == "raw":
            return clip_probs(p)
        if method == "platt":
            return clip_probs(platt.predict_proba(logit(p).reshape(-1, 1))[:, 1])
        if method == "isotonic":
            return clip_probs(isotonic.predict(clip_probs(p)))
        if method == "temperature":
            return clip_probs(sigmoid((logit(p) / temp["temperature"]) + temp["bias"]))
        raise ValueError(method)

    methods = ["raw", "platt", "isotonic", "temperature"]
    results: dict[str, Any] = {
        "run_id": "failure_risk_v1_calibration_v1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "can_trade": False,
        "shadow_mode": True,
        "source_predictions": str(PREDICTIONS_PATH),
        "source_predictions_sha256": sha256_path(PREDICTIONS_PATH),
        "git_commit": git("git rev-parse HEAD"),
        "fit_split": "VALIDATION",
        "evaluation_split": "TEST_OOS",
        "calibrators": {
            "platt": {
                "type": "logistic_on_logit_probability",
                "coef": float(platt.coef_[0][0]),
                "intercept": float(platt.intercept_[0]),
            },
            "isotonic": {
                "type": "isotonic_regression",
                "threshold_count": int(len(isotonic.X_thresholds_)),
            },
            "temperature": {
                "type": "logit_temperature_plus_bias_grid",
                **temp,
            },
        },
        "metrics": {},
    }

    for split, payload in data.items():
        y = payload["y"]
        p = payload["p"]
        results["metrics"][split] = {method: metrics(y, apply(method, p)) for method in methods}

    val_scores = {
        method: (
            results["metrics"]["VALIDATION"][method]["ece"],
            results["metrics"]["VALIDATION"][method]["brier_score"],
            results["metrics"]["VALIDATION"][method]["log_loss"],
        )
        for method in methods
    }
    # raw is not a calibrator candidate; choose among actual calibrators by validation ECE, then Brier, then log_loss.
    best_method = min(["platt", "isotonic", "temperature"], key=lambda m: val_scores[m])
    results["selected_calibrator"] = {
        "method": best_method,
        "selection_rule": "minimum VALIDATION ECE, tie by Brier then log_loss; TEST_OOS not used for selection",
    }

    raw_test = results["metrics"]["TEST_OOS"]["raw"]
    selected_test = results["metrics"]["TEST_OOS"][best_method]
    results["test_oos_delta_selected_vs_raw"] = {
        key: float(selected_test[key] - raw_test[key])
        for key in ["ece", "brier_score", "log_loss", "failure_recall", "failure_precision", "failure_f1", "roc_auc", "pr_auc"]
    }

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")

    plot_curve(
        data["TEST_OOS"]["y"],
        apply("raw", data["TEST_OOS"]["p"]),
        apply(best_method, data["TEST_OOS"]["p"]),
        best_method,
    )

    lines = [
        "# Dictamen — failure_risk_v1 calibration v1",
        "",
        "**Fecha:** 2026-09-15",
        "**Estado:** `REVIEW_CALIBRATION_DIAGNOSTIC`",
        "**Modelo fuente:** `failure_risk_v1`",
        "**Calibrador seleccionado:** `" + best_method + "`",
        "**Politica:** `can_trade=false`, `shadow_mode=true`, `merge_with_tf_outcome_v1_003=DEFERRED`",
        "",
        "## Regla de calibracion",
        "",
        "Los calibradores se ajustaron exclusivamente con `VALIDATION`. `TEST_OOS` se uso solo para evaluacion final.",
        "No se modifico `model.keras`, no se reentreno el modelo y no se ajustaron thresholds usando OOS.",
        "",
        "## VALIDATION",
        "",
        "| Metodo | ECE | Brier | LogLoss | Recall | Precision | F1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in methods:
        m = results["metrics"]["VALIDATION"][method]
        lines.append(
            f"| {method} | {m['ece']:.4f} | {m['brier_score']:.4f} | {m['log_loss']:.4f} | "
            f"{m['failure_recall']:.4f} | {m['failure_precision']:.4f} | {m['failure_f1']:.4f} |"
        )
    lines.extend([
        "",
        "## TEST_OOS",
        "",
        "| Metodo | ECE | Brier | LogLoss | Recall | Precision | F1 | ROC-AUC | PR-AUC |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for method in methods:
        m = results["metrics"]["TEST_OOS"][method]
        lines.append(
            f"| {method} | {m['ece']:.4f} | {m['brier_score']:.4f} | {m['log_loss']:.4f} | "
            f"{m['failure_recall']:.4f} | {m['failure_precision']:.4f} | {m['failure_f1']:.4f} | "
            f"{m['roc_auc']:.4f} | {m['pr_auc']:.4f} |"
        )
    d = results["test_oos_delta_selected_vs_raw"]
    lines.extend([
        "",
        "## Veredicto",
        "",
        f"El calibrador `{best_method}` fue seleccionado por VALIDATION. En TEST_OOS, frente a raw:",
        "",
        "```text",
        f"delta_ECE = {d['ece']:.4f}",
        f"delta_Brier = {d['brier_score']:.4f}",
        f"delta_LogLoss = {d['log_loss']:.4f}",
        f"delta_failure_recall = {d['failure_recall']:.4f}",
        f"delta_failure_f1 = {d['failure_f1']:.4f}",
        "```",
        "",
        "Interpretacion: la calibracion es diagnostica. Si mejora ECE/Brier en OOS, aun queda en `REVIEW` por muestra pequena y sobreajuste del modelo base. Si degrada alguna metrica, se documenta como tradeoff y no se promueve.",
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
        "- `TEST_OOS` no se uso para seleccionar calibrador.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "selected_calibrator": best_method,
        "validation": results["metrics"]["VALIDATION"][best_method],
        "test_oos": results["metrics"]["TEST_OOS"][best_method],
        "delta_vs_raw_test_oos": d,
        "artifacts": [str(OUT_JSON), str(REPORT_PATH), str(FIG_PATH)],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
