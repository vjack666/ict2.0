#!/usr/bin/env python3
"""
TensorFlow AI Outcome v1.003.

Richer neural run over the persisted SEQ_CTX_01 data already on disk.
Uses TRAIN-only feature vocabularies, sequence-stage indicators, constraints,
structure mode, and HTF context layers. HOLDOUT is evaluated only after model
selection by VALIDATION loss.

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
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import tensorflow as tf


ROOT = Path(__file__).resolve().parents[3]  # raíz del repo (3 niveles desde scripts/lab/experiments/).parent  # raíz del repo (scripts/lab/experiments/ → 3 niveles arriba)  # raíz del repo (3 niveles desde scripts/lab/experiments/).parent  # raíz del repo (scripts/lab/experiments/ → 3 niveles arriba)
RUN_ID = "tf_outcome_v1_003"
OUT_DIR = ROOT / "data/ml/tensorflow" / RUN_ID
CORPUS_FILES = [
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl",
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_LITE.jsonl",
]
LABEL = "label_end_6"
LABEL_MAP = {"continuation": 0, "reversal": 1, "failure": 2}
IDX_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}
SEED = 20260916

CATEGORICAL_FEATURES = [
    ("structure_mode", lambda r: r.get("structure_mode", "UNKNOWN")),
    ("context_bucket", lambda r: r.get("context_bucket", "UNKNOWN")),
    ("d1_bias", lambda r: r["features_at_t"]["context_inputs"].get("d1_bias", "UNKNOWN")),
    ("h1_alignment", lambda r: r["features_at_t"]["context_inputs"].get("h1_alignment", "UNKNOWN")),
    ("h4_location", lambda r: r["features_at_t"]["context_inputs"].get("h4_location", "UNKNOWN")),
    ("direction_hint", lambda r: r["features_at_t"]["constraints"].get("direction_hint", "UNKNOWN")),
    ("h1_bias", lambda r: r["features_at_t"]["context_layers"].get("H1", {}).get("bias", "UNKNOWN")),
    ("h4_bias", lambda r: r["features_at_t"]["context_layers"].get("H4", {}).get("bias", "UNKNOWN")),
]
NUMERIC_FEATURES = [
    ("sequence_direction", lambda r: float(r["features_at_t"]["context_inputs"].get("sequence_direction", 0))),
    ("sequence_depth", lambda r: float(r.get("sequence_depth", 0))),
    ("allow_long", lambda r: 1.0 if r["features_at_t"]["constraints"].get("allow_long") else 0.0),
    ("allow_short", lambda r: 1.0 if r["features_at_t"]["constraints"].get("allow_short") else 0.0),
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


def load_rows() -> list[dict]:
    rows = []
    for path in CORPUS_FILES:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    row["_source_file"] = path.name
                    rows.append(row)
    rows.sort(key=lambda r: (r["event_time"], r["_source_file"], r["event_id"]))
    return rows


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    return (
        [r for r in rows if r["split"] == "DESIGN"],
        [r for r in rows if r["split"] == "VALIDATION"],
        [r for r in rows if r["split"] == "HOLDOUT"],
    )


def build_schema(train: list[dict]) -> dict:
    category_maps = {}
    for name, getter in CATEGORICAL_FEATURES:
        values = sorted({str(getter(row)) for row in train} | {"UNKNOWN"})
        category_maps[name] = {value: i for i, value in enumerate(values)}
    stage_values = sorted({stage for row in train for stage in row["features_at_t"].get("sequence", [])})
    return {
        "category_maps": category_maps,
        "sequence_stages": stage_values,
        "numeric_features": [name for name, _ in NUMERIC_FEATURES],
        "categorical_features": [name for name, _ in CATEGORICAL_FEATURES],
        "label_map": LABEL_MAP,
        "idx_to_label": {str(i): label for i, label in IDX_TO_LABEL.items()},
        "fit_scope": "TRAIN/DESIGN only",
    }


def encode(rows: list[dict], schema: dict) -> np.ndarray:
    matrix = []
    for row in rows:
        vec = []
        for _, getter in NUMERIC_FEATURES:
            vec.append(float(getter(row)))
        for name, getter in CATEGORICAL_FEATURES:
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


def labels(rows: list[dict]) -> np.ndarray:
    return np.asarray([LABEL_MAP[row[LABEL]] for row in rows], dtype=np.int32)


def evaluate(y_true: np.ndarray, probs: np.ndarray, pred: np.ndarray) -> dict:
    from sklearn.metrics import classification_report, confusion_matrix, log_loss, precision_recall_fscore_support

    classes = list(range(len(LABEL_MAP)))
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, pred, labels=classes, zero_division=0)
    per_class = {
        IDX_TO_LABEL[i]: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(np.sum(y_true == i)),
        }
        for i in classes
    }
    return {
        "accuracy": float(np.mean(y_true == pred)),
        "balanced_accuracy": float(np.mean([per_class[IDX_TO_LABEL[i]]["recall"] for i in classes])),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(y_true, pred, labels=classes).tolist(),
        "log_loss": float(log_loss(y_true, probs, labels=classes)),
        "brier_score": float(np.mean(np.sum((probs - np.eye(len(classes))[y_true]) ** 2, axis=1))),
        "classification_report": classification_report(
            y_true, pred, labels=classes, target_names=[IDX_TO_LABEL[i] for i in classes], zero_division=0
        ),
    }


def baseline(y_train: np.ndarray, y_test: np.ndarray) -> dict:
    majority = Counter(y_train.tolist()).most_common(1)[0][0]
    pred = np.full(len(y_test), majority, dtype=np.int32)
    probs = np.eye(3)[pred]
    out = evaluate(y_test, probs, pred)
    out["baseline_type"] = "majority_class_from_TRAIN"
    out["majority_class_idx"] = int(majority)
    out["majority_class_label"] = IDX_TO_LABEL[int(majority)]
    return out


def class_weights(y: np.ndarray) -> dict[int, float]:
    counts = Counter(y.tolist())
    total = len(y)
    return {i: float(total / (3 * counts[i])) for i in range(3)}


def build_model(input_dim: int, seed: int) -> tf.keras.Model:
    tf.random.set_seed(seed)
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(input_dim,)),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dense(96, activation="relu"),
            tf.keras.layers.Dropout(0.20),
            tf.keras.layers.Dense(48, activation="relu"),
            tf.keras.layers.Dropout(0.10),
            tf.keras.layers.Dense(3, activation="softmax"),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.0008),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def ece(y_true: np.ndarray, probs: np.ndarray, bins: int = 10) -> dict:
    pred = np.argmax(probs, axis=1)
    conf = np.max(probs, axis=1)
    correct = (pred == y_true).astype(float)
    value = 0.0
    details = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        mask = (conf >= lo) & (conf < hi if i < bins - 1 else conf <= hi)
        if not np.any(mask):
            details.append({"bin": i, "n": 0, "confidence": None, "accuracy": None})
            continue
        c = float(np.mean(conf[mask]))
        a = float(np.mean(correct[mask]))
        value += float(np.mean(mask)) * abs(c - a)
        details.append({"bin": i, "n": int(np.sum(mask)), "confidence": c, "accuracy": a})
    return {"ece": float(value), "bins": details}


def abstention(y_true: np.ndarray, probs: np.ndarray) -> dict:
    pred = np.argmax(probs, axis=1)
    conf = np.max(probs, axis=1)
    out = {}
    for threshold in [0.45, 0.50, 0.55, 0.60, 0.70]:
        mask = conf >= threshold
        out[str(threshold)] = {
            "n": int(np.sum(mask)),
            "coverage": float(np.mean(mask)),
            "accuracy": float(np.mean(pred[mask] == y_true[mask])) if np.any(mask) else None,
        }
    return out


def drift(rows: list[dict], y_true: np.ndarray, pred: np.ndarray) -> dict:
    by_year = defaultdict(list)
    for i, row in enumerate(rows):
        year = row["event_time"][:4]
        by_year[year].append(i)
    return {
        year: {
            "n": len(idxs),
            "accuracy": float(np.mean(y_true[idxs] == pred[idxs])),
            "label_counts": dict(Counter(IDX_TO_LABEL[int(y_true[i])] for i in idxs)),
        }
        for year, idxs in sorted(by_year.items())
    }


def write_json(name: str, payload: dict) -> None:
    (OUT_DIR / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    np.random.seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    train, val, test = split_rows(rows)
    schema = build_schema(train)

    x_train, x_val, x_test = encode(train, schema), encode(val, schema), encode(test, schema)
    y_train, y_val, y_test = labels(train), labels(val), labels(test)
    weights = class_weights(y_train)
    model = build_model(x_train.shape[1], SEED)
    early = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=12, restore_best_weights=True)
    hist = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        class_weight=weights,
        epochs=80,
        batch_size=64,
        callbacks=[early],
        verbose=1,
    )

    val_probs = model.predict(x_val, verbose=0)
    val_pred = np.argmax(val_probs, axis=1)
    test_probs = model.predict(x_test, verbose=0)
    test_pred = np.argmax(test_probs, axis=1)

    base = baseline(y_train, y_test)
    val_metrics = evaluate(y_val, val_probs, val_pred)
    test_metrics = evaluate(y_test, test_probs, test_pred)

    model.save(OUT_DIR / "model.keras")
    write_json("feature_schema.json", schema)
    write_json("baseline.json", base)
    write_json("metrics_validation.json", val_metrics)
    write_json("metrics_test_oos.json", test_metrics)
    write_json("calibration_test_oos.json", ece(y_test, test_probs))
    write_json("abstention_test_oos.json", abstention(y_test, test_probs))
    write_json("drift_test_oos_by_year.json", drift(test, y_test, test_pred))

    with (OUT_DIR / "predictions_test_oos.jsonl").open("w", encoding="utf-8") as f:
        for i, row in enumerate(test):
            f.write(
                json.dumps(
                    {
                        "event_id": row["event_id"],
                        "event_time": row["event_time"],
                        "source_file": row["_source_file"],
                        "true_label": IDX_TO_LABEL[int(y_test[i])],
                        "pred_label": IDX_TO_LABEL[int(test_pred[i])],
                        "prob_continuation": float(test_probs[i][0]),
                        "prob_reversal": float(test_probs[i][1]),
                        "prob_failure": float(test_probs[i][2]),
                        "confidence": float(np.max(test_probs[i])),
                        "correct": bool(y_test[i] == test_pred[i]),
                    }
                )
                + "\n"
            )

    source_manifest = {
        "run_id": RUN_ID,
        "dataset_id": "SEQ_CTX_01_CANONICAL_BOS_PLUS_LITE",
        "target": LABEL,
        "corpus_files": [
            {"path": str(path), "sha256": sha256_path(path), "bytes": path.stat().st_size}
            for path in CORPUS_FILES
        ],
        "n_train": len(train),
        "n_validation": len(val),
        "n_test_oos": len(test),
        "git_commit": git("git rev-parse HEAD"),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    write_json("source_manifest.json", source_manifest)

    training_config = {
        "seed": SEED,
        "epochs_requested": 80,
        "epochs_actual": len(hist.history["loss"]),
        "batch_size": 64,
        "optimizer": "Adam",
        "learning_rate": 0.0008,
        "class_weight": weights,
        "architecture": "BatchNorm+Dense(96)+Dropout(.20)+Dense(48)+Dropout(.10)+Softmax",
        "feature_count": int(x_train.shape[1]),
        "features_fit_scope": "TRAIN/DESIGN only",
    }
    write_json("training_config.json", training_config)
    write_json(
        "environment.json",
        {
            "python": sys.version.split()[0],
            "tensorflow": tf.__version__,
            "numpy": np.__version__,
            "git_commit": source_manifest["git_commit"],
        },
    )

    failure = test_metrics["per_class"]["failure"]
    reasons = []
    status = "REVIEW"
    if failure["recall"] == 0:
        status = "BLOCKED_FAILURE_COLLAPSE"
        reasons.append("failure recall is 0")
    if failure["support"] < 30:
        reasons.append("failure TEST_OOS support is below 30")
    if test_metrics["accuracy"] <= base["accuracy"]:
        reasons.append("model accuracy does not improve baseline")

    audit = {
        "status": status,
        "run_id": RUN_ID,
        "can_trade": False,
        "shadow_mode": True,
        "features_fitted_only_on_train": True,
        "oos_untouched_during_training": True,
        "final_epochs": len(hist.history["loss"]),
        "baseline_accuracy": base["accuracy"],
        "model_accuracy": test_metrics["accuracy"],
        "baseline_log_loss": base["log_loss"],
        "model_log_loss": test_metrics["log_loss"],
        "failure_recall": failure["recall"],
        "failure_support": failure["support"],
        "reasons": reasons,
        "note": "Diagnostic neural training only; not edge, not TRAINING_ELIGIBLE, not trading authorization.",
    }
    write_json("audit.json", audit)
    (OUT_DIR / "report.md").write_text(
        "\n".join(
            [
                "# TensorFlow AI Outcome v1.003 Neural Run",
                "",
                f"**Status:** `{status}`",
                f"**OOS accuracy:** {test_metrics['accuracy']:.4f}",
                f"**OOS log_loss:** {test_metrics['log_loss']:.4f}",
                f"**Failure recall:** {failure['recall']:.4f}",
                f"**Failure support:** {failure['support']}",
                "",
                "Diagnostic only. `can_trade=false`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
