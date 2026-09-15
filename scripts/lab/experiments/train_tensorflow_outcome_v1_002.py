#!/usr/bin/env python3
"""
TensorFlow AI Outcome v1.002.

Continuation of Hermes' tf_outcome_v1_001 run. This runner does not overwrite
the previous run. It uses SEQ_CTX_01_CANONICAL_BOS + SEQ_CTX_01_LITE, records
preflight evidence, fixes idx_to_label, uses TRAIN-only encoders, and writes a
fail-closed diagnostic report.

This is diagnostic research only:
  shadow_mode=true
  can_trade=false
  no trading, no promotion
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import tensorflow as tf


ROOT = Path(r"C:/Users/v_jac/Desktop/ICT SYSTEM")
CORPUS_FILES = [
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl",
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_LITE.jsonl",
]
RUN_ID = "tf_outcome_v1_002"
OUT_DIR = ROOT / "data/ml/tensorflow" / RUN_ID
SEED = 20260915

LABEL_MAP = {"continuation": 0, "reversal": 1, "failure": 2}
IDX_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}
FEATURE_NAMES = [
    "sequence_direction",
    "d1_bias",
    "h1_alignment",
    "h4_location",
    "context_bucket",
    "sequence_depth",
]
SPLIT_MAP = {"DESIGN": "TRAIN", "VALIDATION": "VALIDATION", "HOLDOUT": "TEST_OOS"}


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


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row["_source_file"] = path.name
                rows.append(row)
    return rows


def load_corpus() -> list[dict]:
    rows: list[dict] = []
    for path in CORPUS_FILES:
        rows.extend(load_jsonl(path))
    rows.sort(key=lambda r: (r.get("event_time", ""), r.get("_source_file", ""), r.get("event_id", "")))
    return rows


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def preflight(rows: list[dict]) -> dict:
    checks: dict[str, dict] = {}

    checks["files_exist"] = {
        "status": "PASS" if all(path.exists() for path in CORPUS_FILES) else "FAIL",
        "files": [str(path) for path in CORPUS_FILES],
    }

    required_top = {"event_id", "event_time", "split", "label_end_6", "features_at_t", "can_trade"}
    missing_required = []
    can_trade_bad = 0
    label_in_features = 0
    unknown_label = 0
    split_bad = 0
    feature_missing = 0
    event_ids = set()
    duplicate_ids = 0
    by_source = Counter()
    by_split = Counter()
    by_label = Counter()
    by_split_label: dict[str, Counter] = defaultdict(Counter)
    times_by_split: dict[str, list[dt.datetime]] = defaultdict(list)

    for i, row in enumerate(rows):
        missing = sorted(required_top - set(row))
        if missing:
            missing_required.append({"index": i, "missing": missing})
        event_id = row.get("event_id")
        if event_id in event_ids:
            duplicate_ids += 1
        event_ids.add(event_id)

        if row.get("can_trade") is not False:
            can_trade_bad += 1
        if row.get("label_end_6") not in LABEL_MAP:
            unknown_label += 1
        if row.get("split") not in SPLIT_MAP:
            split_bad += 1

        features = row.get("features_at_t", {})
        if any(key.startswith("label") or key in {"target", "future_return", "future_pnl"} for key in features):
            label_in_features += 1

        context_inputs = features.get("context_inputs", {})
        needed = {"sequence_direction", "d1_bias", "h1_alignment", "h4_location"}
        if not needed.issubset(context_inputs) or "context_bucket" not in row or "sequence_depth" not in row:
            feature_missing += 1

        source = row.get("_source_file", "unknown")
        split = row.get("split", "unknown")
        label = row.get("label_end_6", "unknown")
        by_source[source] += 1
        by_split[split] += 1
        by_label[label] += 1
        by_split_label[split][label] += 1
        if row.get("event_time"):
            times_by_split[split].append(parse_time(row["event_time"]))

    split_order_ok = True
    split_ranges = {}
    for split, values in times_by_split.items():
        if values:
            split_ranges[split] = {
                "min": min(values).isoformat(),
                "max": max(values).isoformat(),
                "n": len(values),
            }
    if {"DESIGN", "VALIDATION"}.issubset(times_by_split):
        split_order_ok = split_order_ok and max(times_by_split["DESIGN"]) < min(times_by_split["VALIDATION"])
    if {"VALIDATION", "HOLDOUT"}.issubset(times_by_split):
        split_order_ok = split_order_ok and max(times_by_split["VALIDATION"]) < min(times_by_split["HOLDOUT"])

    checks["required_fields"] = {"status": "PASS" if not missing_required else "FAIL", "failures": missing_required[:20]}
    checks["event_id_unique"] = {"status": "PASS" if duplicate_ids == 0 else "FAIL", "duplicate_count": duplicate_ids}
    checks["can_trade_false"] = {"status": "PASS" if can_trade_bad == 0 else "FAIL", "bad_rows": can_trade_bad}
    checks["labels_known"] = {"status": "PASS" if unknown_label == 0 else "FAIL", "bad_rows": unknown_label}
    checks["splits_known"] = {"status": "PASS" if split_bad == 0 else "FAIL", "bad_rows": split_bad}
    checks["label_not_in_features"] = {"status": "PASS" if label_in_features == 0 else "FAIL", "bad_rows": label_in_features}
    checks["required_features_present"] = {"status": "PASS" if feature_missing == 0 else "FAIL", "bad_rows": feature_missing}
    checks["temporal_split_order"] = {"status": "PASS" if split_order_ok else "FAIL", "ranges": split_ranges}

    status = "PASS" if all(check["status"] == "PASS" for check in checks.values()) else "FAIL"
    return {
        "status": status,
        "run_id": RUN_ID,
        "n_rows": len(rows),
        "by_source": dict(by_source),
        "by_split": dict(by_split),
        "by_label": dict(by_label),
        "by_split_label": {split: dict(counter) for split, counter in by_split_label.items()},
        "corpus_files": [
            {"path": str(path), "sha256": sha256_path(path), "bytes": path.stat().st_size}
            for path in CORPUS_FILES
        ],
        "checks": checks,
        "note": "This preflight verifies the persisted PIT feature contract; it is not a producer replay FULL/PREFIX proof.",
    }


def fit_maps(train_rows: list[dict]) -> dict[str, dict]:
    values: dict[str, set] = {
        "d1_bias": set(),
        "h1_alignment": set(),
        "h4_location": set(),
        "context_bucket": set(),
    }
    for row in train_rows:
        ci = row["features_at_t"]["context_inputs"]
        values["d1_bias"].add(ci["d1_bias"])
        values["h1_alignment"].add(ci["h1_alignment"])
        values["h4_location"].add(ci["h4_location"])
        values["context_bucket"].add(row["context_bucket"])
    return {key: {value: i for i, value in enumerate(sorted(vals))} for key, vals in values.items()}


def encode_features(rows: list[dict], maps: dict[str, dict]) -> np.ndarray:
    encoded = []
    for row in rows:
        ci = row["features_at_t"]["context_inputs"]
        encoded.append(
            [
                float(ci["sequence_direction"]),
                float(maps["d1_bias"][ci["d1_bias"]]),
                float(maps["h1_alignment"][ci["h1_alignment"]]),
                float(maps["h4_location"][ci["h4_location"]]),
                float(maps["context_bucket"][row["context_bucket"]]),
                float(row["sequence_depth"]),
            ]
        )
    return np.array(encoded, dtype=np.float32)


def encode_labels(rows: list[dict]) -> np.ndarray:
    return np.array([LABEL_MAP[row["label_end_6"]] for row in rows], dtype=np.int32)


def majority_baseline(y_train: np.ndarray, y_test: np.ndarray) -> tuple[dict, np.ndarray]:
    majority = Counter(y_train.tolist()).most_common(1)[0][0]
    preds = np.full(len(y_test), majority, dtype=np.int32)
    metrics = evaluate(y_test, None, preds)
    metrics["baseline_type"] = "majority_class_from_TRAIN"
    metrics["majority_class_idx"] = int(majority)
    metrics["majority_class_label"] = IDX_TO_LABEL[int(majority)]
    return metrics, preds


def evaluate(y_true: np.ndarray, y_proba: np.ndarray | None, y_pred: np.ndarray) -> dict:
    from sklearn.metrics import classification_report, confusion_matrix, log_loss, precision_recall_fscore_support

    n_classes = len(LABEL_MAP)
    y_pred_oh = np.eye(n_classes)[y_pred] if y_proba is None else np.asarray(y_proba)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(n_classes)), zero_division=0
    )
    per_class = {}
    for idx in range(n_classes):
        per_class[IDX_TO_LABEL[idx]] = {
            "precision": float(precision[idx]),
            "recall": float(recall[idx]),
            "f1": float(f1[idx]),
            "support": int(np.sum(y_true == idx)),
        }
    recalls = [per_class[IDX_TO_LABEL[idx]]["recall"] for idx in range(n_classes)]
    return {
        "accuracy": float(np.mean(y_true == y_pred)),
        "balanced_accuracy": float(np.mean(recalls)),
        "per_class": per_class,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=list(range(n_classes))).tolist(),
        "log_loss": float(log_loss(y_true, y_pred_oh, labels=list(range(n_classes)))),
        "brier_score": float(np.mean(np.sum((y_pred_oh - np.eye(n_classes)[y_true]) ** 2, axis=1))),
        "classification_report": classification_report(
            y_true,
            y_pred,
            target_names=[IDX_TO_LABEL[i] for i in range(n_classes)],
            labels=list(range(n_classes)),
            zero_division=0,
        ),
    }


def build_model(input_dim: int) -> tf.keras.Model:
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(input_dim,)),
            tf.keras.layers.Dense(64, activation="relu"),
            tf.keras.layers.Dropout(0.10),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dense(3, activation="softmax"),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def class_weights(y_train: np.ndarray) -> dict[int, float]:
    counts = Counter(y_train.tolist())
    total = len(y_train)
    n_classes = len(LABEL_MAP)
    return {idx: float(total / (n_classes * counts[idx])) for idx in range(n_classes)}


def expected_calibration_error(y_true: np.ndarray, y_proba: np.ndarray, bins: int = 10) -> dict:
    pred = np.argmax(y_proba, axis=1)
    confidence = np.max(y_proba, axis=1)
    correct = (pred == y_true).astype(float)
    ece = 0.0
    bucket_details = []
    for i in range(bins):
        lo = i / bins
        hi = (i + 1) / bins
        mask = (confidence >= lo) & (confidence < hi if i < bins - 1 else confidence <= hi)
        if not np.any(mask):
            bucket_details.append({"bin": i, "n": 0, "confidence": None, "accuracy": None})
            continue
        bin_conf = float(np.mean(confidence[mask]))
        bin_acc = float(np.mean(correct[mask]))
        weight = float(np.mean(mask))
        ece += weight * abs(bin_acc - bin_conf)
        bucket_details.append({"bin": i, "n": int(np.sum(mask)), "confidence": bin_conf, "accuracy": bin_acc})
    return {"ece": float(ece), "bins": bucket_details}


def abstention_summary(y_true: np.ndarray, y_proba: np.ndarray) -> dict:
    pred = np.argmax(y_proba, axis=1)
    confidence = np.max(y_proba, axis=1)
    output = {}
    for threshold in [0.5, 0.6, 0.7, 0.8]:
        mask = confidence >= threshold
        output[str(threshold)] = {
            "coverage": float(np.mean(mask)),
            "n": int(np.sum(mask)),
            "accuracy": float(np.mean(pred[mask] == y_true[mask])) if np.any(mask) else None,
        }
    return output


def drift_by_year(test_rows: list[dict], y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    buckets: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(test_rows):
        buckets[parse_time(row["event_time"]).strftime("%Y")].append(i)
    out = {}
    for year, idxs in sorted(buckets.items()):
        idx = np.array(idxs)
        out[year] = {
            "n": len(idxs),
            "accuracy": float(np.mean(y_true[idx] == y_pred[idx])),
            "label_counts": dict(Counter(IDX_TO_LABEL[int(y_true[i])] for i in idx)),
        }
    return out


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    train = [row for row in rows if row["split"] == "DESIGN"]
    val = [row for row in rows if row["split"] == "VALIDATION"]
    test = [row for row in rows if row["split"] == "HOLDOUT"]
    return train, val, test


def write_json(name: str, data: dict) -> None:
    (OUT_DIR / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> int:
    tf.random.set_seed(SEED)
    np.random.seed(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_corpus()
    preflight_report = preflight(rows)
    write_json("preflight.json", preflight_report)
    if preflight_report["status"] != "PASS":
        write_json(
            "audit.json",
            {
                "status": "BLOCKED_PREFLIGHT",
                "can_trade": False,
                "shadow_mode": True,
                "reason": "Preflight failed; training not executed.",
            },
        )
        return 2

    train_rows, val_rows, test_rows = split_rows(rows)
    maps = fit_maps(train_rows)
    x_train = encode_features(train_rows, maps)
    y_train = encode_labels(train_rows)
    x_val = encode_features(val_rows, maps)
    y_val = encode_labels(val_rows)
    x_test = encode_features(test_rows, maps)
    y_test = encode_labels(test_rows)

    feature_schema = {
        "feature_maps": maps,
        "features": FEATURE_NAMES,
        "input_dim": int(x_train.shape[1]),
        "label_map": LABEL_MAP,
        "idx_to_label": {str(idx): label for idx, label in IDX_TO_LABEL.items()},
        "fit_scope": "TRAIN/DESIGN only",
    }
    write_json("feature_schema.json", feature_schema)

    distribution = {
        "by_split": preflight_report["by_split"],
        "by_label": preflight_report["by_label"],
        "by_split_label": preflight_report["by_split_label"],
    }
    write_json("distribucion_clases.json", distribution)

    baseline_metrics, baseline_pred = majority_baseline(y_train, y_test)
    write_json("baseline.json", baseline_metrics)

    model = build_model(int(x_train.shape[1]))
    weights = class_weights(y_train)
    early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val),
        epochs=50,
        batch_size=256,
        callbacks=[early_stop],
        class_weight=weights,
        verbose=1,
    )
    model.save(OUT_DIR / "model.keras")

    val_proba = model.predict(x_val, verbose=0)
    val_pred = np.argmax(val_proba, axis=1)
    test_proba = model.predict(x_test, verbose=0)
    test_pred = np.argmax(test_proba, axis=1)

    val_metrics = evaluate(y_val, val_proba, val_pred)
    test_metrics = evaluate(y_test, test_proba, test_pred)
    write_json("metrics_validation.json", val_metrics)
    write_json("metrics_test_oos.json", test_metrics)
    write_json("calibration_test_oos.json", expected_calibration_error(y_test, test_proba))
    write_json("abstention_test_oos.json", abstention_summary(y_test, test_proba))
    write_json("drift_test_oos_by_year.json", drift_by_year(test_rows, y_test, test_pred))

    with (OUT_DIR / "predictions_test_oos.jsonl").open("w", encoding="utf-8") as f:
        for i, row in enumerate(test_rows):
            pred = {
                "event_id": row["event_id"],
                "event_time": row["event_time"],
                "source_file": row["_source_file"],
                "true_label": IDX_TO_LABEL[int(y_test[i])],
                "pred_label": IDX_TO_LABEL[int(test_pred[i])],
                "prob_continuation": float(test_proba[i][0]),
                "prob_reversal": float(test_proba[i][1]),
                "prob_failure": float(test_proba[i][2]),
                "confidence": float(np.max(test_proba[i])),
                "correct": bool(y_test[i] == test_pred[i]),
                "split": row["split"],
                "context_bucket": row["context_bucket"],
                "sequence_depth": row["sequence_depth"],
            }
            f.write(json.dumps(pred) + "\n")

    env = {
        "python": sys.version.split()[0],
        "tensorflow": tf.__version__,
        "numpy": np.__version__,
        "git_commit": git("git rev-parse HEAD"),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    write_json("environment.json", env)

    source_manifest = {
        "run_id": RUN_ID,
        "dataset_id": "SEQ_CTX_01_CANONICAL_BOS_PLUS_LITE",
        "corpus_files": preflight_report["corpus_files"],
        "generator_commit_expected": "33fb73d5303b322d35ca16d05700f3ae8540584a",
        "split": {
            "TRAIN": "DESIGN (2006-2015)",
            "VALIDATION": "VALIDATION (2016-2020)",
            "TEST_OOS": "HOLDOUT (2021-2025)",
        },
        "n_train": len(train_rows),
        "n_validation": len(val_rows),
        "n_test_oos": len(test_rows),
        "preflight_status": preflight_report["status"],
    }
    write_json("source_manifest.json", source_manifest)

    training_config = {
        "seed": SEED,
        "epochs_requested": 50,
        "epochs_actual": len(history.history["loss"]),
        "batch_size": 256,
        "optimizer": "Adam",
        "learning_rate": 0.001,
        "early_stopping_patience": 8,
        "class_weight": weights,
        "architecture": "Dense(64)+Dropout(0.10)+Dense(32)+Dense(3,softmax)",
        "loss": "sparse_categorical_crossentropy",
        "git_commit": env["git_commit"],
    }
    write_json("training_config.json", training_config)

    failure = test_metrics["per_class"]["failure"]
    status = "REVIEW"
    reasons = []
    if failure["recall"] <= 0:
        status = "BLOCKED_FAILURE_COLLAPSE"
        reasons.append("failure recall is 0 on TEST_OOS")
    if test_metrics["per_class"]["failure"]["support"] < 30:
        reasons.append("failure TEST_OOS support is below 30")
    if len(test_rows) < 30:
        reasons.append("TEST_OOS total support is below 30")
    if preflight_report["status"] != "PASS":
        status = "BLOCKED_PREFLIGHT"
        reasons.append("preflight failed")

    audit = {
        "status": status,
        "run_id": RUN_ID,
        "can_trade": False,
        "shadow_mode": True,
        "features_fitted_only_on_train": True,
        "oos_untouched_during_training": True,
        "class_weight_used": True,
        "final_epochs": len(history.history["loss"]),
        "train_loss_final": float(history.history["loss"][-1]),
        "val_loss_final": float(history.history["val_loss"][-1]),
        "train_acc_final": float(history.history["accuracy"][-1]),
        "val_acc_final": float(history.history["val_accuracy"][-1]),
        "baseline_accuracy": baseline_metrics["accuracy"],
        "model_accuracy": test_metrics["accuracy"],
        "baseline_log_loss": baseline_metrics["log_loss"],
        "model_log_loss": test_metrics["log_loss"],
        "reasons": reasons,
        "note": "Diagnostic TensorFlow training only; not TRAINING_ELIGIBLE, not edge, not trading authorization.",
    }
    write_json("audit.json", audit)

    report = [
        "# TensorFlow AI Outcome v1.002 Final Report",
        "",
        f"**Run:** `{RUN_ID}`",
        f"**Status:** `{status}`",
        "**Scope:** diagnostic only, `can_trade=false`, `shadow_mode=true`.",
        "",
        "## Data",
        f"- TRAIN: {len(train_rows)}",
        f"- VALIDATION: {len(val_rows)}",
        f"- TEST_OOS: {len(test_rows)}",
        f"- Sources: {', '.join(path.name for path in CORPUS_FILES)}",
        "",
        "## Metrics",
        f"- Baseline OOS accuracy: {baseline_metrics['accuracy']:.4f}",
        f"- TensorFlow OOS accuracy: {test_metrics['accuracy']:.4f}",
        f"- TensorFlow OOS log_loss: {test_metrics['log_loss']:.4f}",
        f"- TensorFlow OOS Brier: {test_metrics['brier_score']:.4f}",
        f"- Failure recall: {failure['recall']:.4f}",
        "",
        "## Verdict",
        "- This run completes the TensorFlow training workflow mechanically.",
        "- It does not authorize production, trading, or promotion.",
        "- Remaining blockers are listed in `audit.json`.",
    ]
    (OUT_DIR / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
