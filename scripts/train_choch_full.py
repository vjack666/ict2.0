import sys, json, os
sys.path.insert(0, ".")
import pandas as pd, numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
import joblib

OUT = "data/learning/choch/full"
df = pd.DataFrame([json.loads(l) for l in open(f"{OUT}/features.jsonl") if l.strip()])
FEAT = ["score_n", "momentum", "after_bos", "displacement", "htf_ctx_code",
        "htf_trend_int", "cd", "break_body_ratio", "dist_to_level", "bos_age_bars", "tf_code"]

def run(label):
    if label not in df.columns:
        print(f"{label}: ausente"); return
    y = df[label].astype(int).to_numpy()
    if df[label].nunique() < 2:
        print(f"{label}: SIN VARIEDAD ({int(y.sum())}/{len(y)})"); return
    X = df[FEAT].astype(float).to_numpy()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)
    results = {}
    for name, clf in [
        ("RF", RandomForestClassifier(n_estimators=300, max_depth=5, random_state=42)),
        ("GBM", GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=42)),
        ("LR", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ]:
        clf.fit(Xtr, ytr)
        p = clf.predict_proba(Xte)[:, 1]
        auc = roc_score = roc_auc_score(yte, p)
        results[name] = (auc, clf)
        print(f"  {label} | {name}: ROC-AUC={auc:.3f}")
    # mejor modelo
    best = max(results, key=lambda k: results[k][0])
    auc, clf = results[best]
    print(f"  -> MEJOR {best} ROC={auc:.3f} para {label}")
    return (label, best, auc, clf)

print(f"Dataset: {len(df)} CHOCH, features={len(FEAT)}")
best_overall = None
for lab in ["label_ep", "label_peak", "label_dir"]:
    print(f"=== {lab} ===")
    r = run(lab)
    if r and (best_overall is None or r[2] > best_overall[2]):
        best_overall = r

if best_overall:
    lab, name, auc, clf = best_overall
    print(f"\nMODELO FINAL: {name} label={lab} ROC={auc:.3f}")
    if auc >= 0.55:
        # guardar modelo envuelto en dict con features + label
        obj = {"model": clf, "features": FEAT, "label": lab, "roc_auc": float(auc)}
        # limpiar model.joblib invalido previo
        for mp in ["data/learning/choch/2026-08/model.joblib", f"{OUT}/model.joblib"]:
            try:
                os.remove(mp)
            except FileNotFoundError:
                pass
        joblib.dump(obj, f"{OUT}/model.joblib")
        print(f"GUARDADO model.joblib (ROC={auc:.3f}, label={lab})")
    else:
        print(f"ROC={auc:.3f} < 0.55: NO se integra. Score geometrico se mantiene.")
else:
    print("Sin modelo entrenable.")
