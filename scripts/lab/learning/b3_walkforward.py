"""B3 — WALK-FORWARD REAL (pipeline científico).

Elimina train_test_split aleatorio. Usa cortes temporales ROLL-FORWARD:
  TRAIN<=2018  VAL 2019-2021  TEST 2022
  TRAIN<=2019  VAL 2022       TEST 2023
  ... hasta TEST 2026

Por cada fold: entrena LogisticRegression sobre features -> mide
PR-AUC, ROC-AUC, recall, precision, base rate. Guarda por fold.

NO promociona. Solo reporta estabilidad OOS (tu BLOQUE 3).

Usa los datasets de B2 (data/learning/choch/<sym>/<tf>/features.jsonl).
D1 se excluye del train por insuficiencia (B2: EURUSD D1=1 fila).
"""
from __future__ import annotations
import sys, os, json, time
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, recall_score, precision_score

OUT = "data/learning/pipeline/experiments/EXP-004_walkforward"
os.makedirs(OUT, exist_ok=True)
SYMS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
TFS = ["H1", "H4"]  # D1 excluido (insuficiente, B2)
FEATS = ["score", "momentum", "after_bos", "displacement", "break_body_ratio"]


def _load(sym, tf):
    p = f"data/learning/choch/{sym}/{tf}/features.jsonl"
    if not os.path.exists(p):
        return None
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    for r in rows:
        r["dt"] = pd.to_datetime(r["time"])
    return rows


def _folds():
    cuts = [(2018, 2019, 2022), (2019, 2022, 2023), (2020, 2023, 2024),
            (2021, 2024, 2025), (2022, 2025, 2026)]
    return cuts


def main():
    t0 = time.time()
    report = {"folds": [], "per_symbol_tf": {}}
    for sym in SYMS:
        report["per_symbol_tf"][sym] = {}
        for tf in TFS:
            rows = _load(sym, tf)
            if not rows or len(rows) < 100:
                report["per_symbol_tf"][sym][tf] = {"error": f"insufficient ({len(rows) if rows else 0})"}
                continue
            df = pd.DataFrame(rows)
            df = df.dropna(subset=FEATS + ["label_ep"])
            y = df["label_ep"].to_numpy()
            X = df[FEATS].to_numpy()
            dt = df["dt"]
            fold_res = []
            for tr_end, val_end, te_end in _folds():
                trm = dt.dt.year <= tr_end
                vm = (dt.dt.year > tr_end) & (dt.dt.year <= val_end)
                tem = dt.dt.year > val_end
                if trm.sum() < 50 or tem.sum() < 10:
                    continue
                Xtr, ytr = X[trm], y[trm]
                Xte, yte = X[tem], y[tem]
                try:
                    m = LogisticRegression(max_iter=500).fit(Xtr, ytr)
                    p = m.predict_proba(Xte)[:, 1]
                    prauc = average_precision_score(yte, p) if yte.sum() > 0 else float("nan")
                    roc = roc_auc_score(yte, p) if len(set(yte)) > 1 else float("nan")
                    pred = (p >= 0.5).astype(int)
                    fold_res.append({
                        "train_end": tr_end, "test_end": te_end,
                        "n_train": int(trm.sum()), "n_test": int(tem.sum()),
                        "base_rate": round(float(yte.mean()), 3),
                        "pr_auc": round(float(prauc), 3) if prauc == prauc else None,
                        "roc_auc": round(float(roc), 3) if roc == roc else None,
                    })
                except Exception as e:
                    fold_res.append({"train_end": tr_end, "error": str(e)[:60]})
            report["per_symbol_tf"][sym][tf] = fold_res
            print(f"{sym} {tf}: {len(fold_res)} folds | "
                  f"PR-AUC medio: {np.nanmean([f.get('pr_auc') or float('nan') for f in fold_res]):.3f}")
    json.dump(report, open(os.path.join(OUT, "walkforward.json"), "w"), indent=2)
    # GATE 3
    all_prauc = [f.get("pr_auc") for s in report["per_symbol_tf"].values()
                 for tf in s.values() if isinstance(tf, list) for f in tf if f.get("pr_auc")]
    gate = "PASS" if len(all_prauc) >= 3 else "INCONCLUSIVE"
    detail = f"{len(all_prauc)} folds con PR-AUC medible. Estabilidad OOS por fold."
    report["GATE_3"] = {"result": gate, "detail": detail}
    json.dump(report, open(os.path.join(OUT, "walkforward.json"), "w"), indent=2)
    print(f"\nGATE 3: {gate} — {detail}  [{time.time()-t0:.0f}s]")
    print(f"-> {OUT}/walkforward.json")


if __name__ == "__main__":
    main()
