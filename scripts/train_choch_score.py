"""Entrena modelo IA para calibrar score CHOCH (F4/F5).

Lee data/learning/choch/2026-08/features.jsonl y entrena RandomForest que
predice si el CHOCH "importo" (label). Usa:
  features: momentum, after_bos, displacement, htf_ctx(0/1/2), score
  target: label

Salida:
  - modelo persistido en data/learning/choch/2026-08/model.joblib
  - importancias para recalibrar pesos del score hibrido
  - reporte de accuracy/feature_importances

Uso: el predict_proba del modelo reemplaza el "IA 15%" del score hibrido
en tools/choch_quality.py (componente extensible).
"""
from __future__ import annotations
import sys, json, os
sys.path.insert(0, ".")
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

FEATURES = ["momentum", "after_bos", "displacement", "htf_ctx_code", "score"]


def load(path: str) -> pd.DataFrame:
    rows = [json.loads(l) for l in open(path) if l.strip()]
    df = pd.DataFrame(rows)
    ctx_map = {"contra": 0, "neutral": 1, "a_favor": 2}
    df["htf_ctx_code"] = df["htf_ctx"].map(ctx_map).fillna(1).astype(int)
    return df


def main():
    path = "data/learning/choch/2026-08/features.jsonl"
    if not os.path.exists(path):
        print("ERROR: no existe dataset. Corre scripts/gen_choch_dataset.py primero.")
        return
    df = load(path)
    print(f"Dataset: {len(df)} CHOCH, labels=1: {int(df['label'].sum())} ({df['label'].mean():.1%})")
    X = df[FEATURES].to_numpy()
    y = df["label"].to_numpy()
    if len(df) < 20 or df["label"].nunique() < 2:
        print("INSUFICIENTE: no hay variedad de labels para entrenar. Revisa el label/umbral.")
        return
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    clf = RandomForestClassifier(n_estimators=200, max_depth=4, random_state=42)
    clf.fit(Xtr, ytr)
    pred = clf.predict(Xte)
    proba = clf.predict_proba(Xte)[:, 1]
    print("=== CLASSIFICATION REPORT (test) ===")
    print(classification_report(yte, pred, zero_division=0))
    try:
        print(f"ROC-AUC: {roc_auc_score(yte, proba):.3f}")
    except Exception:
        pass
    print("=== FEATURE IMPORTANCES ===")
    for f, imp in sorted(zip(FEATURES, clf.feature_importances_), key=lambda x: -x[1]):
        print(f"  {f}: {imp:.3f}")
    # persistir
    try:
        import joblib
        out = "data/learning/choch/2026-08/model.joblib"
        joblib.dump(clf, out)
        print(f"Modelo guardado: {out}")
    except Exception as e:
        print(f"(no se pudo persistir modelo: {e})")


if __name__ == "__main__":
    main()
