#!/usr/bin/env python3
"""
Train failure_risk_v1 — binary failure risk model for ICT SYSTEM.

Diagnostic research only:
  can_trade=false
  shadow_mode=true
  no production, no orders, no promotion

Reference: PLAN_FAILURE_ANATOMY_LEARNING_V1.md
           FAILURE_TAXONOMY_V1.md
           CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np

# Reproducibility
SEED = 42
np.random.seed(SEED)
os.environ["PYTHONHASHSEED"] = str(SEED)

import tensorflow as tf
tf.random.set_seed(SEED)
# Ensure deterministic ops where possible
tf.config.experimental.enable_op_determinism()

from sklearn.preprocessing import StandardScaler, OneHotEncoder
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

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "failure_risk_v1"
OUT_DIR = ROOT / "data/ml/tensorflow" / RUN_ID
DATASET_DIR = ROOT / "data/ml/tensorflow/failure_anatomy_v1"
SCRIPT_PATH = ROOT / "scripts/lab/experiments" / f"train_{RUN_ID}.py"

# Feature config
CAT_FEATURES = [
    "structure_mode",
    "context_bucket",
    "d1_bias",
    "h1_bias",
    "h1_alignment",
    "h4_bias",
    "h4_location",
    "direction_hint",
]
NUM_FEATURES = [
    "sequence_direction",
    "sequence_depth",
    "allow_long",
    "allow_short",
    "regime_train_support",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_datasets() -> dict[str, list[dict[str, Any]]]:
    return {
        "TRAIN": load_jsonl(DATASET_DIR / "dataset_train.jsonl"),
        "VALIDATION": load_jsonl(DATASET_DIR / "dataset_validation.jsonl"),
        "TEST_OOS": load_jsonl(DATASET_DIR / "dataset_test_oos.jsonl"),
    }


def build_ohe_vocab(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    vocab = {}
    for f in CAT_FEATURES:
        vals = sorted({r["features"][f] for r in rows})
        vocab[f] = {v: i for i, v in enumerate(vals)}
    return vocab


def one_hot_encode(
    rows: list[dict[str, Any]], vocab: dict[str, dict[str, int]]
) -> np.ndarray:
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


def scale_numeric(
    rows: list[dict[str, Any]],
    mean: dict[str, float],
    std: dict[str, float],
) -> np.ndarray:
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

    # ECE (Expected Calibration Error)
    n_bins = 10
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        in_bin = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        prop_in_bin = in_bin.mean()
        if prop_in_bin > 0:
            avg_confidence = y_prob[in_bin].mean()
            avg_accuracy = y_true[in_bin].mean()
            ece += abs(avg_accuracy - avg_confidence) * prop_in_bin
    metrics["ece"] = float(ece)
    metrics["n_samples"] = int(len(y_true))
    metrics["n_failure"] = int(y_true.sum())

    return metrics


def build_model(input_dim: int) -> tf.keras.Model:
    """Build the recommended architecture from PLAN_FAILURE_ANATOMY_LEARNING_V1.md.

    Input: features causales disponibles en decision_time
    Dense(48) + ReLU
    Dropout(0.10)
    Dense(24) + ReLU
    Dense(1) + Sigmoid

    Conservative for small dataset: TRAIN n=120, failure=25
    """
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),
        tf.keras.layers.Dense(48, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(1e-4)),
        tf.keras.layers.Dropout(0.10),
        tf.keras.layers.Dense(24, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(1e-4)),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ])
    return model


def count_trainable_params(model: tf.keras.Model) -> int:
    return sum(p.numpy().size for p in model.trainable_variables)


def main() -> int:
    print(f"=" * 70)
    print(f"TRAINING failure_risk_v1")
    print(f"SEED: {SEED}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"TensorFlow: {tf.__version__}")
    print(f"=" * 70)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    datasets = load_datasets()
    train_rows = datasets["TRAIN"]
    val_rows = datasets["VALIDATION"]
    test_rows = datasets["TEST_OOS"]

    print(f"\nDataset loaded:")
    print(f"  TRAIN: {len(train_rows)} rows, {sum(r['is_failure'] for r in train_rows)} failures")
    print(f"  VALIDATION: {len(val_rows)} rows, {sum(r['is_failure'] for r in val_rows)} failures")
    print(f"  TEST_OOS: {len(test_rows)} rows, {sum(r['is_failure'] for r in test_rows)} failures")

    # Verify dataset hashes match materialization
    dataset_hashes = {}
    for split_name in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        path = DATASET_DIR / f"dataset_{split_name.lower()}.jsonl"
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        dataset_hashes[split_name] = h.hexdigest()

    # Expected hashes from materialization
    expected_hashes = {
        "TRAIN": "f34cc94cb50be5652ede901ba18e9a9c519834b8717be0750906bb51cf708863",
        "VALIDATION": "58e7ea4cc88b772c5734bb77c6096aec6545f46bec6aa5fbd281c9d76604b3ad",
        "TEST_OOS": "68e6b1e7a1792d93c6fe49ba49fbf113589d54a3c15c5d4f02ba90b5e3d11695",
    }

    print("\nDataset hash verification:")
    for split_name in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        match = dataset_hashes[split_name] == expected_hashes[split_name]
        status = "MATCH" if match else "MISMATCH"
        print(f"  {split_name}: {status}")
        if not match:
            print(f"    Expected: {expected_hashes[split_name]}")
            print(f"    Got:      {dataset_hashes[split_name]}")
            return 1

    # Build preprocessing from TRAIN ONLY
    print("\nBuilding preprocessing (TRAIN ONLY):")
    ohe_vocab = build_ohe_vocab(train_rows)
    print(f"  Categorical features: {len(CAT_FEATURES)}")
    print(f"  Numeric features: {len(NUM_FEATURES)}")

    cat_dims = [len(vocab) for vocab in ohe_vocab.values()]
    total_cat_dim = sum(cat_dims)
    print(f"  One-hot dimensions: {cat_dims} → total {total_cat_dim}")

    num_mean = {f: float(np.mean([r["features"][f] for r in train_rows])) for f in NUM_FEATURES}
    num_std = {f: float(np.std([r["features"][f] for r in train_rows])) for f in NUM_FEATURES}
    for f in NUM_FEATURES:
        if num_std[f] < 1e-10:
            num_std[f] = 1.0

    print(f"  Numeric means: {num_mean}")
    print(f"  Numeric stds: {num_std}")

    # Encode all splits
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
    print(f"\nFeature matrix dimensions: {input_dim}")
    print(f"  TRAIN: {X_train.shape}")
    print(f"  VALIDATION: {X_val.shape}")
    print(f"  TEST_OOS: {X_test.shape}")

    # Class weights for imbalanced data
    n_failure = y_train.sum()
    n_non_failure = len(y_train) - n_failure
    scale_factor = len(y_train) / 2.0
    pos_weight = scale_factor / n_failure
    neg_weight = scale_factor / n_non_failure
    print(f"\nClass weights (balanced):")
    print(f"  failure (positive): {pos_weight:.4f}")
    print(f"  non-failure (negative): {neg_weight:.4f}")

    sample_weights_train = np.where(y_train == 1, pos_weight, neg_weight)

    # Build model
    print(f"\nBuilding failure_risk_v1 architecture:")
    model = build_model(input_dim)
    model.summary()

    n_params = count_trainable_params(model)
    print(f"\nTotal trainable parameters: {n_params}")
    print(f"Parameter-to-sample ratio: {n_params / len(train_rows):.2f}")

    # Compile
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)
    loss_fn = tf.keras.losses.BinaryCrossentropy()

    model.compile(
        optimizer=optimizer,
        loss=loss_fn,
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="binary_accuracy"),
            tf.keras.metrics.AUC(name="auc", curve="ROC"),
            tf.keras.metrics.AUC(name="pr_auc", curve="PR"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.Precision(name="precision"),
        ],
    )

    # Callbacks
    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=50,
        restore_best_weights=True,
        verbose=1,
    )

    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=20,
        min_lr=1e-6,
        verbose=1,
    )

    # Training
    print(f"\nTraining failure_risk_v1:")
    print(f"  Epochs: 500 (with early stopping, patience=50)")
    print(f"  Batch size: 16")
    print(f"  Optimizer: Adam lr=0.001")
    print(f"  Loss: BinaryCrossentropy")
    print(f"  Class weights: balanced (pos={pos_weight:.4f}, neg={neg_weight:.4f})")
    print(f"  Early stopping: monitor=val_loss, patience=50, restore_best_weights=True")
    print(f"  LR reduction: factor=0.5, patience=20, min_lr=1e-6")

    history = model.fit(
        X_train,
        y_train,
        sample_weight=sample_weights_train,
        validation_data=(X_val, y_val),
        epochs=500,
        batch_size=16,
        shuffle=True,
        callbacks=[early_stopping, reduce_lr],
        verbose=1,
    )

    # Best epoch from early stopping
    best_epoch = int(np.argmin(history.history["val_loss"])) + 1
    print(f"\nBest epoch: {best_epoch} (val_loss={min(history.history['val_loss']):.6f})")

    # Evaluation
    print(f"\n{'=' * 70}")
    print(f"EVALUATION failure_risk_v1")
    print(f"{'=' * 70}")

    all_metrics: dict[str, dict[str, Any]] = {}

    for name, X, y in [
        ("TRAIN", X_train, y_train),
        ("VALIDATION", X_val, y_val),
        ("TEST_OOS", X_test, y_test),
    ]:
        y_prob = model.predict(X, verbose=0).ravel()
        y_pred = (y_prob >= 0.5).astype(int)
        metrics = compute_metrics(y, y_pred, y_prob)
        all_metrics[name] = metrics

        print(f"\n{name} (n={metrics['n_samples']}, failures={metrics['n_failure']}):")
        print(f"  accuracy:          {metrics['accuracy']:.4f}")
        print(f"  balanced_accuracy: {metrics['balanced_accuracy']:.4f}")
        print(f"  failure_recall:    {metrics['failure_recall']:.4f}")
        print(f"  failure_precision: {metrics['failure_precision']:.4f}")
        print(f"  failure_f1:        {metrics['failure_f1']:.4f}")
        print(f"  log_loss:          {metrics['log_loss']:.4f}")
        print(f"  brier_score:       {metrics['brier_score']:.4f}")
        print(f"  roc_auc:           {metrics['roc_auc']:.4f}")
        print(f"  pr_auc:            {metrics['pr_auc']:.4f}")
        print(f"  ece:               {metrics['ece']:.4f}")
        print(f"  confusion_matrix:  {metrics['confusion_matrix']}")

        # Probability distribution stats
        print(f"  prob mean:         {y_prob.mean():.4f}")
        print(f"  prob std:          {y_prob.std():.4f}")
        print(f"  prob min:          {y_prob.min():.4f}")
        print(f"  prob max:          {y_prob.max():.4f}")

    # Save model
    model_path = OUT_DIR / "model.keras"
    model.save(str(model_path))
    print(f"\nModel saved: {model_path}")

    # Save model hash
    with model_path.open("rb") as f:
        model_bytes = f.read()
    model_hash = hashlib.sha256(model_bytes).hexdigest()
    print(f"Model hash (SHA256): {model_hash[:16]}...")

    # Save training artifacts
    training_record = {
        "run_id": RUN_ID,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "seed": SEED,
        "python_version": sys.version.split()[0],
        "tensorflow_version": tf.__version__,
        "hardware": "CPU (no GPU on native Windows)",
        "architecture": {
            "type": "Sequential",
            "layers": [
                {"type": "Dense", "units": 48, "activation": "relu", "kernel_regularizer": "l2(1e-4)"},
                {"type": "Dropout", "rate": 0.10},
                {"type": "Dense", "units": 24, "activation": "relu", "kernel_regularizer": "l2(1e-4)"},
                {"type": "Dense", "units": 1, "activation": "sigmoid"},
            ],
        },
        "total_trainable_parameters": n_params,
        "parameter_to_sample_ratio": round(n_params / len(train_rows), 2),
        "input_dim": input_dim,
        "categorical_features": CAT_FEATURES,
        "numeric_features": NUM_FEATURES,
        "categorical_vocab": {f: list(vocab.keys()) for f, vocab in ohe_vocab.items()},
        "numeric_mean": num_mean,
        "numeric_std": num_std,
        "training": {
            "epochs_requested": 500,
            "epochs_completed": best_epoch,
            "batch_size": 16,
            "optimizer": "Adam",
            "learning_rate": 0.001,
            "loss": "BinaryCrossentropy",
            "class_weights": {"failure": float(pos_weight), "non_failure": float(neg_weight)},
            "early_stopping": {"monitor": "val_loss", "patience": 50, "restore_best_weights": True},
            "lr_scheduler": {"monitor": "val_loss", "factor": 0.5, "patience": 20, "min_lr": 1e-6},
        },
        "dataset_hashes": dataset_hashes,
        "dataset_info": {
            "TRAIN": {"n": len(train_rows), "failure": int(y_train.sum())},
            "VALIDATION": {"n": len(val_rows), "failure": int(y_val.sum())},
            "TEST_OOS": {"n": len(test_rows), "failure": int(y_test.sum())},
        },
        "metrics": all_metrics,
        "training_history": {
            "train_loss": [float(x) for x in history.history["loss"]],
            "val_loss": [float(x) for x in history.history["val_loss"]],
            "train_auc": [float(x) for x in history.history["auc"]],
            "val_auc": [float(x) for x in history.history["auc_1"]],
            "train_pr_auc": [float(x) for x in history.history["pr_auc"]],
            "val_pr_auc": [float(x) for x in history.history["pr_auc_1"]],
        },
        "best_epoch": best_epoch,
        "model_hash": model_hash,
        "can_trade": False,
        "shadow_mode": True,
        "merge_with_tf_outcome_v1_003": "DEFERRED",
    }

    record_path = OUT_DIR / "training_record.json"
    with record_path.open("w", encoding="utf-8") as f:
        json.dump(training_record, f, indent=2, sort_keys=True)
    print(f"Training record saved: {record_path}")

    # Save predictions for all splits
    predictions = {}
    for name, X, y in [
        ("TRAIN", X_train, y_train),
        ("VALIDATION", X_val, y_val),
        ("TEST_OOS", X_test, y_test),
    ]:
        y_prob = model.predict(X, verbose=0).ravel()
        predictions[name] = {
            "event_ids": [r["event_id"] for r in (train_rows if name == "TRAIN" else val_rows if name == "VALIDATION" else test_rows)],
            "true_labels": y.tolist(),
            "predicted_probs": y_prob.tolist(),
            "predicted_labels": ((y_prob >= 0.5).astype(int)).tolist(),
        }

    pred_path = OUT_DIR / "predictions.json"
    with pred_path.open("w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, sort_keys=True)
    print(f"Predictions saved: {pred_path}")

    # Summary
    print(f"\n{'=' * 70}")
    print(f"SUMMARY failure_risk_v1")
    print(f"{'=' * 70}")
    print(f"Model: {model_path}")
    print(f"Model hash: {model_hash}")
    print(f"Parameters: {n_params}")
    print(f"Best epoch: {best_epoch}")
    print(f"\nTEST_OOS performance:")
    test_m = all_metrics["TEST_OOS"]
    print(f"  ROC-AUC:    {test_m['roc_auc']:.4f}")
    print(f"  PR-AUC:     {test_m['pr_auc']:.4f}")
    print(f"  Brier:      {test_m['brier_score']:.4f}")
    print(f"  LogLoss:    {test_m['log_loss']:.4f}")
    print(f"  BalAcc:     {test_m['balanced_accuracy']:.4f}")
    print(f"  FailRecall: {test_m['failure_recall']:.4f}")
    print(f"  FailPrec:   {test_m['failure_precision']:.4f}")
    print(f"  FailF1:     {test_m['failure_f1']:.4f}")
    print(f"  ECE:        {test_m['ece']:.4f}")

    print(f"\n{'=' * 70}")
    print(f"TRAINING COMPLETED — failure_risk_v1")
    print(f"{'=' * 70}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
