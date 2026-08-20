"""B4 — EVALUACIÓN NATURE HEAD vs BASELINES (eval instantáneo, carga .npz).

Carga X,y persistidos por train_nature_head (nature_head_data.npz) y compara
nature_head.pt contra:
  - Majority (siempre reclaim=0)
  - Random (base rate)
  - LogisticRegression sobre bloque aplanado
Métricas: BCE, PR-AUC, ROC-AUC, Brier.
REGLA PLAN: si nature head no supera baselines consistentemente => NO promocionar.
"""
from __future__ import annotations
import sys, os, json, time
sys.path.insert(0, ".")
import numpy as np
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

# importar NatureHead del script real
import importlib.util as _u
_spec = _u.spec_from_file_location("tnh_mod", "scripts/lab/learning/train_nature_head.py")
tnh_mod = _u.module_from_spec(_spec)
_spec.loader.exec_module(tnh_mod)
NatureHead = tnh_mod.NatureHead

t0 = time.time()
d = np.load("data/learning/encoder/nature_head_data.npz", allow_pickle=True)
X, y, idx, n_tr = d["X"], d["y"], d["idx"], int(d["n_tr"])
print(f"Cargado: {len(X)} muestras (confirm={int(y.sum())}, {100*y.mean():.1f}%)")

tr, te = idx[:n_tr], idx[n_tr:]
Xtr, ytr = X[tr], y[tr]
Xte, yte = X[te], y[te]

# ---- Baselines ----
maj = np.zeros_like(yte)
maj_bce = 0.0
maj_brier = float(np.mean((maj - yte) ** 2))

base_rate = ytr.mean()
rng = np.random.RandomState(42)
rand = (rng.rand(len(yte)) < base_rate).astype(float)
rand_bce = float(-np.mean(yte * np.log(np.clip(rand, 1e-15, 1-1e-15)) +
                             (1 - yte) * np.log(np.clip(1 - rand, 1e-15, 1-1e-15))))
rand_brier = float(brier_score_loss(yte, rand))
rand_prauc = float(average_precision_score(yte, rand))
rand_roc = float(roc_auc_score(yte, rand))

lr = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
lr_p = lr.predict_proba(Xte)[:, 1]
lr_bce = float(-np.mean(yte * np.log(np.clip(lr_p, 1e-15, 1-1e-15)) +
                             (1 - yte) * np.log(np.clip(1 - lr_p, 1e-15, 1-1e-15))))
lr_brier = float(brier_score_loss(yte, lr_p))
lr_prauc = float(average_precision_score(yte, lr_p))
lr_roc = float(roc_auc_score(yte, lr_p))

# ---- Nature head ----
ckpt = torch.load("data/learning/encoder/nature_head.pt", weights_only=False)
model = NatureHead(int(ckpt["dim"]))
model.load_state_dict(ckpt["state"])
model.eval()
with torch.no_grad():
    nh_p = torch.sigmoid(model(torch.from_numpy(Xte.astype(np.float32)))).numpy()
nh_bce = float(-np.mean(yte * np.log(np.clip(nh_p, 1e-15, 1-1e-15)) +
                           (1 - yte) * np.log(np.clip(1 - nh_p, 1e-15, 1-1e-15))))
nh_brier = float(brier_score_loss(yte, nh_p))
nh_prauc = float(average_precision_score(yte, nh_p))
nh_roc = float(roc_auc_score(yte, nh_p))

report = {
    "n_test": int(len(yte)), "base_rate_confirm": round(float(base_rate), 4),
    "majority": {"bce": round(maj_bce, 4), "brier": round(maj_brier, 4), "pr_auc": None, "roc_auc": None},
    "random": {"bce": round(rand_bce, 4), "brier": round(rand_brier, 4),
               "pr_auc": round(rand_prauc, 4), "roc_auc": round(rand_roc, 4)},
    "logistic": {"bce": round(lr_bce, 4), "brier": round(lr_brier, 4),
                 "pr_auc": round(lr_prauc, 4), "roc_auc": round(lr_roc, 4)},
    "nature_head": {"bce": round(nh_bce, 4), "brier": round(nh_brier, 4),
                    "pr_auc": round(nh_prauc, 4), "roc_auc": round(nh_roc, 4)},
}
beats_lr = (nh_prauc > lr_prauc) and (nh_roc > lr_roc)
beats_rand = (nh_prauc > rand_prauc) and (nh_roc > rand_roc)
gate = "PASS" if (beats_lr and beats_rand) else "FAIL"
detail = (f"nature PR-AUC={nh_prauc:.3f} vs LR={lr_prauc:.3f} vs Rand={rand_prauc:.3f}; "
          f"ROC={nh_roc:.3f} vs LR={lr_roc:.3f}; BCE={nh_bce:.3f}")
report["GATE_4"] = {"result": gate, "detail": detail,
                    "beats_logistic": bool(beats_lr), "beats_random": bool(beats_rand)}
json.dump(report, open("data/learning/pipeline/experiments/EXP-005_nature_head_eval.json", "w"),
          indent=2, default=lambda o: float(o) if hasattr(o, "item") else str(o))

print(f"\nPR-AUC: nature={nh_prauc:.3f}  LR={lr_prauc:.3f}  Rand={rand_prauc:.3f}")
print(f"ROC  : nature={nh_roc:.3f}  LR={lr_roc:.3f}  Rand={rand_roc:.3f}")
print(f"BCE  : nature={nh_bce:.3f}  LR={lr_bce:.3f}  Rand={rand_bce:.3f}")
print(f"Brier: nature={nh_brier:.3f}  LR={lr_brier:.3f}  Rand={rand_brier:.3f}")
print(f"\nGATE 4: {gate} — {detail}  [{time.time()-t0:.0f}s]")
print("-> data/learning/pipeline/experiments/EXP-005_nature_head_eval.json")
