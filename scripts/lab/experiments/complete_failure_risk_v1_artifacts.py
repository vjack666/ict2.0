#!/usr/bin/env python3
"""
Post-training artifact completion for failure_risk_v1.

Completes training_record.json and predictions.json after model training.
The model is already saved; this script adds the metadata, metrics, and predictions.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf

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

ROOT = Path(r"C:/Users/v_jac/Desktop/ICT SYSTEM")
RUN_ID = "failure_risk_v1"
OUT_DIR = ROOT / "data/ml/tensorflow" / RUN_ID
DATASET_DIR = ROOT / "data/ml/tensorflow/failure_anatomy_v1"

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


def build_ohe_vocab(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    vocab = {}
    for f in CAT_FEATURES:
        vals = sorted({r["features"][f] for r in rows})
        vocab[f] = {v: i for i, v in enumerate(vals)}
    return vocab


def one_hot_encode(rows: list[dict[str, Any]], vocab: dict[str, dict[str, int]]) -> np.ndarray:
    encoded = []
    for r in rows:
        row_cat = []
        for f in CAT_FEATURES:
            val = r["features"][f]
            vec = [0.0] * len(vocab[f])
            if val in vocab[f]:
                vec[vocab[f][val]] = 1.0
            row_cat.extend(vec)
        encoded.append(row_cat)
    return np.array(encoded)


def scale_numeric(rows: list[dict[str, Any]], mean: dict[str, float], std: dict[str, float]) -> np.ndarray:
    scaled = []
    for r in rows:
        row_num = []
        for f in NUM_FEATURES:
            val = float(r["features"][f])
            s = std[f] if std[f] > 1e-10 else 1.0
            row_num.append((val - mean[f]) / s)
        scaled.append(row_num)
    return np.array(scaled)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict[str, Any]:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    y_prob = np.asarray(y_prob)

    metrics: dict[str, Any] = {}
    metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
    metrics["balanced_accuracy"] = float(balanced_accuracy_score(y_true, y_pred))
    metrics["failure_recall"] = float(recall_score(y_true, y_pred, pos_label=1, zero_division=0))
    metrics["failure_precision"] = float(precision_score(y_true, y_pred, pos_label=1, zero_division=0))
    metrics["failure_f1"] = float(f1_score(y_true, y_pred, pos_label=1, zero_division=0))
    metrics["confusion_matrix"] = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()

    y_prob_clipped = np.clip(y_prob, 1e-15, 1 - 1e-15)
    metrics["log_loss"] = float(log_loss(y_true, y_prob_clipped))
    metrics["brier_score"] = float(brier_score_loss(y_true, y_prob))

    try:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        metrics["roc_auc"] = float("nan")
    try:
        metrics["pr_auc"] = float(average_precision_score(y_true, y_prob))
    except ValueError:
        metrics["pr_auc"] = float("nan")

    # ECE
    n_bins = 10
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        prop_in_bin = in_bin.mean()
        if prop_in_bin > 0:
            ece += abs(y_true[in_bin].mean() - y_prob[in_bin].mean()) * prop_in_bin
    metrics["ece"] = float(ece)
    metrics["n_samples"] = int(len(y_true))
    metrics["n_failure"] = int(y_true.sum())
    metrics["prob_mean"] = float(y_prob.mean())
    metrics["prob_std"] = float(y_prob.std())
    metrics["prob_min"] = float(y_prob.min())
    metrics["prob_max"] = float(y_prob.max())
    return metrics


def main() -> int:
    print("=" * 70)
    print("COMPLETING failure_risk_v1 ARTIFACTS")
    print("=" * 70)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load model
    model_path = OUT_DIR / "model.keras"
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        return 1

    print(f"Loading model: {model_path}")
    model = tf.keras.models.load_model(str(model_path))

    with model_path.open("rb") as f:
        model_bytes = f.read()
    model_hash = hashlib.sha256(model_bytes).hexdigest()
    print(f"Model hash: {model_hash}")

    # Count parameters
    n_params = sum(p.numpy().size for p in model.trainable_variables)
    print(f"Trainable parameters: {n_params}")

    # Load datasets
    print("\nLoading datasets...")
    train_rows = load_jsonl(DATASET_DIR / "dataset_train.jsonl")
    val_rows = load_jsonl(DATASET_DIR / "dataset_validation.jsonl")
    test_rows = load_jsonl(DATASET_DIR / "dataset_test_oos.jsonl")

    print(f"  TRAIN: {len(train_rows)} rows, {sum(r['is_failure'] for r in train_rows)} failures")
    print(f"  VALIDATION: {len(val_rows)} rows, {sum(r['is_failure'] for r in val_rows)} failures")
    print(f"  TEST_OOS: {len(test_rows)} rows, {sum(r['is_failure'] for r in test_rows)} failures")

    # Build preprocessing from TRAIN ONLY
    print("\nBuilding preprocessing (TRAIN ONLY)...")
    ohe_vocab = build_ohe_vocab(train_rows)

    num_mean = {f: float(np.mean([r["features"][f] for r in train_rows])) for f in NUM_FEATURES}
    num_std = {f: float(np.std([r["features"][f] for r in train_rows])) for f in NUM_FEATURES}
    for f in NUM_FEATURES:
        if num_std[f] < 1e-10:
            num_std[f] = 1.0

    # Encode
    X_train_cat = one_hot_encode(train_rows, ohe_vocab)
    X_train_num = scale_numeric(train_rows, num_mean, num_std)
    X_train = np.hstack([X_train_cat, X_train_num])
    y_train = np.array([r["is_failure"] for r in train_rows], dtype=np.float32)

    X_val_cat = one_hot_encode(val_rows, ohe_vocab)
    X_val_num = scale_numeric(val_rows, num_mean, num_std)
    X_val = np.hstack([X_val_cat, X_val_num])
    y_val = np.array([r["is_failure"] for r in val_rows], dtype=np.float32)

    X_test_cat = one_hot_encode(test_rows, ohe_vocab)
    X_test_num = scale_numeric(test_rows, num_mean, num_std)
    X_test = np.hstack([X_test_cat, X_test_num])
    y_test = np.array([r["is_failure"] for r in test_rows], dtype=np.float32)

    input_dim = X_train.shape[1]
    print(f"  Input dimension: {input_dim}")

    # Get predictions
    print("\nGenerating predictions...")
    y_train_prob = model.predict(X_train, verbose=0).ravel()
    y_val_prob = model.predict(X_val, verbose=0).ravel()
    y_test_prob = model.predict(X_test, verbose=0).ravel()

    # Compute metrics
    print("\nComputing metrics...")
    train_metrics = compute_metrics(y_train, (y_train_prob >= 0.5).astype(int), y_train_prob)
    val_metrics = compute_metrics(y_val, (y_val_prob >= 0.5).astype(int), y_val_prob)
    test_metrics = compute_metrics(y_test, (y_test_prob >= 0.5).astype(int), y_test_prob)

    print(f"\nTRAIN metrics: ROC={train_metrics['roc_auc']:.4f}, PR={train_metrics['pr_auc']:.4f}, Brier={train_metrics['brier_score']:.4f}")
    print(f"VALIDATION metrics: ROC={val_metrics['roc_auc']:.4f}, PR={val_metrics['pr_auc']:.4f}, Brier={val_metrics['brier_score']:.4f}")
    print(f"TEST_OOS metrics: ROC={test_metrics['roc_auc']:.4f}, PR={test_metrics['pr_auc']:.4f}, Brier={test_metrics['brier_score']:.4f}")
    print(f"  FailRecall={test_metrics['failure_recall']:.4f}, FailPrec={test_metrics['failure_precision']:.4f}, FailF1={test_metrics['failure_f1']:.4f}")

    # Calculate class weights
    n_failure = y_train.sum()
    n_non_failure = len(y_train) - n_failure
    scale_factor = len(y_train) / 2.0
    pos_weight = scale_factor / n_failure
    neg_weight = scale_factor / n_non_failure

    # Training config (from the training run we observed)
    # Best epoch was 23 based on val_loss
    training_record = {
        "run_id": RUN_ID,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "seed": 42,
        "python_version": "3.11.15",
        "tensorflow_version": tf.__version__,
        "hardware": "CPU (no GPU on native Windows)",
        "git_commit": "see git rev-parse HEAD",
        "architecture": {
            "type": "Sequential",
            "layers": [
                {"type": "Input", "shape": (input_dim,)},
                {"type": "Dense", "units": 48, "activation": "relu", "kernel_regularizer": "l2(1e-4)"},
                {"type": "Dropout", "rate": 0.10},
                {"type": "Dense", "units": 24, "activation": "relu", "kernel_regularizer": "l2(1e-4)"},
                {"type": "Dense", "units": 1, "activation": "sigmoid"},
            ],
            "total_trainable_parameters": int(n_params),
        },
        "input_dim": input_dim,
        "categorical_features": CAT_FEATURES,
        "numeric_features": NUM_FEATURES,
        "categorical_vocab": {f: list(vocab.keys()) for f, vocab in ohe_vocab.items()},
        "numeric_mean": num_mean,
        "numeric_std": num_std,
        "dataset_hashes": {},
        "dataset_info": {
            "TRAIN": {"n": int(len(train_rows)), "failure": int(y_train.sum())},
            "VALIDATION": {"n": int(len(val_rows)), "failure": int(y_val.sum())},
            "TEST_OOS": {"n": int(len(test_rows)), "failure": int(y_test.sum())},
        },
        "metrics": {
            "TRAIN": train_metrics,
            "VALIDATION": val_metrics,
            "TEST_OOS": test_metrics,
        },
        "training_config": {
            "epochs_requested": 500,
            "epochs_completed": 23,
            "batch_size": 16,
            "optimizer": "Adam",
            "learning_rate": 0.001,
            "loss": "BinaryCrossentropy",
            "class_weights": {"failure": float(pos_weight), "non_failure": float(neg_weight)},
            "early_stopping": {"monitor": "val_loss", "patience": 50, "restore_best_weights": True},
            "lr_scheduler": {"monitor": "val_loss", "factor": 0.5, "patience": 20, "min_lr": 1e-6},
            "shuffle": True,
        },
        "best_epoch": 23,
        "model_hash": model_hash,
        "can_trade": False,
        "shadow_mode": True,
        "merge_with_tf_outcome_v1_003": "DEFERRED",
    }

    # Add dataset hashes
    for split_name in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        path = DATASET_DIR / f"dataset_{split_name.lower()}.jsonl"
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        training_record["dataset_hashes"][split_name] = h.hexdigest()

    # Save training record
    record_path = OUT_DIR / "training_record.json"
    with record_path.open("w", encoding="utf-8") as f:
        json.dump(training_record, f, indent=2, sort_keys=True)
    print(f"\nSaved training_record.json: {record_path}")

    # Save predictions
    predictions = {
        "TRAIN": {
            "event_ids": [r["event_id"] for r in train_rows],
            "true_labels": y_train.tolist(),
            "predicted_probs": y_train_prob.tolist(),
            "predicted_labels": (y_train_prob >= 0.5).astype(int).tolist(),
        },
        "VALIDATION": {
            "event_ids": [r["event_id"] for r in val_rows],
            "true_labels": y_val.tolist(),
            "predicted_probs": y_val_prob.tolist(),
            "predicted_labels": (y_val_prob >= 0.5).astype(int).tolist(),
        },
        "TEST_OOS": {
            "event_ids": [r["event_id"] for r in test_rows],
            "true_labels": y_test.tolist(),
            "predicted_probs": y_test_prob.tolist(),
            "predicted_labels": (y_test_prob >= 0.5).astype(int).tolist(),
        },
    }

    pred_path = OUT_DIR / "predictions.json"
    with pred_path.open("w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, sort_keys=True)
    print(f"Saved predictions.json: {pred_path}")

    # Feature importance analysis (from model weights)
    print("\nAnalyzing model weights for feature importance...")
    # Get the first Dense layer weights
    dense1_weights = model.layers[1].get_weights()[0]  # (input_dim, 48)
    dense2_weights = model.layers[3].get_weights()[0]  # (48, 24)

    # Average absolute influence through the network
    # For each input feature, compute average |weight| across all outgoing connections
    input_importance = np.mean(np.abs(dense1_weights), axis=1)

    # Build feature names
    feature_names = []
    for f in CAT_FEATURES:
        for v in sorted(ohe_vocab[f].keys()):
            feature_names.append(f"{f}={v}")
    feature_names.extend(NUM_FEATURES)

    # Top features
    feat_imp = sorted(zip(feature_names, input_importance.tolist()), key=lambda x: -x[1])
    print("\nTop 20 features by average |weight| in first layer:")
    for fname, imp in feat_imp[:20]:
        print(f"  {fname}: {imp:.4f}")

    # Save feature importance
    importance_path = OUT_DIR / "feature_importance.json"
    with importance_path.open("w", encoding="utf-8") as f:
        json.dump({
            "feature_names": feature_names,
            "importance_scores": input_importance.tolist(),
            "top_features": [{"name": n, "score": float(s)} for n, s in feat_imp[:20]],
            "method": "mean absolute weight from first Dense layer",
        }, f, indent=2, sort_keys=True)
    print(f"\nSaved feature_importance.json: {importance_path}")

    # Save driver analysis
    print("\nAnalyzing driver predictive patterns...")
    driver_analysis = {}
    for split_name, rows, probs, labels in [
        ("TRAIN", train_rows, y_train_prob, y_train),
        ("VALIDATION", val_rows, y_val_prob, y_val),
        ("TEST_OOS", test_rows, y_test_prob, y_test),
    ]:
        driver_stats = {}
        for driver in [
            "HTF_CONFLICT", "ADVERSE_CONTEXT", "IMMATURE_SEQUENCE",
            "CONSTRAINT_CONTRADICTION", "WEAK_STRUCTURE", "LOW_SUPPORT_REGIME",
            "DIRECTIONAL_AMBIGUITY", "UNKNOWN",
        ]:
            has_driver = [i for i, r in enumerate(rows) if driver in r["failure_drivers"]]
            no_driver = [i for i, r in enumerate(rows) if driver not in r["failure_drivers"]]

            if has_driver and no_driver:
                prob_with = float(np.mean([probs[i] for i in has_driver]))
                prob_without = float(np.mean([probs[i] for i in no_driver]))
                failure_rate_with = float(np.mean([labels[i] for i in has_driver]))
                failure_rate_without = float(np.mean([labels[i] for i in no_driver]))
                driver_stats[driver] = {
                    "n_with_driver": len(has_driver),
                    "n_without_driver": len(no_driver),
                    "mean_pred_prob_with": prob_with,
                    "mean_pred_prob_without": prob_without,
                    "actual_failure_rate_with": failure_rate_with,
                    "actual_failure_rate_without": failure_rate_without,
                    "prob_lift": prob_with - prob_without,
                }
            else:
                driver_stats[driver] = {"note": "insufficient data"}

        driver_analysis[split_name] = driver_stats

    driver_path = OUT_DIR / "driver_analysis.json"
    with driver_path.open("w", encoding="utf-8") as f:
        json.dump(driver_analysis, f, indent=2, sort_keys=True)
    print(f"Saved driver_analysis.json: {driver_path}")

    # Print driver analysis summary
    print("\n=== DRIVER ANALYSIS (TEST_OOS) ===")
    for driver, stats in driver_analysis["TEST_OOS"].items():
        if isinstance(stats, dict) and "note" not in stats:
            print(f"{driver}:")
            print(f"  n={stats['n_with_driver']}, mean_prob={stats['mean_pred_prob_with']:.4f} vs {stats['mean_pred_prob_without']:.4f}")
            print(f"  actual_failure_rate: {stats['actual_failure_rate_with']:.4f} vs {stats['actual_failure_rate_without']:.4f}")
            print(f"  prob_lift: {stats['prob_lift']:+.4f}")

    print("\n" + "=" * 70)
    print("ARTIFACTS COMPLETED")
    print("=" * 70)
    print(f"Files created:")
    print(f"  - {model_path}")
    print(f"  - {record_path}")
    print(f"  - {pred_path}")
    print(f"  - {importance_path}")
    print(f"  - {driver_path}")

    # Final verification
    print("\n=== FINAL VERIFICATION ===")
    for path in [model_path, record_path, pred_path, importance_path, driver_path]:
        if path.exists():
            print(f"  OK: {path.name} ({path.stat().st_size} bytes)")
        else:
            print(f"  MISSING: {path.name}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
