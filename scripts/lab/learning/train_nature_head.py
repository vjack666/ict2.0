"""P5 — HEAD B: modelo que aprende la NATURALEZA del CHOCH (recomendacion auditoria #1).

El encoder P2 tiene test_mse plano (no aprendio dinamica util). La auditoria
externa (commit 4dd90aa) recomienda: en vez de bajar MSE de reconstruccion,
entrenar un HEAD SUPERVISADO por la naturaleza medida en P3
(bos_confirm / reclaim). Eso alinea el aprendizaje con la pregunta de
negocio: "¿este CHOCH se comporto como giro real o como ruido?".

Diseno robusto (no depende del encoder defectuoso):
  Input A: embedding_z del encoder (si se usa) -> extractor de forma
  Input B: features del bloque normalizado (flatten 61x7) -> informativo de forma
  Target : naturaleza P3 (0=reclaim, 1=bos_confirm)  [el 92.8% reclaim es la
           distribucion real del dominio; el modelo la internaliza, no la pelea]
  Modelo : MLP ligero (2 capas) -> sigmoid. CE loss.
  Salida : P(bos_confirm) por CHOCH + reporte de calibracion.

Esto es el cierre del loop F5: la IA "aprende la naturaleza" desde el bloque
de velas, sin asumir la narrativa de que CHOCH=giro.

Requiere torch (ya instalado en venv). Reusa tools/block_builder + probe.
"""
from __future__ import annotations
import sys, os, json, time
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from tools.block_builder import build_tf_blocks, W_PRE_DEFAULT, W_POST_DEFAULT
from tools.choch import CHOCHTool
from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.bos_filter import filter_bos_thesis
from tools.displacement import detect_displacement

SYM = "EURUSD"
TF = "M5"
PARQUET = f"data/raw/{SYM}/{SYM}_{TF}.parquet"
USE_EMBEDDING = False   # el encoder P2 es plano; usamos bloque normalizado directo
EPOCHS = 12
BATCH = 256
LR = 1e-3
OUT = "data/learning/encoder/nature_head.pt"


def _nature_targets():
    """Re-mide la naturaleza P3 (confirm vs reclaim) y devuelve (bars, cds, labels)."""
    d = pd.read_parquet(PARQUET)
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    # OPCION A (2026-08-20): usar TODO el rango (no solo 2026-08) y NO filtrar
    # CHOCH por filter_bos_thesis (anulaba CHOCH). Suff samples para baselines.
    out = detect_displacement(d)
    sw = SwingTool(lookback=5).run(out, symbol=SYM)
    sids = {e.origin_bar: e.id for e in sw if e.origin_bar is not None}
    bo = BOSTool(lookback=5).run(out, symbol=SYM, context={"swing_ids": sids, "swings": sw})
    bo = apply_validation(out, bo)
    # anti-flood BOS (Opción A: solo BOS)
    bo = filter_bos_thesis(out, bo, confirm_bars=2, max_idle_bars=0)
    bo = [e for e in bo if e.extra.get("is_unique") is True]
    che = CHOCHTool().run(out, symbol=SYM, context={"swings": sw, "boses": bo})
    # OPCION A: NO filter_bos_thesis sobre CHOCH
    evs = []
    for e in che:
        bb = e.break_bar if e.break_bar is not None else e.bar_index
        if bb is None:
            continue
        evs.append({"break_bar": int(bb), "signal": e.signal, "tf": TF,
                    "symbol": SYM, "time": str(d["time"].iloc[bb])})
    blocks = build_tf_blocks(PARQUET, evs, w_pre=W_PRE_DEFAULT, w_post=30)
    close = d["close"].to_numpy(float)
    rng = (d["high"] - d["low"]).clip(lower=0).rolling(14, min_periods=1).mean().to_numpy()
    X, y = [], []
    for b in blocks:
        i = b["bar"]
        if i + 30 >= len(close):
            continue
        level = close[i]
        post = close[i + 1: i + 31]
        cd = b["cd"]
        if cd == 1:
            reclaimed = bool((post < level).any())
            fav = float(np.clip((post - level).max(), 0, None))
        else:
            reclaimed = bool((post > level).any())
            fav = float(np.clip((level - post).max(), 0, None))
        thr = 2.0 * (rng[i] if rng[i] > 1e-9 else 1e-9)
        confirm = int((not reclaimed) and fav >= thr)
        X.append(b["X"].astype(np.float32).flatten())
        y.append(confirm)
    return np.array(X), np.array(y, dtype=np.float32)


class NatureHead(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, 64), nn.ReLU(),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 1),
        )
    def forward(self, x):
        return self.net(x).squeeze(-1)


def main():
    X, y = _nature_targets()
    print(f"Muestras naturaleza: {len(X)} | confirm={int(y.sum())} ({100*y.mean():.1f}%)")
    if len(X) < 50:
        print("ERROR: pocas muestras"); return
    n = len(X)
    rng = np.random.RandomState(42)
    idx = rng.permutation(n)
    n_tr = int(n * 0.8)
    tr, te = idx[:n_tr], idx[n_tr:]
    Xtr, ytr = X[tr], y[tr]; Xte, yte = X[te], y[te]
    dim = X.shape[1]
    model = NatureHead(dim)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.BCEWithLogitsLoss()
    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(ytr))
    dl = DataLoader(ds, batch_size=BATCH, shuffle=True)
    t0 = time.time()
    for ep in range(EPOCHS):
        model.train(); tot = 0.0; nb = 0
        for xb, yb in dl:
            opt.zero_grad()
            z = model(xb)
            loss = loss_fn(z, yb)
            loss.backward(); opt.step()
            tot += loss.item() * len(xb); nb += len(xb)
        model.eval()
        with torch.no_grad():
            te_loss = loss_fn(model(torch.from_numpy(Xte)), torch.from_numpy(yte)).item()
        print(f"epoch {ep+1}/{EPOCHS}  train_bce={tot/nb:.4f}  test_bce={te_loss:.4f}  [{time.time()-t0:.0f}s]")
    torch.save({"state": model.state_dict(), "dim": dim,
                "meta": {"target": "bos_confirm vs reclaim (P3)",
                         "n": n, "rate_confirm": float(y.mean()),
                         "note": "encoder P2 plano; input = bloque normalizado flatten"}},
               OUT)
    # Persistir X,y + split para eval instantaneo (evita rebuild de build_tf_blocks)
    np.savez("data/learning/encoder/nature_head_data.npz",
             X=X, y=y, idx=idx, n_tr=n_tr)
    print(f"NATURE HEAD GUARDADO: {OUT}")
    print(f"DATOS GUARDADOS: data/learning/encoder/nature_head_data.npz")
    print("Siguiente: usar P(bos_confirm) para modular el bias del motor.")


if __name__ == "__main__":
    main()
