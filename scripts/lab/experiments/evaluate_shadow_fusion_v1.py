#!/usr/bin/env python3
"""
Evaluate shadow fusion review v1.

Compares:
  A) tf_outcome_v1_003 alone
  B) tf_outcome_v1_003 + failure_risk_v1 diagnostic state/probability

Loop policy:
  - Select fusion candidate on VALIDATION only.
  - Evaluate TEST_OOS once after selection.
  - If TEST_OOS fails, document REVIEW/FAIL; do not redesign with TEST_OOS.
  - Diagnostic shadow only: can_trade=false, no production, no orders.
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
import tensorflow as tf
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    log_loss,
    precision_recall_fscore_support,
)


ROOT = Path(__file__).resolve().parent.parent  # raíz del repo
TF_RUN = ROOT / "data/ml/tensorflow/tf_outcome_v1_003"
RISK_RUN = ROOT / "data/ml/tensorflow/failure_risk_v1"
REPORT_DIR = ROOT / "reports/audits/experiments/ai"
OUT_JSON = RISK_RUN / "shadow_fusion_v1.json"
REPORT_PATH = REPORT_DIR / "failure_risk_v1_shadow_fusion_review.md"
FIG_PATH = REPORT_DIR / "failure_risk_v1_shadow_fusion_review.png"

CORPUS_FILES = [
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl",
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_LITE.jsonl",
]
LABEL_MAP = {"continuation": 0, "reversal": 1, "failure": 2}
IDX_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}

MIN_VAL_FAILURE_RECALL_DELTA = 0.05
MIN_VAL_FAILURE_F1_DELTA = 0.0
MAX_VAL_MACRO_F1_DROP = 0.03
MAX_VAL_LOGLOSS_INCREASE = 0.10

MIN_TEST_FAILURE_RECALL_DELTA = 0.0
MIN_TEST_FAILURE_F1_DELTA = -0.02
MAX_TEST_MACRO_F1_DROP = 0.05
MAX_TEST_LOGLOSS_INCREASE = 0.15


@dataclass
class Candidate:
    loop_iteration: int
    design: str
    risk_source: str
    alpha: float = 0.0
    threshold: float = 0.25
    multiplier: float = 1.0


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


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in CORPUS_FILES:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
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


def encode_outcome_rows(rows: list[dict[str, Any]], schema: dict[str, Any]) -> np.ndarray:
    categorical = [
        ("structure_mode", lambda r: r.get("structure_mode", "UNKNOWN")),
        ("context_bucket", lambda r: r.get("context_bucket", "UNKNOWN")),
        ("d1_bias", lambda r: r["features_at_t"]["context_inputs"].get("d1_bias", "UNKNOWN")),
        ("h1_alignment", lambda r: r["features_at_t"]["context_inputs"].get("h1_alignment", "UNKNOWN")),
        ("h4_location", lambda r: r["features_at_t"]["context_inputs"].get("h4_location", "UNKNOWN")),
        ("direction_hint", lambda r: r["features_at_t"]["constraints"].get("direction_hint", "UNKNOWN")),
        ("h1_bias", lambda r: r["features_at_t"]["context_layers"].get("H1", {}).get("bias", "UNKNOWN")),
        ("h4_bias", lambda r: r["features_at_t"]["context_layers"].get("H4", {}).get("bias", "UNKNOWN")),
    ]
    numeric = [
        ("sequence_direction", lambda r: float(r["features_at_t"]["context_inputs"].get("sequence_direction", 0))),
        ("sequence_depth", lambda r: float(r.get("sequence_depth", 0))),
        ("allow_long", lambda r: 1.0 if r["features_at_t"]["constraints"].get("allow_long") else 0.0),
        ("allow_short", lambda r: 1.0 if r["features_at_t"]["constraints"].get("allow_short") else 0.0),
    ]
    matrix = []
    for row in rows:
        vec = []
        for _, getter in numeric:
            vec.append(float(getter(row)))
        for name, getter in categorical:
            cmap = schema["category_maps"][name]
            raw = str(getter(row))
            idx = cmap.get(raw, cmap["UNKNOWN"])
            one_hot = [0.0] * len(cmap)
            one_hot[idx] = 1.0
            vec.extend(one_hot)
        stages = set(row["features_at_t"].get("sequence", []))
        vec.extend([1.0 if stage in stages else 0.0 for stage in schema["sequence_stages"]])
        matrix.append(vec)
    return np.asarray(matrix, dtype=np.float32)


def load_outcome_predictions() -> dict[str, dict[str, Any]]:
    rows = split_rows(load_rows())
    schema = json.loads((TF_RUN / "feature_schema.json").read_text(encoding="utf-8"))
    model = tf.keras.models.load_model(TF_RUN / "model.keras")
    out = {}
    for split in ["VALIDATION", "TEST_OOS"]:
        split_rows_ = rows[split]
        x = encode_outcome_rows(split_rows_, schema)
        probs = clip_probs(model.predict(x, verbose=0))
        out[split] = {
            "event_ids": [r["event_id"] for r in split_rows_],
            "y": np.asarray([LABEL_MAP[r["label_end_6"]] for r in split_rows_], dtype=int),
            "probs": probs / probs.sum(axis=1, keepdims=True),
        }
    return out


def load_risk_probs() -> dict[str, dict[str, Any]]:
    raw = json.loads((RISK_RUN / "predictions.json").read_text(encoding="utf-8"))
    y_val = np.asarray(raw["VALIDATION"]["true_labels"], dtype=int)
    p_val = clip_probs(np.asarray(raw["VALIDATION"]["predicted_probs"], dtype=float))
    platt = LogisticRegression(solver="lbfgs", C=1e6, max_iter=1000, random_state=0)
    platt.fit(logit(p_val).reshape(-1, 1), y_val)
    out = {}
    for split in ["VALIDATION", "TEST_OOS"]:
        p = clip_probs(np.asarray(raw[split]["predicted_probs"], dtype=float))
        out[split] = {
            "event_ids": raw[split]["event_ids"],
            "raw": p,
            "platt": clip_probs(platt.predict_proba(logit(p).reshape(-1, 1))[:, 1]),
        }
    return out


def align(outcome: dict[str, Any], risk: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    risk_by_id = {event_id: i for i, event_id in enumerate(risk["event_ids"])}
    idx = [risk_by_id[event_id] for event_id in outcome["event_ids"]]
    return outcome["y"], outcome["probs"], np.asarray(idx, dtype=int)


def multiclass_metrics(y: np.ndarray, probs: np.ndarray) -> dict[str, Any]:
    probs = clip_probs(probs)
    probs = probs / probs.sum(axis=1, keepdims=True)
    pred = np.argmax(probs, axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(y, pred, labels=[0, 1, 2], zero_division=0)
    per_class = {
        IDX_TO_LABEL[i]: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i in [0, 1, 2]
    }
    eye = np.eye(3)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(np.mean(f1)),
        "macro_recall": float(np.mean(recall)),
        "failure_precision": per_class["failure"]["precision"],
        "failure_recall": per_class["failure"]["recall"],
        "failure_f1": per_class["failure"]["f1"],
        "log_loss": float(log_loss(y, probs, labels=[0, 1, 2])),
        "brier_score": float(np.mean(np.sum((probs - eye[y]) ** 2, axis=1))),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
        "per_class": per_class,
    }


def apply_candidate(candidate: Candidate, probs: np.ndarray, risk: np.ndarray) -> np.ndarray:
    fused = probs.copy()
    high = risk >= candidate.threshold
    if candidate.design == "failure_boost":
        fused[high, 2] = fused[high, 2] + candidate.alpha
        fused = clip_probs(fused)
        return fused / fused.sum(axis=1, keepdims=True)
    if candidate.design == "failure_multiplier":
        fused[high, 2] = fused[high, 2] * candidate.multiplier
        fused = clip_probs(fused)
        return fused / fused.sum(axis=1, keepdims=True)
    if candidate.design == "risk_blend":
        # Blend failure probability with binary risk and redistribute non-failure proportionally.
        new_failure = np.clip((1 - candidate.alpha) * fused[:, 2] + candidate.alpha * risk, 1e-6, 1 - 1e-6)
        non_failure_total = np.clip(fused[:, 0] + fused[:, 1], 1e-6, None)
        cont_share = fused[:, 0] / non_failure_total
        rev_share = fused[:, 1] / non_failure_total
        fused[:, 2] = new_failure
        fused[:, 0] = (1 - new_failure) * cont_share
        fused[:, 1] = (1 - new_failure) * rev_share
        return fused / fused.sum(axis=1, keepdims=True)
    if candidate.design == "risk_override":
        # Conservative override: only set failure if risk is high and failure was already second-best or close.
        top = np.argmax(fused, axis=1)
        failure_close = fused[:, 2] >= (np.max(fused, axis=1) - candidate.alpha)
        override = high & (top != 2) & failure_close
        fused[override, 2] = np.max(fused[override], axis=1) + 1e-3
        fused = clip_probs(fused)
        return fused / fused.sum(axis=1, keepdims=True)
    raise ValueError(candidate.design)


def build_candidates() -> list[Candidate]:
    candidates: list[Candidate] = []
    for risk_source in ["raw", "platt"]:
        for threshold in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]:
            for alpha in [0.03, 0.05, 0.08, 0.10, 0.15]:
                candidates.append(Candidate(1, "failure_boost", risk_source, alpha=alpha, threshold=threshold))
            for multiplier in [1.10, 1.20, 1.35, 1.50, 1.75]:
                candidates.append(Candidate(2, "failure_multiplier", risk_source, threshold=threshold, multiplier=multiplier))
            for alpha in [0.10, 0.20, 0.30, 0.40]:
                candidates.append(Candidate(3, "risk_blend", risk_source, alpha=alpha, threshold=threshold))
            for alpha in [0.02, 0.05, 0.08, 0.10]:
                candidates.append(Candidate(4, "risk_override", risk_source, alpha=alpha, threshold=threshold))
    return candidates


def validation_pass(base: dict[str, Any], fused: dict[str, Any]) -> bool:
    return (
        fused["failure_recall"] >= base["failure_recall"] + MIN_VAL_FAILURE_RECALL_DELTA
        and fused["failure_f1"] >= base["failure_f1"] + MIN_VAL_FAILURE_F1_DELTA
        and fused["macro_f1"] >= base["macro_f1"] - MAX_VAL_MACRO_F1_DROP
        and fused["log_loss"] <= base["log_loss"] + MAX_VAL_LOGLOSS_INCREASE
    )


def test_pass(base: dict[str, Any], fused: dict[str, Any]) -> bool:
    return (
        fused["failure_recall"] >= base["failure_recall"] + MIN_TEST_FAILURE_RECALL_DELTA
        and fused["failure_f1"] >= base["failure_f1"] + MIN_TEST_FAILURE_F1_DELTA
        and fused["macro_f1"] >= base["macro_f1"] - MAX_TEST_MACRO_F1_DROP
        and fused["log_loss"] <= base["log_loss"] + MAX_TEST_LOGLOSS_INCREASE
    )


def score(base: dict[str, Any], fused: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        fused["failure_f1"] - base["failure_f1"],
        fused["failure_recall"] - base["failure_recall"],
        fused["macro_f1"] - base["macro_f1"],
        -(fused["log_loss"] - base["log_loss"]),
    )


def plot_results(base_val: dict[str, Any], selected_val: dict[str, Any], base_test: dict[str, Any], selected_test: dict[str, Any]) -> None:
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
    labels = ["failure_recall", "failure_precision", "failure_f1", "macro_f1"]
    x = np.arange(len(labels))
    width = 0.18
    fig, ax = plt.subplots(figsize=(11, 6))
    series = [
        ("VAL base", base_val, "#58a6ff"),
        ("VAL fused", selected_val, "#3fb950"),
        ("OOS base", base_test, "#d29922"),
        ("OOS fused", selected_test, "#f85149"),
    ]
    for i, (name, metrics, color) in enumerate(series):
        vals = [metrics[k] for k in labels]
        ax.bar(x + (i - 1.5) * width, vals, width, label=name, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15)
    ax.set_ylim(0, 1)
    ax.set_title("Shadow Fusion Review v1 — base vs fused")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()
    fig.text(0.5, 0.01, "Candidate selected on VALIDATION only. TEST_OOS is final review. can_trade=false.", ha="center", fontsize=8, color="#8b949e")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(FIG_PATH, dpi=150, bbox_inches="tight", facecolor="#0f1117")
    plt.close(fig)


def main() -> int:
    outcome = load_outcome_predictions()
    risk = load_risk_probs()
    aligned: dict[str, dict[str, Any]] = {}
    for split in ["VALIDATION", "TEST_OOS"]:
        y, probs, risk_idx = align(outcome[split], risk[split])
        aligned[split] = {
            "y": y,
            "probs": probs,
            "risk": {
                "raw": risk[split]["raw"][risk_idx],
                "platt": risk[split]["platt"][risk_idx],
            },
        }

    base = {split: multiclass_metrics(aligned[split]["y"], aligned[split]["probs"]) for split in ["VALIDATION", "TEST_OOS"]}
    candidates = build_candidates()
    val_rows = []
    for candidate in candidates:
        fused_probs = apply_candidate(candidate, aligned["VALIDATION"]["probs"], aligned["VALIDATION"]["risk"][candidate.risk_source])
        metrics = multiclass_metrics(aligned["VALIDATION"]["y"], fused_probs)
        row = {
            "candidate": asdict(candidate),
            "metrics": metrics,
            "passes_validation": validation_pass(base["VALIDATION"], metrics),
            "score": score(base["VALIDATION"], metrics),
        }
        val_rows.append(row)

    passing = [r for r in val_rows if r["passes_validation"]]
    if passing:
        selected = max(passing, key=lambda r: tuple(r["score"]))
        loop_status = "VALIDATION_PASS"
    else:
        selected = max(val_rows, key=lambda r: tuple(r["score"]))
        loop_status = "VALIDATION_FAIL_REDESIGN_REQUIRED"

    candidate = Candidate(**selected["candidate"])
    test_probs = apply_candidate(candidate, aligned["TEST_OOS"]["probs"], aligned["TEST_OOS"]["risk"][candidate.risk_source])
    test_metrics = multiclass_metrics(aligned["TEST_OOS"]["y"], test_probs)

    if passing and test_pass(base["TEST_OOS"], test_metrics):
        final_status = "PASS_SHADOW_FUSION_DIAGNOSTIC"
    elif passing:
        final_status = "REVIEW_NO_STABLE_FUSION_BENEFIT"
    else:
        final_status = "FAIL_NO_VALIDATION_FUSION_BENEFIT"

    payload: dict[str, Any] = {
        "run_id": "shadow_fusion_review_v1",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git_commit": git("git rev-parse HEAD"),
        "can_trade": False,
        "shadow_mode": True,
        "automatic_fusion_allowed": False,
        "selection_split": "VALIDATION",
        "evaluation_split": "TEST_OOS",
        "tf_outcome_model": str(TF_RUN / "model.keras"),
        "tf_outcome_model_sha256": sha256_path(TF_RUN / "model.keras"),
        "risk_predictions": str(RISK_RUN / "predictions.json"),
        "risk_predictions_sha256": sha256_path(RISK_RUN / "predictions.json"),
        "minimums": {
            "validation_failure_recall_delta": MIN_VAL_FAILURE_RECALL_DELTA,
            "validation_failure_f1_delta": MIN_VAL_FAILURE_F1_DELTA,
            "validation_max_macro_f1_drop": MAX_VAL_MACRO_F1_DROP,
            "validation_max_logloss_increase": MAX_VAL_LOGLOSS_INCREASE,
            "test_failure_recall_delta": MIN_TEST_FAILURE_RECALL_DELTA,
            "test_failure_f1_delta": MIN_TEST_FAILURE_F1_DELTA,
            "test_max_macro_f1_drop": MAX_TEST_MACRO_F1_DROP,
            "test_max_logloss_increase": MAX_TEST_LOGLOSS_INCREASE,
        },
        "loop_status": loop_status,
        "final_status": final_status,
        "base_metrics": base,
        "selected": selected,
        "test_oos_selected_metrics": test_metrics,
        "validation_candidates": val_rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    plot_results(base["VALIDATION"], selected["metrics"], base["TEST_OOS"], test_metrics)

    report = [
        "# Dictamen — Shadow Fusion Review v1",
        "",
        "**Fecha:** 2026-09-15",
        f"**Estado:** `{final_status}`",
        "**Politica:** `can_trade=false`, `automatic_fusion_allowed=false`",
        "",
        "## Regla del loop",
        "",
        "Los candidatos de fusion se seleccionan solo con `VALIDATION`. `TEST_OOS` se usa una sola vez para dictamen final. Si TEST_OOS falla, no se redisenia mirando OOS.",
        "",
        "## Candidato seleccionado",
        "",
        "```json",
        json.dumps(selected["candidate"], indent=2),
        "```",
        "",
        "| Split | Modelo | Failure recall | Failure precision | Failure F1 | Macro F1 | LogLoss |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        f"| VALIDATION | v1.003 solo | {base['VALIDATION']['failure_recall']:.4f} | {base['VALIDATION']['failure_precision']:.4f} | {base['VALIDATION']['failure_f1']:.4f} | {base['VALIDATION']['macro_f1']:.4f} | {base['VALIDATION']['log_loss']:.4f} |",
        f"| VALIDATION | fusion sombra | {selected['metrics']['failure_recall']:.4f} | {selected['metrics']['failure_precision']:.4f} | {selected['metrics']['failure_f1']:.4f} | {selected['metrics']['macro_f1']:.4f} | {selected['metrics']['log_loss']:.4f} |",
        f"| TEST_OOS | v1.003 solo | {base['TEST_OOS']['failure_recall']:.4f} | {base['TEST_OOS']['failure_precision']:.4f} | {base['TEST_OOS']['failure_f1']:.4f} | {base['TEST_OOS']['macro_f1']:.4f} | {base['TEST_OOS']['log_loss']:.4f} |",
        f"| TEST_OOS | fusion sombra | {test_metrics['failure_recall']:.4f} | {test_metrics['failure_precision']:.4f} | {test_metrics['failure_f1']:.4f} | {test_metrics['macro_f1']:.4f} | {test_metrics['log_loss']:.4f} |",
        "",
        "## Veredicto",
        "",
    ]
    if final_status == "PASS_SHADOW_FUSION_DIAGNOSTIC":
        report.append("La fusion sombra cumple minimos de VALIDATION y sostiene beneficio diagnostico en TEST_OOS. Queda como diagnostico shadow, no operativo.")
    elif final_status == "REVIEW_NO_STABLE_FUSION_BENEFIT":
        report.append("La fusion sombra cumple VALIDATION pero no sostiene minimos en TEST_OOS. No se fusiona; queda REVIEW.")
    else:
        report.append("Ningun candidato cumple minimos en VALIDATION. Se activa rediseno de fusion.")
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
        "- No se cambio `tf_outcome_v1_003`.",
        "- `TEST_OOS` no se uso para seleccionar candidatos.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")

    print(json.dumps({
        "final_status": final_status,
        "selected": selected["candidate"],
        "validation_base": base["VALIDATION"],
        "validation_fused": selected["metrics"],
        "test_oos_base": base["TEST_OOS"],
        "test_oos_fused": test_metrics,
        "artifacts": [str(OUT_JSON), str(REPORT_PATH), str(FIG_PATH)],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
