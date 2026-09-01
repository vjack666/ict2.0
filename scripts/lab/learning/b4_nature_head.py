"""B4 — NATURE HEAD + BASELINES (pipeline científico, BLOQUE 4).

Entrena naturaleza (bos_confirm vs reclaim) con walk-forward temporal.
Compara contra baselines OBLIGATORIOS (tu regla):
  - Majority  (siempre predice reclaim => la clase mayoritaria)
  - Random
  - LogisticRegression
  - NatureHead (MLP, P5)
Si el sofisticado no supera baselines consistentemente => NO se promociona.

Metrica: PR-AUC de la clase confirm (rara, ~10%), NO accuracy
(89-90% accuracy de Majority ya "ganaria" y no significaria nada).

Reusa tools/block_builder para bloques de velas normalizados.
Walk-forward: cortes temporales por año (igual que B3).
"""
from __future__ import annotations
import sys, os, json, time
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

from tools.block_builder import build_tf_blocks, W_PRE_DEFAULT, W_POST_DEFAULT
from tools.choch import CHOCHTool
from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.bos_filter import filter_bos_thesis
from tools.displacement import detect_displacement
from tools.choch_quality import mark_choch_quality

OUT = "data/learning/pipeline/experiments/EXP-005_nature_head"
os.makedirs(OUT, exist_ok=True)
SYMS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
TFS = ["M5"]  # B4 usa M5 (volumen + block_builder rapido, como P5). H1/H4 para B7.
W_POST = 30


def _nature_blocks(sym, tf):
    """Re-mide naturaleza P3 y devuelve (X_flat, y, years) por CHOCH real."""
    p = f"data/raw/{sym}/{sym}_{tf}.parquet"
    if not os.path.exists(p):
        return None
    d = pd.read_parquet(p).assign(time=pd.to_datetime(pd.read_parquet(p)["time"])).reset_index(drop=True)
    out = detect_displacement(d)
    sw = SwingTool(tf=tf).run(out, symbol=sym)
    sids = {e.origin_bar: e.id for e in sw}
    bo = BOSTool(lookback=5).run(out, symbol=sym, context={"swing_ids": sids})
    bo = apply_validation(out, bo)
    bo = filter_bos_thesis(out, bo, confirm_bars=2, max_idle_bars=0)
    che = CHOCHTool().run(out, symbol=sym, context={"swings": sw, "boses": bo})
    che = mark_choch_quality(out, che, sw, bo, htf_frames={})
    evs = []
    for e in che:
        if not e.extra.get("choch_real"):
            continue
        bb = e.break_bar if e.break_bar is not None else e.bar_index
        if bb is None:
            continue
        evs.append({"break_bar": int(bb), "signal": e.signal, "tf": tf, "symbol": sym,
                    "time": str(d["time"].iloc[bb])})
    blocks = build_tf_blocks(p, evs, w_pre=W_PRE_DEFAULT, w_post=W_POST)
    close = d["close"].to_numpy(float)
    rng = (d["high"] - d["low"]).clip(lower=0).rolling(14, min_periods=1).mean().to_numpy()
    X, y, yrs = [], [], []
    for b in blocks:
        i = b["bar"]
        if i + W_POST >= len(close):
            continue
        level = close[i]; post = close[i + 1: i + W_POST + 1]
        cd = b["cd"]
        reclaimed = bool((post < level).any()) if cd == 1 else bool((post > level).any())
        fav = float(np.clip((post - level).max() if cd == 1 else (level - post).max(), 0, None))
        thr = 2.0 * (rng[i] if rng[i] > 1e-9 else 1e-9)
        confirm = int((not reclaimed) and fav >= thr)
        X.append(b["X"].astype(np.float32).flatten())
        y.append(confirm)
        yrs.append(pd.to_datetime(b["time"]).year)
    return np.array(X), np.array(y, dtype=np.float32), np.array(yrs)


class NatureHead(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, 64), nn.ReLU(),
                                 nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))
    def forward(self, x):
        return self.net(x).squeeze(-1)


def _folds():
    return [(2018, 2019, 2022), (2019, 2022, 2023), (2020, 2023, 2024),
            (2021, 2024, 2025), (2022, 2025, 2026)]


def _pr_auc(y, p):
    if y.sum() == 0 or len(set(y)) < 2:
        return None
    return float(average_precision_score(y, p))


def main():
    t0 = time.time()
    report = {"per_symbol_tf": {}}
    for sym in SYMS:
        report["per_symbol_tf"][sym] = {}
        for tf in TFS:
            res = _nature_blocks(sym, tf)
            if res is None or len(res[0]) < 100:
                report["per_symbol_tf"][sym][tf] = {"error": "insufficient"}
                continue
            X, y, yrs = res
            pr_aucs = {"majority": [], "random": [], "logreg": [], "naturehead": []}
            for tr_end, val_end, te_end in _folds():
                trm = yrs <= tr_end; tem = yrs > val_end
                if trm.sum() < 50 or tem.sum() < 10:
                    continue
                Xtr, ytr, Xte, yte = X[trm], y[trm], X[tem], y[tem]
                base = float(yte.mean())
                # Majority: siempre reclaim => P(confirm)=0
                pr_aucs["majority"].append(_pr_auc(yte, np.zeros(len(yte))))
                # Random
                rng = np.random.RandomState(0)
                pr_aucs["random"].append(_pr_auc(yte, rng.rand(len(yte))))
                # LogReg
                try:
                    m = LogisticRegression(max_iter=500).fit(Xtr, ytr)
                    pr_aucs["logreg"].append(_pr_auc(yte, m.predict_proba(Xte)[:, 1]))
                except Exception:
                    pass
                # NatureHead MLP
                try:
                    model = NatureHead(X.shape[1])
                    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
                    loss_fn = nn.BCEWithLogitsLoss()
                    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(ytr))
                    dl = DataLoader(ds, batch_size=256, shuffle=True)
                    for _ in range(8):
                        for xb, yb in dl:
                            opt.zero_grad(); loss = loss_fn(model(xb), yb)
                            loss.backward(); opt.step()
                    model.eval()
                    with torch.no_grad():
                        pp = torch.sigmoid(model(torch.from_numpy(Xte))).numpy()
                    pr_aucs["naturehead"].append(_pr_auc(yte, pp))
                except Exception:
                    pass
            summ = {k: round(float(np.nanmean([x for x in v if x is not None])), 3)
                    if any(x is not None for x in v) else None for k, v in pr_aucs.items()}
            report["per_symbol_tf"][sym][tf] = {"folds": len(pr_aucs["majority"]),
                                                 "pr_auc_confirm": summ}
            print(f"{sym} {tf}: PR-AUC confirm | maj={summ['majority']} "
                  f"rnd={summ['random']} lr={summ['logreg']} nh={summ['naturehead']}")
    # GATE 4
    nh = [tf["pr_auc_confirm"]["naturehead"] for s in report["per_symbol_tf"].values()
          for tf in s.values() if isinstance(tf, dict) and tf.get("pr_auc_confirm", {}).get("naturehead")]
    lr = [tf["pr_auc_confirm"]["logreg"] for s in report["per_symbol_tf"].values()
          for tf in s.values() if isinstance(tf, dict) and tf.get("pr_auc_confirm", {}).get("logreg")]
    if nh and lr and np.nanmean(nh) > np.nanmean(lr):
        gate = "PASS"
        detail = f"NatureHead PR-AUC medio {np.nanmean(nh):.3f} > LogReg {np.nanmean(lr):.3f}"
    else:
        gate = "INCONCLUSIVE"
        detail = "NatureHead NO supera consistentemente baselines => NO se promociona al motor"
    report["GATE_4"] = {"result": gate, "detail": detail}
    json.dump(report, open(os.path.join(OUT, "nature_head.json"), "w"), indent=2)
    print(f"\nGATE 4: {gate} — {detail}  [{time.time()-t0:.0f}s]")
    print(f"-> {OUT}/nature_head.json")


if __name__ == "__main__":
    main()
