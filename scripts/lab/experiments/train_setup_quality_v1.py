#!/usr/bin/env python3
"""Train setup_quality_v1 from SETUP_GRAMMAR_DATASET_V1.

Research only:
  can_trade=false
  shadow_mode=true
  no production, no orders, no promotion
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, log_loss


SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)
os.environ["PYTHONHASHSEED"] = str(SEED)

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "setup_quality_v1"
DATASET_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1"
OUT_DIR = ROOT / "data/ml/tensorflow" / RUN_ID
REPORT_DIR = ROOT / "reports/audits/experiments/ai"
REPORT_MD = REPORT_DIR / "setup_quality_v1_training.md"
REPORT_JSON = REPORT_DIR / "setup_quality_v1_training.json"

CAT_FEATURES = [
    "symbol",
    "timeframe",
    "structure_mode",
    "context_bucket",
    "direction_hint",
    "d1_bias",
    "h1_alignment",
    "h4_location",
    "exec_tf_status",
    "exec_tf_source_family",
]
NUM_FEATURES = [
    "direction",
    "sequence_depth",
    "allow_long",
    "allow_short",
    "exec_tf_window_bars",
]
SEQ_FEATURES = [
    "LIQUIDITY_POOL",
    "SWEEP",
    "DISPLACEMENT",
    "STRUCTURE",
    "OB",
    "FVG",
    "RETEST",
]


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_splits() -> dict[str, list[dict[str, Any]]]:
    return {
        "TRAIN": load_jsonl(DATASET_DIR / "dataset_train.jsonl"),
        "VALIDATION": load_jsonl(DATASET_DIR / "dataset_validation.jsonl"),
        "TEST_OOS": load_jsonl(DATASET_DIR / "dataset_test_oos.jsonl"),
    }


def source_family(source: str | None) -> str:
    text = str(source or "")
    if "2006_2010" in text:
        return "DUKASCOPY_2006_2010_MONTHLY"
    if "2011_2020" in text:
        return "DUKASCOPY_2011_2020_MONTHLY"
    if "2021_2025" in text:
        return "DUKASCOPY_2021_2025_MONTHLY"
    if text.endswith("EURUSD_M15_2006_2015.parquet"):
        return "PARQUET_DESIGN_2006_2015"
    if text.endswith("EURUSD_M15.parquet"):
        return "PARQUET_RECENT"
    return "LOCAL_M15_SOURCE"


def extract_features(row: dict[str, Any]) -> dict[str, Any]:
    raw_features = row.get("features_at_t") or {}
    constraints = raw_features.get("constraints") or {}
    context = raw_features.get("context_inputs") or {}
    sequence = {str(item).upper() for item in raw_features.get("sequence") or []}
    exec_evidence = row.get("exec_tf_evidence") or {}
    features: dict[str, Any] = {
        "symbol": row.get("symbol", "MISSING"),
        "timeframe": row.get("timeframe", "MISSING"),
        "structure_mode": row.get("structure_mode", "MISSING"),
        "context_bucket": row.get("context_bucket", "MISSING"),
        "direction_hint": constraints.get("direction_hint", "MISSING"),
        "d1_bias": context.get("d1_bias", "MISSING"),
        "h1_alignment": context.get("h1_alignment", "MISSING"),
        "h4_location": context.get("h4_location", "MISSING"),
        "exec_tf_status": exec_evidence.get("status", "MISSING"),
        "exec_tf_source_family": source_family(exec_evidence.get("source")),
        "direction": int(row.get("features_at_t", {}).get("context_inputs", {}).get("sequence_direction", row.get("direction", 0)) or 0),
        "sequence_depth": int(row.get("sequence_depth", 0) or 0),
        "allow_long": 1.0 if constraints.get("allow_long") is True else 0.0,
        "allow_short": 1.0 if constraints.get("allow_short") is True else 0.0,
        "exec_tf_window_bars": int(exec_evidence.get("window_bars", 0) or 0),
    }
    for item in SEQ_FEATURES:
        features[f"seq_{item}"] = 1.0 if item in sequence else 0.0
    return features


def build_vocab(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    vocab: dict[str, dict[str, int]] = {}
    for feature in CAT_FEATURES:
        values = sorted({str(extract_features(row)[feature]) for row in rows})
        vocab[feature] = {value: index for index, value in enumerate(values)}
    return vocab


def encode_x(rows: list[dict[str, Any]], vocab: dict[str, dict[str, int]], means: dict[str, float], stds: dict[str, float]) -> np.ndarray:
    encoded: list[list[float]] = []
    for row in rows:
        features = extract_features(row)
        values: list[float] = []
        for feature in CAT_FEATURES:
            one_hot = [0.0] * len(vocab[feature])
            value = str(features[feature])
            if value in vocab[feature]:
                one_hot[vocab[feature][value]] = 1.0
            values.extend(one_hot)
        for feature in NUM_FEATURES:
            std = stds[feature] if stds[feature] > 1e-10 else 1.0
            values.append((float(features[feature]) - means[feature]) / std)
        values.extend(float(features[f"seq_{item}"]) for item in SEQ_FEATURES)
        encoded.append(values)
    return np.asarray(encoded, dtype=np.float32)


def build_label_vocab(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    values = sorted({str(row["grammar_labels"][key]) for row in rows})
    return {value: index for index, value in enumerate(values)}


def encode_label(rows: list[dict[str, Any]], vocab: dict[str, int], key: str) -> np.ndarray:
    labels = []
    for row in rows:
        value = str(row["grammar_labels"][key])
        if value not in vocab:
            raise ValueError(f"Unseen {key} label outside TRAIN vocab: {value}")
        labels.append(vocab[value])
    return np.asarray(labels, dtype=np.int64)


def build_model(input_dim: int, setup_classes: int, weak_classes: int) -> tf.keras.Model:
    inputs = tf.keras.Input(shape=(input_dim,), name="causal_features")
    x = tf.keras.layers.Dense(64, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(1e-4))(inputs)
    x = tf.keras.layers.Dropout(0.10)(x)
    x = tf.keras.layers.Dense(32, activation="relu", kernel_regularizer=tf.keras.regularizers.l2(1e-4))(x)
    setup_out = tf.keras.layers.Dense(setup_classes, activation="softmax", name="setup_decision")(x)
    weak_out = tf.keras.layers.Dense(weak_classes, activation="softmax", name="weak_link")(x)
    failure_out = tf.keras.layers.Dense(1, activation="sigmoid", name="failure_risk")(x)
    return tf.keras.Model(inputs=inputs, outputs=[setup_out, weak_out, failure_out], name=RUN_ID)


def multiclass_metrics(y_true: np.ndarray, prob: np.ndarray) -> dict[str, Any]:
    pred = prob.argmax(axis=1)
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "macro_f1": float(f1_score(y_true, pred, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y_true, np.clip(prob, 1e-15, 1 - 1e-15), labels=list(range(prob.shape[1])))),
        "support": dict(Counter(int(item) for item in y_true)),
    }


def binary_metrics(y_true: np.ndarray, prob: np.ndarray) -> dict[str, Any]:
    pred = (prob >= 0.5).astype(int)
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "macro_f1": float(f1_score(y_true, pred, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y_true, np.clip(prob, 1e-15, 1 - 1e-15), labels=[0, 1])),
        "support": dict(Counter(int(item) for item in y_true)),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    splits = load_splits()
    train_rows = splits["TRAIN"]
    val_rows = splits["VALIDATION"]
    test_rows = splits["TEST_OOS"]

    if any(row.get("diagnostics") for rows in splits.values() for row in rows):
        raise SystemExit("Dataset contains blocking diagnostics; refusing setup_quality_v1 training.")

    train_features = [extract_features(row) for row in train_rows]
    vocab = build_vocab(train_rows)
    means = {feature: float(np.mean([item[feature] for item in train_features])) for feature in NUM_FEATURES}
    stds = {feature: float(np.std([item[feature] for item in train_features]) or 1.0) for feature in NUM_FEATURES}

    x_train = encode_x(train_rows, vocab, means, stds)
    x_val = encode_x(val_rows, vocab, means, stds)
    x_test = encode_x(test_rows, vocab, means, stds)

    setup_vocab = build_label_vocab(train_rows, "setup_decision")
    weak_vocab = build_label_vocab(train_rows, "weak_link")
    y_setup_train = encode_label(train_rows, setup_vocab, "setup_decision")
    y_setup_val = encode_label(val_rows, setup_vocab, "setup_decision")
    y_setup_test = encode_label(test_rows, setup_vocab, "setup_decision")
    y_weak_train = encode_label(train_rows, weak_vocab, "weak_link")
    y_weak_val = encode_label(val_rows, weak_vocab, "weak_link")
    y_weak_test = encode_label(test_rows, weak_vocab, "weak_link")
    y_fail_train = np.asarray([row["target"]["is_failure"] for row in train_rows], dtype=np.float32)
    y_fail_val = np.asarray([row["target"]["is_failure"] for row in val_rows], dtype=np.float32)
    y_fail_test = np.asarray([row["target"]["is_failure"] for row in test_rows], dtype=np.float32)

    model = build_model(x_train.shape[1], len(setup_vocab), len(weak_vocab))
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=8e-4),
        loss={
            "setup_decision": "sparse_categorical_crossentropy",
            "weak_link": "sparse_categorical_crossentropy",
            "failure_risk": "binary_crossentropy",
        },
        loss_weights={"setup_decision": 1.0, "weak_link": 0.8, "failure_risk": 0.5},
        metrics={
            "setup_decision": ["accuracy"],
            "weak_link": ["accuracy"],
            "failure_risk": ["binary_accuracy"],
        },
    )
    history = model.fit(
        x_train,
        {"setup_decision": y_setup_train, "weak_link": y_weak_train, "failure_risk": y_fail_train},
        validation_data=(x_val, {"setup_decision": y_setup_val, "weak_link": y_weak_val, "failure_risk": y_fail_val}),
        epochs=300,
        batch_size=16,
        callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=30, restore_best_weights=True)],
        verbose=1,
    )

    model_path = OUT_DIR / "model.keras"
    model.save(model_path)
    predictions: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    for name, rows, x, y_setup, y_weak, y_fail in [
        ("TRAIN", train_rows, x_train, y_setup_train, y_weak_train, y_fail_train),
        ("VALIDATION", val_rows, x_val, y_setup_val, y_weak_val, y_fail_val),
        ("TEST_OOS", test_rows, x_test, y_setup_test, y_weak_test, y_fail_test),
    ]:
        setup_prob, weak_prob, failure_prob = model.predict(x, verbose=0)
        failure_prob = failure_prob.ravel()
        metrics[name] = {
            "setup_decision": multiclass_metrics(y_setup, setup_prob),
            "weak_link": multiclass_metrics(y_weak, weak_prob),
            "failure_risk": binary_metrics(y_fail, failure_prob),
            "n": len(rows),
        }
        predictions[name] = [
            {
                "event_id": row["event_id"],
                "setup_decision_prob": setup_prob[index].round(6).tolist(),
                "weak_link_prob": weak_prob[index].round(6).tolist(),
                "failure_risk": round(float(failure_prob[index]), 6),
            }
            for index, row in enumerate(rows)
        ]

    dataset_hashes = {
        split: sha256_path(DATASET_DIR / f"dataset_{split.lower()}.jsonl")
        for split in ["TRAIN", "VALIDATION", "TEST_OOS"]
    }
    record = {
        "run_id": RUN_ID,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "REVIEW",
        "can_trade": False,
        "shadow_mode": True,
        "python_version": sys.version.split()[0],
        "tensorflow_version": tf.__version__,
        "seed": SEED,
        "input_dim": int(x_train.shape[1]),
        "epochs_completed": len(history.history["loss"]),
        "best_val_loss": float(min(history.history["val_loss"])),
        "model_sha256": sha256_path(model_path),
        "dataset_hashes": dataset_hashes,
        "feature_config": {
            "categorical": CAT_FEATURES,
            "numeric": NUM_FEATURES,
            "sequence_flags": SEQ_FEATURES,
            "categorical_vocab": {key: list(value.keys()) for key, value in vocab.items()},
            "numeric_mean": means,
            "numeric_std": stds,
        },
        "label_vocab": {
            "setup_decision": {key: int(value) for key, value in setup_vocab.items()},
            "weak_link": {key: int(value) for key, value in weak_vocab.items()},
        },
        "metrics": metrics,
    }
    (OUT_DIR / "training_record.json").write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "predictions.json").write_text(json.dumps(predictions, indent=2, sort_keys=True), encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# setup_quality_v1 Training",
        "",
        "**Estado:** `REVIEW`",
        "**Trading:** `can_trade=false`, `shadow_mode=true`",
        "",
        "## Resultado",
        "",
        f"- TensorFlow: `{tf.__version__}`",
        f"- Input dim: `{x_train.shape[1]}`",
        f"- Epochs completados: `{len(history.history['loss'])}`",
        f"- Best val_loss: `{min(history.history['val_loss']):.6f}`",
        f"- Modelo: `{model_path.relative_to(ROOT)}`",
        f"- Modelo sha256: `{record['model_sha256']}`",
        "",
        "## Metricas",
        "",
    ]
    for split, split_metrics in metrics.items():
        lines.append(f"### {split}")
        lines.append(f"- setup_decision accuracy: `{split_metrics['setup_decision']['accuracy']:.4f}`; balanced_accuracy: `{split_metrics['setup_decision']['balanced_accuracy']:.4f}`")
        lines.append(f"- weak_link accuracy: `{split_metrics['weak_link']['accuracy']:.4f}`; balanced_accuracy: `{split_metrics['weak_link']['balanced_accuracy']:.4f}`")
        lines.append(f"- failure_risk accuracy: `{split_metrics['failure_risk']['accuracy']:.4f}`; balanced_accuracy: `{split_metrics['failure_risk']['balanced_accuracy']:.4f}`")
        lines.append("")
    lines.extend([
        "## Lectura",
        "",
        "Primera red multi-head entrenada sobre gramatica de setup sin aceptar `UNKNOWN`. Estado `REVIEW`: sirve para shadow diagnostics, no para operar ni modificar el motor.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": "REVIEW", "metrics": metrics, "model": str(model_path)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
