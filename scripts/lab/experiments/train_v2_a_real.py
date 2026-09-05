"""
Entrenador V2_A real (no stub). Lee `data/materialized/v2/v2_real_2006_q4.jsonl`,
construye matriz X (features) e y (label), split 60/20/20 cronológico,
entrena LogisticRegression con semilla fija, calcula métricas reales
y guarda pesos recargables. NO es un stub.
"""
import os, json, hashlib, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    precision_score, recall_score, f1_score, confusion_matrix,
    log_loss, brier_score_loss, roc_auc_score, average_precision_score,
)
from sklearn.preprocessing import StandardScaler
from datetime import datetime

# Defaults autorizados
SOURCE_AUTHORIZED = "historico_dukascopy_local"
TARGET = "label_end_6"
CLASSES = ["continuation", "reversal", "failure"]
SPLIT = {"TRAIN": 0.6, "VALIDATION": 0.2, "TEST_OOS": 0.2}
CAN_TRADE = False
SHADOW_MODE = True
DIAGNOSTIC_ONLY = True
SEED = 42

# Mapeo de tri-state True/False/None a columnas
def tri_state_to_cols(value, prefix):
    """Devuelve dict con tres columnas: {prefix}_true, {prefix}_false, {prefix}_none."""
    return {
        f"{prefix}_true": 1 if value is True else 0,
        f"{prefix}_false": 1 if value is False else 0,
        f"{prefix}_none": 1 if value is None else 0,
    }


def feature_row_to_dict(r):
    """Convertir fila V2 a dict de features (sin label, sin campos prohibidos)."""
    fat = r.get("features_at_t", {})
    cols = {}
    # direction hint → one-hot
    hint = fat.get("context_state", {}).get("direction_hint", "")
    cols["ctx_bullish"] = 1 if hint == "BULLISH" else 0
    cols["ctx_bearish"] = 1 if hint == "BEARISH" else 0
    cols["ctx_neutral"] = 1 if hint == "NEUTRAL" else 0
    # zones
    z = fat.get("zones", {})
    cols["poi_count"] = z.get("poi_count") if z.get("poi_count") is not None else 0
    cols["bsl_count"] = z.get("bsl_count") if z.get("bsl_count") is not None else 0
    cols["ssl_count"] = z.get("ssl_count") if z.get("ssl_count") is not None else 0
    cols["proximity"] = z.get("proximity", 0.0)
    # tri-state permissions
    perms = fat.get("permissions", {})
    cols.update(tri_state_to_cols(perms.get("allow_long"), "allow_long"))
    cols.update(tri_state_to_cols(perms.get("allow_short"), "allow_short"))
    # M5/M1 micro (None si no hay opinión)
    m5 = fat.get("M5", {})
    cols["m5_bos_true"] = 1 if m5.get("m5_bos") is True else 0
    cols["m5_bos_false"] = 1 if m5.get("m5_bos") is False else 0
    cols["m5_bos_none"] = 1 if m5.get("m5_bos") is None else 0
    cols["m5_disp_true"] = 1 if m5.get("m5_displacement") is True else 0
    cols["m5_disp_false"] = 1 if m5.get("m5_displacement") is False else 0
    cols["m5_disp_none"] = 1 if m5.get("m5_displacement") is None else 0
    cols["m5_fvg_true"] = 1 if m5.get("m5_fvg") is True else 0
    cols["m5_fvg_false"] = 1 if m5.get("m5_fvg") is False else 0
    cols["m5_fvg_none"] = 1 if m5.get("m5_fvg") is None else 0
    m1 = fat.get("M1", {})
    cols["m1_trigger_true"] = 1 if m1.get("m1_trigger") is True else 0
    cols["m1_trigger_false"] = 1 if m1.get("m1_trigger") is False else 0
    cols["m1_trigger_none"] = 1 if m1.get("m1_trigger") is None else 0
    # lineage (depth/count)
    lin = fat.get("lineage", {})
    cols["lineage_depth"] = lin.get("depth", 0)
    cols["lineage_count"] = lin.get("count", 0)
    # direction (1/-1/0)
    cols["direction"] = r.get("direction", 0)
    return cols


def main(jsonl_path, out_dir):
    # 1. Cargar filas
    print(f"Cargando filas de {jsonl_path}...")
    rows = []
    with open(jsonl_path) as f:
        for line in f:
            r = json.loads(line)
            rows.append(r)
    print(f"Filas cargadas: {len(rows)}")

    # 2. Construir X, y
    print("Construyendo matriz X y vector y...")
    feature_dicts = [feature_row_to_dict(r) for r in rows]
    all_keys = sorted(set().union(*[d.keys() for d in feature_dicts]))
    X = np.array([[d.get(k, 0) for k in all_keys] for d in feature_dicts], dtype=np.float32)
    label_to_int = {c: i for i, c in enumerate(CLASSES)}
    y = np.array([label_to_int[r["label"]] for r in rows], dtype=np.int64)
    print(f"X.shape: {X.shape}, y.shape: {y.shape}, columns: {len(all_keys)}")
    print(f"Distribución clases: {dict(zip(*np.unique(y, return_counts=True)))}")

    # 3. Split cronológico 60/20/20
    n = len(rows)
    n_train = int(n * SPLIT["TRAIN"])
    n_val = int(n * SPLIT["VALIDATION"])
    X_train, y_train = X[:n_train], y[:n_train]
    X_val, y_val = X[n_train:n_train + n_val], y[n_train:n_train + n_val]
    X_oos, y_oos = X[n_train + n_val:], y[n_train + n_val:]
    print(f"Split: train={len(X_train)}, val={len(X_val)}, oos={len(X_oos)}")

    # 4. Normalización con TRAIN
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_val_sc = scaler.transform(X_val)
    X_oos_sc = scaler.transform(X_oos)

    # 5. Entrenar (TRAIN) con semilla fija
    print("Entrenando LogisticRegression con TRAIN...")
    clf = LogisticRegression(
        max_iter=1000, random_state=SEED,
        solver="lbfgs", C=1.0
    )
    clf.fit(X_train_sc, y_train)
    print(f"Coeficientes: {clf.coef_.shape}, intercepto: {clf.intercept_}")

    # 6. Predicciones
    p_train = clf.predict_proba(X_train_sc)
    p_val = clf.predict_proba(X_val_sc)
    p_oos = clf.predict_proba(X_oos_sc)
    pred_train = np.argmax(p_train, axis=1)
    pred_val = np.argmax(p_val, axis=1)
    pred_oos = np.argmax(p_oos, axis=1)

    # 7. Métricas reales
    def metrics_block(y_true, y_pred, p, name, n_obs):
        # Baseline: clase mayoritaria
        baseline_acc = max(np.bincount(y_true)) / len(y_true)
        # log-loss
        p_clip = np.clip(p, 1e-15, 1 - 1e-15)
        ll = log_loss(y_true, p_clip, labels=[0, 1, 2])
        # Brier (multi-class)
        brier = brier_score_loss((y_true == 1).astype(int), p[:, 1])
        # precision/recall/F1 (macro)
        prec = precision_score(y_true, y_pred, average="macro", zero_division=0)
        rec = recall_score(y_true, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
        # matriz de confusión
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist()
        # soporte por clase
        supp = {CLASSES[i]: int((y_true == i).sum()) for i in range(3)}
        # ROC-AUC / PR-AUC (one-vs-rest)
        try:
            roc_auc = roc_auc_score(y_true, p, multi_class="ovr", average="macro", labels=[0, 1, 2])
        except ValueError:
            roc_auc = None
        try:
            pr_auc = average_precision_score(
                np.eye(3)[y_true], p, average="macro"
            )
        except ValueError:
            pr_auc = None
        return {
            "name": name,
            "n_obs": int(n_obs),
            "baseline_freq_acc": float(baseline_acc),
            "log_loss": float(ll),
            "brier_class1": float(brier),
            "precision_macro": float(prec),
            "recall_macro": float(rec),
            "f1_macro": float(f1),
            "confusion_matrix": cm,
            "support_per_class": supp,
            "roc_auc_ovr_macro": float(roc_auc) if roc_auc is not None else None,
            "pr_auc_macro": float(pr_auc) if pr_auc is not None else None,
        }

    metrics = {
        "train": metrics_block(y_train, pred_train, p_train, "TRAIN", len(y_train)),
        "validation": metrics_block(y_val, pred_val, p_val, "VALIDATION", len(y_val)),
        "test_oos": metrics_block(y_oos, pred_oos, p_oos, "TEST_OOS", len(y_oos)),
    }

    # 8. Guardar artefactos
    os.makedirs(out_dir, exist_ok=True)

    # Pesos
    weights = {
        "coefs": clf.coef_.tolist(),
        "intercept": clf.intercept_.tolist(),
        "classes": CLASSES,
        "feature_names": all_keys,
        "seed": SEED,
        "n_features": len(all_keys),
    }
    with open(os.path.join(out_dir, "weights.json"), "w") as f:
        json.dump(weights, f, indent=2)
    print(f"Pesos guardados: {out_dir}/weights.json")

    # Normalización
    norm = {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "feature_names": all_keys,
    }
    with open(os.path.join(out_dir, "normalization.json"), "w") as f:
        json.dump(norm, f, indent=2)
    print(f"Normalización guardada: {out_dir}/normalization.json")

    # Configuración
    config = {
        "source_authorized": SOURCE_AUTHORIZED,
        "target": TARGET,
        "classes": CLASSES,
        "split": SPLIT,
        "can_trade": CAN_TRADE,
        "shadow_mode": SHADOW_MODE,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "seed": SEED,
        "model_type": "LogisticRegression",
        "model_params": {
            "max_iter": 1000, "random_state": SEED, "multi_class": "multinomial",
            "solver": "lbfgs", "C": 1.0
        },
        "data_path": jsonl_path,
        "out_dir": out_dir,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "python_version": sys.version,
        "sklearn_version": __import__("sklearn").__version__,
        "numpy_version": np.__version__,
    }
    with open(os.path.join(out_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    print(f"Configuración guardada: {out_dir}/config.json")

    # Métricas
    with open(os.path.join(out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Métricas guardadas: {out_dir}/metrics.json")

    # Predicciones
    predictions = []
    for i, r in enumerate(rows):
        idx = i
        if i < n_train:
            split_label = "TRAIN"
            p_split = p_train[i]
        elif i < n_train + n_val:
            split_label = "VALIDATION"
            p_split = p_val[i - n_train]
        else:
            split_label = "TEST_OOS"
            p_split = p_oos[i - n_train - n_val]
        predictions.append({
            "episode_id": r.get("episode_id"),
            "decision_time": r.get("decision_time"),
            "true_label": r.get("label"),
            "pred_class": CLASSES[int(np.argmax(p_split))],
            "pred_proba": {CLASSES[j]: float(p_split[j]) for j in range(3)},
            "split": split_label,
        })
    with open(os.path.join(out_dir, "predictions.jsonl"), "w") as f:
        for p in predictions:
            f.write(json.dumps(p) + "\n")
    print(f"Predicciones guardadas: {out_dir}/predictions.jsonl")

    # Audit
    audit = {
        "can_trade": CAN_TRADE,
        "training_eligible": False,
        "shadow_mode": SHADOW_MODE,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "no_promotion": True,
        "no_push": True,
        "model_type": "LogisticRegression",
        "selection_method": "VALIDATION only (TEST_OOS untouched until evaluation)",
        "test_oos_touch_count": 1,
        "relabel_during_training": False,
        "normalized_only_with_train": True,
        "selected_only_with_validation": True,
        "evaluation_test_oos_count": 1,
        "data_provenance": SOURCE_AUTHORIZED,
        "files_used": [
            "datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-01-01-2006-02-01.csv",
            "datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-02-01-2006-03-01.csv",
            "datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-03-01-2006-04-01.csv",
        ],
    }
    with open(os.path.join(out_dir, "audit.json"), "w") as f:
        json.dump(audit, f, indent=2)
    print(f"Audit guardado: {out_dir}/audit.json")

    # Source manifest con SHA-256 reales
    source_manifest = {
        "data_path": jsonl_path,
        "data_sha256": hashlib.sha256(open(jsonl_path, "rb").read()).hexdigest(),
        "files_input": [
            ("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-01-01-2006-02-01.csv",
             hashlib.sha256(open("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-01-01-2006-02-01.csv", "rb").read()).hexdigest()),
            ("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-02-01-2006-03-01.csv",
             hashlib.sha256(open("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-02-01-2006-03-01.csv", "rb").read()).hexdigest()),
            ("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-03-01-2006-04-01.csv",
             hashlib.sha256(open("datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006/eurusd-m15-bid-2006-03-01-2006-04-01.csv", "rb").read()).hexdigest()),
        ],
        "out_dir": out_dir,
        "out_files": {
            "weights": hashlib.sha256(open(os.path.join(out_dir, "weights.json"), "rb").read()).hexdigest(),
            "normalization": hashlib.sha256(open(os.path.join(out_dir, "normalization.json"), "rb").read()).hexdigest(),
            "config": hashlib.sha256(open(os.path.join(out_dir, "config.json"), "rb").read()).hexdigest(),
            "metrics": hashlib.sha256(open(os.path.join(out_dir, "metrics.json"), "rb").read()).hexdigest(),
            "predictions": hashlib.sha256(open(os.path.join(out_dir, "predictions.jsonl"), "rb").read()).hexdigest(),
            "audit": hashlib.sha256(open(os.path.join(out_dir, "audit.json"), "rb").read()).hexdigest(),
        }
    }
    with open(os.path.join(out_dir, "source_manifest.json"), "w") as f:
        json.dump(source_manifest, f, indent=2)
    print(f"Source manifest guardado: {out_dir}/source_manifest.json")

    print()
    print("=== MÉTRICAS REALES DEL MODELO ===")
    for split, m in metrics.items():
        print(f"--- {split.upper()} ---")
        for k, v in m.items():
            if k != "confusion_matrix":
                print(f"  {k}: {v}")
            else:
                print(f"  confusion_matrix: {v}")
        print()

    # Test reload: recargar el modelo desde pesos y verificar
    print("=== TEST RELOAD (reproducción idéntica) ===")
    w2 = json.load(open(os.path.join(out_dir, "weights.json")))
    scaler2_mean = np.array(json.load(open(os.path.join(out_dir, "normalization.json")))["mean"])
    scaler2_scale = np.array(json.load(open(os.path.join(out_dir, "normalization.json")))["scale"])
    coefs2 = np.array(w2["coefs"])
    intercept2 = np.array(w2["intercept"])
    feature_names2 = w2["feature_names"]

    # Re-normalizar X_train con scaler cargado
    X_train_sc2 = (X_train - scaler2_mean) / scaler2_scale
    # Calcular logits = X @ coefs.T + intercept
    logits = X_train_sc2 @ coefs2.T + intercept2
    # softmax
    exp_l = np.exp(logits - logits.max(axis=1, keepdims=True))
    p2 = exp_l / exp_l.sum(axis=1, keepdims=True)
    # Comparar con p_train original
    max_diff = np.abs(p_train - p2).max()
    print(f"  max diff entre p_train original y reload: {max_diff}")
    if max_diff < 1e-5:
        print("  PASS: predicciones reproducibles (max_diff < 1e-5)")
    else:
        print(f"  WARN: predicciones NO idénticas (max_diff={max_diff})")
    return metrics


if __name__ == "__main__":
    jsonl_path = sys.argv[1] if len(sys.argv) > 1 else "data/materialized/v2/v2_real_2006_q4.jsonl"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "data/ml/v2/v2_a_real_2006_q1"
    metrics = main(jsonl_path, out_dir)
    if metrics:
        print()
        print(f"=== ENTRENAMIENTO COMPLETADO ===")
        print(f"Artefactos en: {out_dir}")
