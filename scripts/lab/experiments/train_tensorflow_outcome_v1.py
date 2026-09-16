"""
train_tensorflow_outcome_v1.py — Runner TensorFlow para AI_OUTCOME_CLASSIFIER_V1.

Contrato: docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md
Plan: docs/planificacion/PLAN_ENTRENAMIENTO_TENSORFLOW_HERMES_V1.md
Corpus: data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl

Target: label_end_6 (continuation / reversal / failure)
Features: direction, sequence_depth, context_bucket, h1_alignment, d1_bias, h4_location
Split: DESIGN=train, VALIDATION=validation, HOLDOUT=test_oos
"""

from __future__ import annotations
import os, sys, json, hashlib, datetime, numpy as np, tensorflow as tf
from pathlib import Path
from collections import Counter

# Reproducibilidad
SEED = 20260915
tf.random.set_seed(SEED)
np.random.seed(SEED)

# Paths
BASE = Path(r"C:/Users/v_jac/Desktop/ICT SYSTEM")
CORPUS_F = BASE / "data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl"
OUT_F = BASE / "data/ml/tensorflow/tf_outcome_v1_001"
OUT_F.mkdir(parents=True, exist_ok=True)

# Feature encoding maps (desde TRAIN solamente)
D1_BIAS_MAP = {"BULLISH": 0, "BEARISH": 1, "MIXED": 2}
H1_ALIGNMENT_MAP = {"NEUTRAL": 0, "ALIGNED": 1, "AGAINST": 2}
H4_LOCATION_MAP = {"DISCOUNT": 0, "EQUILIBRIUM": 1, "PREMIUM": 2}
CONTEXT_BUCKET_MAP = {"NEUTRAL": 0, "ALIGNED": 1, "AGAINST": 2}
LABEL_MAP = {"continuation": 0, "reversal": 1, "failure": 2}
IDX_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}

def sha256_path(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def load_corpus(path):
    rows = []
    with open(path, "r") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows

def encode_features(rows, fit_maps=None):
    """Convierte features_at_t a vector numerico. fit_maps=None => se fittea sobre este conjunto (solo para TRAIN)."""
    if fit_maps is None:
        fit_maps = {
            "d1_bias": D1_BIAS_MAP.copy(),
            "h1_alignment": H1_ALIGNMENT_MAP.copy(),
            "h4_location": H4_LOCATION_MAP.copy(),
            "context_bucket": CONTEXT_BUCKET_MAP.copy(),
        }
    X = []
    for r in rows:
        feat = r["features_at_t"]
        ci = feat["context_inputs"]
        vec = [
            ci["sequence_direction"],  # -1 o 1
            fit_maps["d1_bias"][ci["d1_bias"]],
            fit_maps["h1_alignment"][ci["h1_alignment"]],
            fit_maps["h4_location"][ci["h4_location"]],
            fit_maps["context_bucket"][r["context_bucket"]],
            r["sequence_depth"],  # 4-7
        ]
        X.append(vec)
    return np.array(X, dtype=np.float32), fit_maps

def encode_labels(rows):
    y = np.array([LABEL_MAP[r["label_end_6"]] for r in rows], dtype=np.int32)
    return y

def build_model(input_dim):
    """Arquitectura v1: Dense(64) + Dropout(0.10) + Dense(32) + Dense(3) softmax."""
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.10),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(3, activation="softmax"),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model

def majority_baseline(y_train, y_test):
    """Baseline: siempre predice la clase mayoritaria de TRAIN."""
    counts = Counter(y_train)
    majority_class = counts.most_common(1)[0][0]
    n = len(y_test)
    correct = sum(1 for yt in y_test if yt == majority_class)
    acc = correct / n
    preds = np.full(n, majority_class, dtype=np.int32)
    return {"accuracy": acc, "preds": preds, "majority_class": IDX_TO_LABEL[majority_class]}

def evaluate(y_true, y_pred_proba, y_pred_class):
    """Calcular metricas completas."""
    from sklearn.metrics import (confusion_matrix, precision_recall_fscore_support,
                                  log_loss, brier_score_loss, classification_report)
    n_classes = 3
    # One-hot para log_loss y brier
    y_true_oh = np.eye(n_classes)[y_true]
    # Si no hay probabilidades suaves, usar one-hot duro de la clase predicha
    if y_pred_proba is None:
        y_pred_oh = np.eye(n_classes)[y_pred_class]
    else:
        y_pred_oh = np.array(y_pred_proba)
        # Validar que no haya NaN
        if np.any(np.isnan(y_pred_oh)):
            raise ValueError("Probabilidades contienen NaN")
    
    acc = np.mean(y_true == y_pred_class)
    balanced_acc = np.mean([
        np.mean(y_pred_class[y_true == c] == c) for c in range(n_classes)
    ])
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred_class, labels=[0,1,2], zero_division=0)
    cm = confusion_matrix(y_true, y_pred_class, labels=[0,1,2])
    logloss = log_loss(y_true_oh, y_pred_oh)
    # Brier score por clase (multinomial)
    brier = np.mean(np.sum((y_pred_oh - y_true_oh) ** 2, axis=1))
    
    report = classification_report(y_true, y_pred_class, target_names=["continuation","reversal","failure"],
                                  labels=[0,1,2], zero_division=0)
    
    return {
        "accuracy": float(acc),
        "balanced_accuracy": float(balanced_acc),
        "per_class": {
            IDX_TO_LABEL[c]: {
                "precision": float(prec[c]),
                "recall": float(rec[c]),
                "f1": float(f1[c]),
                "support": int(np.sum(y_true == c)),
            }
            for c in range(n_classes)
        },
        "confusion_matrix": cm.tolist(),
        "log_loss": float(logloss),
        "brier_score": float(brier),
        "classification_report": report,
    }

def main():
    print(f"=== TensorFlow AI Outcome Classifier v1 ===")
    print(f"Fecha: {datetime.datetime.utcnow().isoformat()}")
    print(f"Seed: {SEED}")
    print(f"TF version: {tf.__version__}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Corpus: {CORPUS_F}")
    print(f"Corpus SHA256: {sha256_path(CORPUS_F)[:16]}...")
    print()
    
    # Cargar corpus
    all_rows = load_corpus(CORPUS_F)
    print(f"Total observaciones: {len(all_rows)}")
    
    # Separar por split
    train_rows = [r for r in all_rows if r["split"] == "DESIGN"]
    val_rows = [r for r in all_rows if r["split"] == "VALIDATION"]
    test_rows = [r for r in all_rows if r["split"] == "HOLDOUT"]
    
    print(f"  TRAIN (DESIGN): {len(train_rows)}")
    print(f"  VALIDATION: {len(val_rows)}")
    print(f"  TEST/OOS (HOLDOUT): {len(test_rows)}")
    print()
    
    # Encodings: fittai maps SOLO con TRAIN
    X_train, feat_maps = encode_features(train_rows)
    y_train = encode_labels(train_rows)
    X_val, _ = encode_features(val_rows, fit_maps=feat_maps)
    y_val = encode_labels(val_rows)
    X_test, _ = encode_features(test_rows, fit_maps=feat_maps)
    y_test = encode_labels(test_rows)
    
    print(f"Features usadas (contractuales): direction, sequence_depth, context_bucket, h1_alignment, d1_bias, h4_location")
    print(f"Dimension de entrada: {X_train.shape[1]}")
    print()
    print("Distribucion TRAIN:")
    for label, idx in LABEL_MAP.items():
        n = np.sum(y_train == idx)
        print(f"  {label}: {n}")
    print()
    print("Distribucion VALIDATION:")
    for label, idx in LABEL_MAP.items():
        n = np.sum(y_val == idx)
        print(f"  {label}: {n}")
    print()
    print("Distribucion TEST/OOS:")
    for label, idx in LABEL_MAP.items():
        n = np.sum(y_test == idx)
        print(f"  {label}: {n}")
    print()
    
    # Guardar feature_maps (congelados desde TRAIN)
    feature_schema = {
        "feature_maps": {
            k: {str(vk): vi for vk, vi in vm.items()}
            for k, vm in feat_maps.items()
        },
        "features": ["sequence_direction", "d1_bias", "h1_alignment", "h4_location", "context_bucket", "sequence_depth"],
        "input_dim": int(X_train.shape[1]),
        "label_map": LABEL_MAP,
        "idx_to_label": {str(v): k for k, v in IDX_TO_LABEL.items()},
    }
    json.dump(feature_schema, open(OUT_F / "feature_schema.json", "w"), indent=2)
    
    # === BASELINE REAL ===
    print("=== BASELINE REAL (majority class from TRAIN) ===")
    baseline = majority_baseline(y_train, y_test)
    print(f"  Clase mayoritaria TRAIN: {baseline['majority_class']}")
    print(f"  Accuracy OOS: {baseline['accuracy']:.4f}")
    baseline_metrics = evaluate(y_test, None, baseline["preds"])
    print(f"  Balanced accuracy: {baseline_metrics['balanced_accuracy']:.4f}")
    print(f"  Log-loss: {baseline_metrics['log_loss']:.4f}")
    print(f"  Brier: {baseline_metrics['brier_score']:.4f}")
    print()
    
    # === ENTRENAMIENTO ===
    print("=== ENTRENAMIENTO TENSORFLOW ===")
    model = build_model(input_dim=X_train.shape[1])
    model.summary()
    print()
    
    early_stop = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=8, restore_best_weights=True
    )
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=50,
        batch_size=256,
        callbacks=[early_stop],
        verbose=1,
    )
    
    # Guardar modelo
    model.save(OUT_F / "model.keras")
    print(f"Modelo guardado: {OUT_F / 'model.keras'}")
    
    # Guardar config
    training_config = {
        "seed": SEED,
        "epochs_requested": 50,
        "epochs_actual": len(history.history["loss"]),
        "batch_size": 256,
        "optimizer": "Adam",
        "learning_rate": 0.001,
        "early_stopping_patience": 8,
        "architecture": "Dense(64)+Dropout(0.10)+Dense(32)+Dense(3,softmax)",
        "loss": "sparse_categorical_crossentropy",
        "git_commit": subprocess_check("git rev-parse HEAD")[:12],
    }
    json.dump(training_config, open(OUT_F / "training_config.json", "w"), indent=2)
    
    # === EVALUACION VALIDATION ===
    print()
    print("=== EVALUACION VALIDATION ===")
    val_proba = model.predict(X_val, verbose=0)
    val_pred = np.argmax(val_proba, axis=1)
    val_metrics = evaluate(y_val, val_proba, val_pred)
    print(f"  Accuracy: {val_metrics['accuracy']:.4f}")
    print(f"  Balanced accuracy: {val_metrics['balanced_accuracy']:.4f}")
    print(f"  Log-loss: {val_metrics['log_loss']:.4f}")
    print(f"  Brier: {val_metrics['brier_score']:.4f}")
    for label, m in val_metrics["per_class"].items():
        print(f"    {label}: P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} n={m['support']}")
    json.dump(val_metrics, open(OUT_F / "metrics_validation.json", "w"), indent=2)
    
    # === EVALUACION OOS (HOLDOUT) ===
    print()
    print("=== EVALUACION OOS (HOLDOUT) ===")
    oos_proba = model.predict(X_test, verbose=0)
    oos_pred = np.argmax(oos_proba, axis=1)
    oos_metrics = evaluate(y_test, oos_proba, oos_pred)
    print(f"  Accuracy: {oos_metrics['accuracy']:.4f}")
    print(f"  Balanced accuracy: {oos_metrics['balanced_accuracy']:.4f}")
    print(f"  Log-loss: {oos_metrics['log_loss']:.4f}")
    print(f"  Brier: {oos_metrics['brier_score']:.4f}")
    for label, m in oos_metrics["per_class"].items():
        print(f"    {label}: P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f} n={m['support']}")
    print()
    print("Matriz de confusion OOS:")
    print(oos_metrics["confusion_matrix"])
    print()
    print(oos_metrics["classification_report"])
    
    json.dump(oos_metrics, open(OUT_F / "metrics_test_oos.json", "w"), indent=2)
    
    # Comparacion vs baseline
    print()
    print("=== COMPARACION vs BASELINE ===")
    print(f"  Baseline accuracy OOS: {baseline['accuracy']:.4f}")
    print(f"  TensorFlow accuracy OOS: {oos_metrics['accuracy']:.4f}")
    if oos_metrics['accuracy'] > baseline['accuracy']:
        print(f"  MEJORA: +{oos_metrics['accuracy'] - baseline['accuracy']:.4f}")
    else:
        print(f"  SIN MEJORA vs baseline")
    print(f"  Baseline log-loss: {baseline_metrics['log_loss']:.4f}")
    print(f"  TensorFlow log-loss: {oos_metrics['log_loss']:.4f}")
    print()
    
    # Guardar predicciones OOS (formato JSONL: un JSON por linea)
    with open(OUT_F / "predictions_test_oos.jsonl", "w") as f:
        for i, r in enumerate(test_rows):
            pred = {
                "event_id": r["event_id"],
                "event_time": r["event_time"],
                "true_label": IDX_TO_LABEL[int(y_test[i])],
                "pred_label": IDX_TO_LABEL[int(oos_pred[i])],
                "prob_continuation": float(oos_proba[i][0]),
                "prob_reversal": float(oos_proba[i][1]),
                "prob_failure": float(oos_proba[i][2]),
                "confidence": float(np.max(oos_proba[i])),
                "correct": bool(y_test[i] == oos_pred[i]),
                "split": r["split"],
                "context_bucket": r["context_bucket"],
                "sequence_depth": r["sequence_depth"],
            }
            f.write(json.dumps(pred) + "\n")
    
    # Environment
    env = {
        "python": sys.version.split()[0],
        "tensorflow": tf.__version__,
        "numpy": np.__version__,
        "git_commit": subprocess_check("git rev-parse HEAD")[:12],
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    json.dump(env, open(OUT_F / "environment.json", "w"), indent=2)
    
    # Source manifest
    source_manifest = {
        "corpus_path": str(CORPUS_F),
        "corpus_sha256": sha256_path(CORPUS_F),
        "dataset_id": "SEQ_CTX_01_CANONICAL_BOS",
        "dataset_sha256": "74962a1d12b75ca68816d6769bbb1b57326e6ed84f2ad7f46d725687c9edc1b1",
        "generator_commit": "33fb73d5303b322d35ca16d05700f3ae8540584a",
        "split": {"TRAIN": "DESIGN (2006-2015)", "VALIDATION": "VALIDATION (2016-2020)", "TEST_OOS": "HOLDOUT (2021-2025)"},
        "n_train": len(train_rows),
        "n_validation": len(val_rows),
        "n_test_oos": len(test_rows),
    }
    json.dump(source_manifest, open(OUT_F / "source_manifest.json", "w"), indent=2)
    
    # Audit summary
    audit = {
        "can_trade": False,
        "shadow_mode": True,
        "features_fitted_only_on_train": True,
        "oos_untouched_during_training": True,
        "early_stopping_monitor": "val_loss",
        "final_epochs": len(history.history["loss"]),
        "train_loss_final": float(history.history["loss"][-1]),
        "val_loss_final": float(history.history["val_loss"][-1]),
        "train_acc_final": float(history.history["accuracy"][-1]),
        "val_acc_final": float(history.history["accuracy"][-1]),
    }
    json.dump(audit, open(OUT_F / "audit.json", "w"), indent=2)
    
    print()
    print("=== ARTEFACTOS GUARDADOS ===")
    for f in sorted(OUT_F.iterdir()):
        print(f"  {f.name} ({f.stat().st_size} bytes)")
    
    return {
        "status": "COMPLETED",
        "baseline_accuracy": baseline["accuracy"],
        "model_accuracy": oos_metrics["accuracy"],
        "baseline_logloss": baseline_metrics["log_loss"],
        "model_logloss": oos_metrics["log_loss"],
        "model_brier": oos_metrics["brier_score"],
        "final_epochs": len(history.history["loss"]),
        "train_loss": float(history.history["loss"][-1]),
        "val_loss": float(history.history["val_loss"][-1]),
    }

def subprocess_check(cmd):
    import subprocess
    try:
        return subprocess.check_output(cmd, shell=True, cwd=str(BASE)).decode().strip()
    except Exception:
        return "unknown"

if __name__ == "__main__":
    main()
