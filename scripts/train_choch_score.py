"""Entrena modelo IA para calibrar score CHOCH (F4/F5).

Lee data/learning/choch/<mes>/features.jsonl y entrena modelos que predicen
si el CHOCH "importo" (label de mercado). Itera sobre VARIOS LABELS y VARIOS
MODELOS, reporta ROC-AUC en test holdout (y CV), y persiste el mejor.

Labels candidatos (todos derivables del dataset ya generado):
  ep    : label_ep  (cierre >= k*rango en dir, sin invalidar; spec)
  peak  : label_peak (excursion favorable max >= k*rango, sin invalidar)
  dir   : label_dir (movimiento neto en la direccion del giro)
  peak15/peak10 : norm_peak = peak_fav/avg_range >= 1.5 / 1.0 (sin invalidar)
  move15/move10 : norm_move = move_ep /avg_range >= 1.5 / 1.0 (sin invalidar)

Modelos:
  lr  : LogisticRegression(class_weight=balanced)
  rf  : RandomForestClassifier(class_weight=balanced)
  gb  : GradientBoostingClassifier (sample_weight balance)

Criterio de integracion: ROC-AUC test >= 0.55 (>=0.60 ideal). Si el mejor
queda < 0.55, NO se integra y se documenta NO-EDGE.

Persiste: data/learning/choch/<mes>/model.joblib  (dict {model, features, label, meta})
          data/learning/choch/<mes>/feature_importances.json
          data/learning/choch/<mes>/train_report.json
"""
from __future__ import annotations
import sys, os, json
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import roc_auc_score, classification_report

from tools.choch_quality import FEATURES

MONTH = "2026-08"
BASE = f"data/learning/choch/{MONTH}"
SRC = os.path.join(BASE, "features.jsonl")
SEED = 42


def load() -> pd.DataFrame:
    rows = [json.loads(l) for l in open(SRC) if l.strip()]
    df = pd.DataFrame(rows)
    # derivar labels suaves a partir de columnas continuas ya guardadas
    df["norm_peak"] = df["peak_fav"] / df["avg_range"].replace(0, np.nan)
    df["norm_move"] = df["move_ep"] / df["avg_range"].replace(0, np.nan)
    df["norm_peak"] = df["norm_peak"].fillna(0.0)
    df["norm_move"] = df["norm_move"].fillna(0.0)
    df["peak15"] = (df["norm_peak"] >= 1.5).astype(int)
    df["peak10"] = (df["norm_peak"] >= 1.0).astype(int)
    df["move15"] = (df["norm_move"] >= 1.5).astype(int)
    df["move10"] = (df["norm_move"] >= 1.0).astype(int)
    return df


def make_models():
    return {
        "lr": LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEED),
        "rf": RandomForestClassifier(n_estimators=500, max_depth=6,
                                     class_weight="balanced_subsample",
                                     n_jobs=-1, random_state=SEED),
        "gb": GradientBoostingClassifier(n_estimators=300, max_depth=3,
                                         learning_rate=0.05, random_state=SEED),
    }


def cv_auc(model, X, y) -> float:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    scores = []
    for tr, te in skf.split(X, y):
        m = model.__class__(**model.get_params())
        sw = None
        if hasattr(m, "class_weight"):
            pass
        if isinstance(m, GradientBoostingClassifier):
            w = np.where(y[tr] == 1, (y[tr] == 0).sum() / max(1, (y[tr] == 1).sum()), 1.0)
            sw = w
        m.fit(X[tr], y[tr], **( {"sample_weight": sw} if sw is not None else {} ))
        p = m.predict_proba(X[te])[:, 1]
        if len(np.unique(y[te])) > 1:
            scores.append(roc_auc_score(y[te], p))
    return float(np.mean(scores)) if scores else float("nan")


def main():
    if not os.path.exists(SRC):
        print("ERROR: no existe dataset. Corre scripts/gen_choch_dataset.py primero.")
        return
    df = load()
    print(f"Dataset: {len(df)} CHOCH REAL | por tf: {df['tf'].value_counts().to_dict()}")

    labels = ["label_ep", "label_peak", "label_dir", "peak15", "peak10", "move15", "move10"]
    models = make_models()
    X = df[FEATURES].to_numpy(dtype=float)
    results = []

    print(f"\n{'label':10} {'model':4} {'n_pos':>6} {'rate':>6} {'CV_auc':>7} {'TEST_auc':>8}")
    print("-" * 50)
    for lab in labels:
        y = df[lab].to_numpy(dtype=int)
        npos = int(y.sum())
        rate = y.mean()
        if npos < 20 or (1 - rate) < 0.02:
            print(f"{lab:10} {'--':4} {npos:>6} {rate:>6.2%}  SKIP (pocos positivos/variedad)")
            continue
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25,
                                              random_state=SEED, stratify=y)
        for name, mdl in models.items():
            m = mdl.__class__(**mdl.get_params())
            sw = None
            if isinstance(m, GradientBoostingClassifier):
                w = np.where(ytr == 1, (ytr == 0).sum() / max(1, (ytr == 1).sum()), 1.0)
                sw = w
            m.fit(Xtr, ytr, **( {"sample_weight": sw} if sw is not None else {} ))
            p = m.predict_proba(Xte)[:, 1]
            test_auc = roc_auc_score(yte, p) if len(np.unique(yte)) > 1 else float("nan")
            cv = cv_auc(mdl, X, y)
            print(f"{lab:10} {name:4} {npos:>6} {rate:>6.2%} {cv:>7.3f} {test_auc:>8.3f}")
            results.append({
                "label": lab, "model": name, "n_pos": npos, "rate": float(rate),
                "cv_auc": cv, "test_auc": float(test_auc),
            })

    results.sort(key=lambda r: r["test_auc"], reverse=True)
    print("\n=== RANKING (por TEST ROC-AUC) ===")
    for r in results:
        print(f"  {r['label']:10} {r['model']:4} test={r['test_auc']:.3f} cv={r['cv_auc']:.3f} npos={r['n_pos']}")

    best = results[0] if results else None
    INTEGRATE = False
    verdict = ""
    if best is None:
        verdict = "NO-EDGE: sin suficientes positivos en ningun label."
    elif best["test_auc"] >= 0.60:
        INTEGRATE = True
        verdict = f"EDGE FUERTE: integramos {best['label']}/{best['model']} (ROC={best['test_auc']:.3f})."
    elif best["test_auc"] >= 0.55:
        INTEGRATE = True
        verdict = f"EDGE MODERADO: integramos {best['label']}/{best['model']} (ROC={best['test_auc']:.3f})."
    else:
        verdict = (f"NO-EDGE: mejor ROC={best['test_auc']:.3f} (<0.55). "
                   f"No se integra; score geometrico se mantiene.")

    print(f"\nVEREDICTO: {verdict}")

    report = {
        "best": best, "integrate": INTEGRATE, "verdict": verdict,
        "all_results": results, "features": FEATURES,
    }

    if INTEGRATE and best is not None:
        lab = best["label"]
        name = best["model"]
        y = df[lab].to_numpy(dtype=int)
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25,
                                              random_state=SEED, stratify=y)
        mdl = models[name]
        m = mdl.__class__(**mdl.get_params())
        sw = None
        if isinstance(m, GradientBoostingClassifier):
            w = np.where(ytr == 1, (ytr == 0).sum() / max(1, (ytr == 1).sum()), 1.0)
            sw = w
        m.fit(Xtr, ytr, **( {"sample_weight": sw} if sw is not None else {} ))
        p = m.predict_proba(Xte)[:, 1]
        test_auc = roc_auc_score(yte, p)
        # importancias
        if hasattr(m, "feature_importances_"):
            imp = {f: float(v) for f, v in zip(FEATURES, m.feature_importances_)}
        else:
            imp = {f: float(v) for f, v in zip(FEATURES, np.abs(m.coef_[0]))}
        imp = dict(sorted(imp.items(), key=lambda x: -x[1]))

        print("\n=== FEATURE IMPORTANCES (mejor modelo) ===")
        for f, v in imp.items():
            print(f"  {f}: {v:.3f}")

        try:
            import joblib
            obj = {"model": m, "features": FEATURES, "label": lab,
                   "meta": {"test_auc": float(test_auc), "cv_auc": best["cv_auc"],
                            "n": len(df), "n_pos": int(y.sum()),
                            "model_name": name, "trained_on": "all EURUSD M5/H4/D1 2022-2026"}}
            out = os.path.join(BASE, "model.joblib")
            joblib.dump(obj, out)
            print(f"\nModelo guardado: {out}")
            with open(os.path.join(BASE, "feature_importances.json"), "w") as f:
                json.dump(imp, f, indent=2)
            print(f"Importancias: {os.path.join(BASE, 'feature_importances.json')}")
        except Exception as e:
            print(f"(no se pudo persistir: {e})")
    else:
        print("Modelo NO persistido (no cumple umbral de edge).")

    with open(os.path.join(BASE, "train_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Reporte: {os.path.join(BASE, 'train_report.json')}")


if __name__ == "__main__":
    main()
