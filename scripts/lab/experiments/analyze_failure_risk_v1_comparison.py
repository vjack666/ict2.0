#!/usr/bin/env python3
"""
Generate comparison and memorization analysis for failure_risk_v1.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent  # raíz del repo
DATASET_DIR = ROOT / "data/ml/tensorflow/failure_anatomy_v1"
MODEL_DIR = ROOT / "data/ml/tensorflow/failure_risk_v1"

CAT_FEATURES = [
    "structure_mode", "context_bucket", "d1_bias", "h1_bias",
    "h1_alignment", "h4_bias", "h4_location", "direction_hint",
]
NUM_FEATURES = [
    "sequence_direction", "sequence_depth", "allow_long", "allow_short",
    "regime_train_support",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def compute_full_metrics(
    y_true: list[int],
    y_pred: list[int],
    y_prob: list[float],
) -> dict[str, Any]:
    from sklearn.metrics import (
        accuracy_score,
        balanced_accuracy_score,
        roc_auc_score,
        average_precision_score,
        log_loss,
        brier_score_loss,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )

    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred)
    y_prob_arr = np.array(y_prob)

    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true_arr, y_pred_arr)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true_arr, y_pred_arr)),
        "failure_recall": float(recall_score(y_true_arr, y_pred_arr, pos_label=1, zero_division=0)),
        "failure_precision": float(precision_score(y_true_arr, y_pred_arr, pos_label=1, zero_division=0)),
        "failure_f1": float(f1_score(y_true_arr, y_pred_arr, pos_label=1, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1]).tolist(),
        "n": int(len(y_true_arr)),
        "n_failure": int(y_true_arr.sum()),
    }

    y_prob_clip = np.clip(y_prob_arr, 1e-15, 1 - 1e-15)
    metrics["log_loss"] = float(log_loss(y_true_arr, y_prob_clip))
    metrics["brier_score"] = float(brier_score_loss(y_true_arr, y_prob_arr))

    try:
        metrics["roc_auc"] = float(roc_auc_score(y_true_arr, y_prob_arr))
    except ValueError:
        metrics["roc_auc"] = float("nan")
    try:
        metrics["pr_auc"] = float(average_precision_score(y_true_arr, y_prob_arr))
    except ValueError:
        metrics["pr_auc"] = float("nan")

    return metrics


def main() -> int:
    print("=" * 70)
    print("COMPARISON AND MEMORIZATION ANALYSIS")
    print("=" * 70)

    train_rows = load_jsonl(DATASET_DIR / "dataset_train.jsonl")
    val_rows = load_jsonl(DATASET_DIR / "dataset_validation.jsonl")
    test_rows = load_jsonl(DATASET_DIR / "dataset_test_oos.jsonl")

    # Load model predictions
    with open(MODEL_DIR / "predictions.json") as f:
        preds = json.load(f)

    # Compute model metrics
    model_metrics: dict[str, dict[str, Any]] = {}
    for split_name, split_key in [
        ("TRAIN", "TRAIN"), ("VALIDATION", "VALIDATION"), ("TEST_OOS", "TEST_OOS")
    ]:
        model_metrics[split_name] = compute_full_metrics(
            preds[split_key]["true_labels"],
            preds[split_key]["predicted_labels"],
            preds[split_key]["predicted_probs"],
        )

    # Compute baselines
    print("\nComputing baselines...")

    # B1: Majority class
    for split_name, rows in [
        ("TRAIN", train_rows), ("VALIDATION", val_rows), ("TEST_OOS", test_rows)
    ]:
        y = [r["is_failure"] for r in rows]
        n = len(y)
        model_metrics[f"B1_MAJORITY_{split_name}"] = compute_full_metrics(
            y, [0] * n, [0.0] * n
        )

    # B2: Prevalence
    prevalence = float(np.mean([r["is_failure"] for r in train_rows]))
    for split_name, rows in [
        ("TRAIN", train_rows), ("VALIDATION", val_rows), ("TEST_OOS", test_rows)
    ]:
        y = [r["is_failure"] for r in rows]
        n = len(y)
        model_metrics[f"B2_PREVALENCE_{split_name}"] = compute_full_metrics(
            y, [1 if prevalence >= 0.5 else 0] * n, [prevalence] * n
        )

    # B3: Driver count heuristic
    def driver_score(rows: list[dict]) -> list[float]:
        return [min(len(r["failure_drivers"]) / 8.0, 1.0) for r in rows]

    for split_name, rows in [
        ("TRAIN", train_rows), ("VALIDATION", val_rows), ("TEST_OOS", test_rows)
    ]:
        y = [r["is_failure"] for r in rows]
        y_prob = driver_score(rows)
        model_metrics[f"B3_DRIVERCOUNT_{split_name}"] = compute_full_metrics(
            y, [1 if p >= 0.5 else 0 for p in y_prob], y_prob
        )

    # B6: Logistic Regression
    print("  Fitting Logistic Regression baseline...")
    from sklearn.linear_model import LogisticRegression

    # Build vocab from train only
    vocab: dict[str, dict[str, int]] = {}
    for f in CAT_FEATURES:
        vals = sorted({r["features"][f] for r in train_rows})
        vocab[f] = {v: i for i, v in enumerate(vals)}

    num_mean = {f: float(np.mean([r["features"][f] for r in train_rows])) for f in NUM_FEATURES}
    num_std = {f: float(np.std([r["features"][f] for r in train_rows])) for f in NUM_FEATURES}
    for f in NUM_FEATURES:
        if num_std[f] < 1e-10:
            num_std[f] = 1.0

    def encode_and_scale(rows: list[dict]) -> np.ndarray:
        cat_mat = []
        for r in rows:
            row_cat = []
            for f in CAT_FEATURES:
                vec = [0.0] * len(vocab[f])
                if r["features"][f] in vocab[f]:
                    vec[vocab[f][r["features"][f]]] = 1.0
                row_cat.extend(vec)
            cat_mat.append(row_cat)
        cat_mat = np.array(cat_mat)

        num_mat = []
        for r in rows:
            row_num = [
                (float(r["features"][f]) - num_mean[f]) / (num_std[f] if num_std[f] > 1e-10 else 1.0)
                for f in NUM_FEATURES
            ]
            num_mat.append(row_num)
        num_mat = np.array(num_mat)

        return np.hstack([cat_mat, num_mat])

    X_train = encode_and_scale(train_rows)
    y_train = np.array([r["is_failure"] for r in train_rows])
    X_val = encode_and_scale(val_rows)
    y_val = np.array([r["is_failure"] for r in val_rows])
    X_test = encode_and_scale(test_rows)
    y_test = np.array([r["is_failure"] for r in test_rows])

    lr = LogisticRegression(class_weight="balanced", max_iter=2000, random_state=42, solver="lbfgs")
    lr.fit(X_train, y_train)

    for split_name, X, y in [
        ("TRAIN", X_train, y_train),
        ("VALIDATION", X_val, y_val),
        ("TEST_OOS", X_test, y_test),
    ]:
        y_prob = lr.predict_proba(X)[:, 1].tolist()
        y_pred = lr.predict(X).tolist()
        model_metrics[f"B6_LR_{split_name}"] = compute_full_metrics(y, y_pred, y_prob)
        print(f"  LR {split_name}: ROC={model_metrics[f'B6_LR_{split_name}']['roc_auc']:.4f}")

    # Print comparison tables
    print("\n" + "=" * 100)
    print("COMPARISON TABLE — TEST_OOS (the decision metric)")
    print("=" * 100)
    header = f"{'Model':<30} {'Acc':>7} {'BalAcc':>7} {'FailRec':>8} {'FailPrec':>9} {'FailF1':>7} {'LogLoss':>8} {'Brier':>7} {'ROC':>6} {'PR':>6}"
    print(header)
    print("-" * 100)

    baseline_keys = sorted(
        [k for k in model_metrics if k.startswith("B") and "_TEST_OOS" in k]
    )
    for key in baseline_keys:
        m = model_metrics[key]
        name = key.replace("_TEST_OOS", "")
        print(
            f"{name:<30} {m['accuracy']:>7.4f} {m['balanced_accuracy']:>7.4f} "
            f"{m['failure_recall']:>8.4f} {m['failure_precision']:>9.4f} "
            f"{m['failure_f1']:>7.4f} {m['log_loss']:>8.4f} {m['brier_score']:>7.4f} "
            f"{m['roc_auc']:>6.4f} {m['pr_auc']:>6.4f}"
        )

    m = model_metrics["TEST_OOS"]
    print(
        f"{'failure_risk_v1':<30} {m['accuracy']:>7.4f} {m['balanced_accuracy']:>7.4f} "
        f"{m['failure_recall']:>8.4f} {m['failure_precision']:>9.4f} "
        f"{m['failure_f1']:>7.4f} {m['log_loss']:>8.4f} {m['brier_score']:>7.4f} "
        f"{m['roc_auc']:>6.4f} {m['pr_auc']:>6.4f}"
    )

    print("\n" + "=" * 70)
    print("TRAIN vs VALIDATION vs TEST_OOS — failure_risk_v1")
    print("=" * 70)
    for split in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        m = model_metrics[split]
        print(
            f"{split}: Acc={m['accuracy']:.4f} BalAcc={m['balanced_accuracy']:.4f} "
            f"FailRec={m['failure_recall']:.4f} FailPrec={m['failure_precision']:.4f} "
            f"FailF1={m['failure_f1']:.4f} ROC={m['roc_auc']:.4f} "
            f"PR={m['pr_auc']:.4f} Brier={m['brier_score']:.4f} LogLoss={m['log_loss']:.4f}"
        )

    # v1.003 reference
    v1_003_ref: dict[str, Any] = {
        "TEST_OOS": {
            "n": 76,
            "n_failure": 26,
            "accuracy": 0.5132,
            "balanced_accuracy": 0.5158,
            "failure_recall": 0.2308,
            "failure_f1": 0.2609,
            "status": "REVIEW",
        }
    }

    print("\n" + "=" * 70)
    print("v1.003 vs failure_risk_v1 (TEST_OOS)")
    print("=" * 70)
    print(f"{'Metric':<25} {'v1.003':>10} {'failure_risk_v1':>15} {'Delta':>10}")
    print("-" * 50)
    for metric in ["accuracy", "balanced_accuracy", "failure_recall", "failure_f1"]:
        v1_val = v1_003_ref["TEST_OOS"][metric]
        v2_val = model_metrics["TEST_OOS"][metric]
        delta = v2_val - v1_val
        print(f"{metric:<25} {v1_val:>10.4f} {v2_val:>15.4f} {delta:>+10.4f}")

    print(
        f"{'roc_auc':<25} {'N/A':>10} {model_metrics['TEST_OOS']['roc_auc']:>15.4f}"
    )
    print(
        f"{'pr_auc':<25} {'N/A':>10} {model_metrics['TEST_OOS']['pr_auc']:>15.4f}"
    )
    print(
        f"{'brier_score':<25} {'N/A':>10} {model_metrics['TEST_OOS']['brier_score']:>15.4f}"
    )

    # Memorization analysis
    print("\n" + "=" * 70)
    print("MEMORIZATION / OVERFITTING ANALYSIS")
    print("=" * 70)
    for split in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        m = model_metrics[split]
        probs = preds[split]["predicted_probs"]
        arr = np.array(probs)
        very_high = int((arr > 0.9).sum())
        very_low = int((arr < 0.1).sum())
        print(
            f"{split}: mean={arr.mean():.4f} std={arr.std():.4f} "
            f"min={arr.min():.4f} max={arr.max():.4f} "
            f"P(p>0.9)={very_high}/{len(arr)} ({100*very_high/len(arr):.1f}%) "
            f"P(p<0.1)={very_low}/{len(arr)} ({100*very_low/len(arr):.1f}%)"
        )

    train_roc = model_metrics["TRAIN"]["roc_auc"]
    val_roc = model_metrics["VALIDATION"]["roc_auc"]
    test_roc = model_metrics["TEST_OOS"]["roc_auc"]
    print(f"\nROC-AUC progression: TRAIN={train_roc:.4f} -> VAL={val_roc:.4f} -> OOS={test_roc:.4f}")
    print(f"Overfit gap TRAIN->OOS: {train_roc - test_roc:.4f}")

    # Save comparison
    comparison: dict[str, Any] = {
        "failure_risk_v1": model_metrics,
        "baselines": {k: model_metrics[k] for k in baseline_keys},
        "v1_003_reference": v1_003_ref,
        "notes": {
            "v1_003_metrics_from": "PLAN_FAILURE_ANATOMY_LEARNING_V1.md (2026-09-15)",
            "v1_003_details": "accuracy=0.5132, balanced_accuracy=0.5158, failure_recall=0.2308, failure_F1=0.2609, status=REVIEW",
            "v1_003_roc_pr_not_reported": True,
        },
    }

    with open(MODEL_DIR / "comparison.json", "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, sort_keys=True)
    print(f"\nSaved comparison.json")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
