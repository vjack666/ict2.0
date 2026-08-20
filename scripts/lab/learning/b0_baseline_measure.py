"""B0 baseline measurement — REAL, not hardcoded.

Replica EXACTAMENTE el entrenamiento de train_choch_full.py (mismas FEAT,
mismo train_test_split random_state=42, mismos 3 modelos) y MIDE las métricas
que el plan B0 exige y que train_choch_full NO reporta:
  - ROC-AUC, PR-AUC, Brier / calibration, matriz de confusión
  - distribución de labels, n, base rate
  - sha256 del dataset (features.jsonl) y hash de código

NO modifica el pipeline: solo mide. Salida:
  data/learning/experiments/BASELINE-001/{manifest,metrics,dataset_stats,environment}.json
"""
from __future__ import annotations
import sys, os, json, hashlib, subprocess, datetime, time
sys.path.insert(0, ".")

import pandas as pd, numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_auc_score, average_precision_score,
                              brier_score_loss, confusion_matrix,
                              classification_report)

OUT = "data/learning/choch/full"
FEAT = ["score_n", "momentum", "after_bos", "displacement", "htf_ctx_code",
        "htf_trend_int", "cd", "break_body_ratio", "dist_to_level",
        "bos_age_bars", "tf_code"]
EXP = "data/learning/experiments/BASELINE-001"


def _git_commit() -> str:
    return subprocess.check_output(["git", "rev_parse", "HEAD"]).decode().strip()


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _train(label, df):
    if label not in df.columns:
        return None
    y = df[label].astype(int).to_numpy()
    if df[label].nunique() < 2:
        return {"label": label, "error": f"SIN VARIEDAD ({int(y.sum())}/{len(y)})"}
    X = df[FEAT].astype(float).to_numpy()
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)
    out = {"label": label, "n_total": int(len(y)),
           "n_pos": int(y.sum()), "base_rate": float(y.mean()),
           "n_test": int(len(yte)), "n_test_pos": int(yte.sum())}
    models = {}
    for name, clf in [
        ("RF", RandomForestClassifier(n_estimators=300, max_depth=5, random_state=42)),
        ("GBM", GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=42)),
        ("LR", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ]:
        t0 = time.time()
        clf.fit(Xtr, ytr)
        p = clf.predict_proba(Xte)[:, 1]
        pred = (p >= 0.5).astype(int)
        auc = float(roc_auc_score(yte, p))
        pr = float(average_precision_score(yte, p))
        brier = float(brier_score_loss(yte, p))
        cm = confusion_matrix(yte, pred).tolist()
        models[name] = {
            "ROC_AUC": round(auc, 4), "PR_AUC": round(pr, 4),
            "Brier": round(brier, 4), "confusion_matrix": cm,
            "seconds": round(time.time() - t0, 1),
        }
        print(f"  {label} | {name}: ROC={auc:.3f} PR={pr:.3f} Brier={brier:.3f}")
    out["models"] = models
    out["best"] = max(models, key=lambda k: models[k]["ROC_AUC"])
    return out


def main():
    os.makedirs(EXP, exist_ok=True)
    commit = _git_commit()
    feat_path = os.path.join(OUT, "features.jsonl")
    ds_sha = _sha256(feat_path)
    df = pd.DataFrame([json.loads(l) for l in open(feat_path) if l.strip()])

    print(f"Dataset: {len(df)} CHOCH, features={len(FEAT)}")
    results = {}
    for lab in ["label_ep", "label_peak", "label_dir"]:
        print(f"=== {lab} ===")
        r = _train(lab, df)
        results[lab] = r

    # ---- artifacts ----
    manifest = {
        "experiment_id": "BASELINE-001",
        "git_commit": commit,
        "pipeline": "train_choch_full.py (sin modificar) + gen_choch_dataset.py (código vigente)",
        "split_method": "train_test_split(test_size=0.25, random_state=42, stratify=y) [ALEATORIO, NO walk-forward]",
        "symbols_hardcoded": "EURUSD",
        "tfs_used": "M5 (CHOCH), M5/H4/D1 (contexto)",
        "features": FEAT,
        "labels": ["label_ep", "label_peak", "label_dir"],
        "generated_at": datetime.datetime.utcnow().isoformat(),
    }
    environment = {
        "python": sys.version.split()[0],
        "commit": commit,
        "data_raw_pairs": sorted(os.listdir("data/raw")),
        "dataset_sha256": ds_sha,
        "dataset_path": feat_path,
    }
    # class distribution real
    dist = {}
    for lab in ["label_ep", "label_peak", "label_dir"]:
        s = df[lab].astype(int)
        dist[lab] = {"n": int(len(s)), "pos": int(s.sum()),
                     "rate": round(float(s.mean()), 4)}
    by_tf = df["tf"].value_counts().to_dict()
    dataset_stats = {
        "n_total": int(len(df)),
        "by_tf": {k: int(v) for k, v in by_tf.items()},
        "label_distribution": dist,
        "label_ep_rate": round(float(df["label_ep"].mean()), 4),
        "label_peak_rate": round(float(df["label_peak"].mean()), 4),
        "label_dir_rate": round(float(df["label_dir"].mean()), 4),
    }
    # metrics = results reales por label/modelo
    metrics = {k: v for k, v in results.items() if v}
    metrics["note"] = ("ROC-AUC medido REAL sobre label_ep/peak/dir (split aleatorio). "
                       "NO confundir label_dir (~50%, sanity) con label_ep (edge real). "
                       "Walk-forward y nature head son bloques B3/B4 posteriores.")

    for name, obj in (("manifest", manifest), ("environment", environment),
                      ("dataset_stats", dataset_stats), ("metrics", metrics)):
        json.dump(obj, open(os.path.join(EXP, f"{name}.json"), "w"), indent=2)

    # STATE.json minimal
    state = {
        "pipeline_id": "LEARN-2026-08-16",
        "current_block": "B0_BASELINE",
        "current_step": "baseline_grabado",
        "status": "BLOCK_DONE",
        "last_completed_block": "B0_BASELINE",
        "last_completed_step": "baseline_grabado",
        "dataset_id": ds_sha[:16],
        "experiment_id": "BASELINE-001",
        "git_commit": commit,
        "dataset_sha256": ds_sha,
        "started_at": datetime.datetime.utcnow().isoformat(),
        "updated_at": datetime.datetime.utcnow().isoformat(),
    }
    json.dump(state, open("data/learning/pipeline/STATE.json", "w"), indent=2)

    print(f"\nBASELINE-001 grabado en {EXP}/")
    print(f"dataset sha256={ds_sha[:16]}  commit={commit[:12]}")


if __name__ == "__main__":
    main()
