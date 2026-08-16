"""P2 — Entrena el ENCODER de bloque de velas (el "ojo" auto-supervisado).

Objetivo: aprender el COMPORTAMIENTO y la NATURALEZA del patron CHOCH desde
las velas crudas, SIN labels humanos. Auto-supervision por reconstruccion de
la ventana futura cercana: el encoder ve [-W_pre, break] y debe reconstruir
[break+1, break+W_post]. Si logra reconstruir el movimiento inmediato tras
el evento, ha captado la dinamica local del bloque.

NO hay look-ahead en inferencia: el target (ventana futura) SOLO se usa como
supervisor en entrenamiento; el encoder en produccion recibe unico el input
causal X.

Arquitectura (ligera, CPU-friendly, pocos params -> anti-overfit):
  Input (60,7) -> Conv1d(7->32, k=5) -> ReLU -> MaxPool(2)
                -> Conv1d(32->64, k=3) -> ReLU -> MaxPool(2)
                -> GlobalAvgPool -> z (64,)
  Decoder: Linear(64 -> 30*7) -> reshape (30,7)  (reconstruye y_win)

Persiste: data/learning/encoder/chooch_encoder.pt  (solo el encoder)
          data/learning/encoder/encoder_meta.json  (shapes, norm_feats)

Uso: el embedding z alimenta luego los heads (rubric humana + naturaleza),
reemplazando las 11 features aplanadas de tools/choch_quality.py.

Requiere torch (pip install torch --index-url ... cpu). Si no esta, el script
avisa y sale sin corromper nada.
"""
from __future__ import annotations

import os
import sys
import json
import glob
import time
import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from tools.block_builder import build_tf_blocks, NORM_FEATS, W_PRE_DEFAULT, W_POST_DEFAULT

SYM = "EURUSD"
TF = "M5"
PARQUET = f"data/raw/{SYM}/{SYM}_{TF}.parquet"
OUT_DIR = "data/learning/encoder"
W_PRE = W_PRE_DEFAULT
W_POST = W_POST_DEFAULT
BATCH = 256
EPOCHS = 8
LR = 1e-3
EMB_DIM = 64
SEED = 42

os.makedirs(OUT_DIR, exist_ok=True)


def _collect_blocks() -> list[dict]:
    """Recolecta bloques CHOCH de TODO el historico M5 usando el pipeline tools/."""
    # Reusa los detectores aislados (sin el scorer, solo estructura)
    from tools.choch import CHOCHTool
    from tools.swing import SwingTool
    from tools.bos import BOSTool
    from tools.bos_validate import apply_validation
    from tools.bos_filter import filter_bos_thesis
    from tools.displacement import detect_displacement

    d = pd.read_parquet(PARQUET)
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    out = detect_displacement(d)
    sw = SwingTool(lookback=5).run(out, symbol=SYM)
    sids = {e.origin_bar: e.id for e in sw}
    bo = BOSTool(lookback=5).run(out, symbol=SYM, context={"swing_ids": sids})
    bo = apply_validation(out, bo)
    bo = filter_bos_thesis(out, bo, confirm_bars=2, max_idle_bars=0)
    che = CHOCHTool().run(out, symbol=SYM, context={"swings": sw, "boses": bo})
    evs = []
    for e in che:
        bb = e.break_bar if e.break_bar is not None else e.bar_index
        if bb is None:
            continue
        evs.append({"break_bar": int(bb), "signal": e.signal, "tf": TF,
                    "symbol": SYM, "time": str(d["time"].iloc[bb])})
    print(f"[collect] {len(evs)} eventos CHOCH crudos M5")
    blocks = build_tf_blocks(PARQUET, evs, w_pre=W_PRE, w_post=W_POST)
    print(f"[collect] {len(blocks)} bloques causales unicos (zona limpia)")
    return blocks


def _to_arrays(blocks):
    X = np.stack([b["X"] for b in blocks]).astype(np.float32)   # (N,60,7)
    Y = np.stack([b["y_win"] for b in blocks]).astype(np.float32)  # (N,30,7)
    return X, Y


def main():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as e:
        print(f"ERROR: torch no disponible ({e}). Instala: pip install torch (CPU). "
              f"El encoder NO se entreno; no se corrompio nada.")
        return

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    blocks = _collect_blocks()
    if len(blocks) < 50:
        print(f"ERROR: pocos bloques ({len(blocks)}); aborta sin escribir.")
        return
    X, Y = _to_arrays(blocks)
    # split 90/10 (el holdout lo usamos para reconstruccion en test)
    n = len(X)
    rng = np.random.RandomState(SEED)
    idx = rng.permutation(n)
    n_tr = int(n * 0.9)
    tr, te = idx[:n_tr], idx[n_tr:]
    Xtr, Ytr = X[tr], Y[tr]
    Xte, Yte = X[te], Y[te]

    class Encoder(nn.Module):
        def __init__(self, n_feat=7, emb=EMB_DIM):
            super().__init__()
            self.conv1 = nn.Conv1d(n_feat, 32, kernel_size=5)
            self.pool1 = nn.MaxPool1d(2)
            self.conv2 = nn.Conv1d(32, 64, kernel_size=3)
            self.pool2 = nn.MaxPool1d(2)
            self.adapt = nn.AdaptiveAvgPool1d(1)
            self.proj = nn.Linear(64, emb)

        def forward(self, x):
            # x: (B, W, F) -> (B, F, W)
            x = x.transpose(1, 2)
            x = self.pool1(torch.relu(self.conv1(x)))
            x = self.pool2(torch.relu(self.conv2(x)))
            x = self.adapt(x).squeeze(-1)
            return self.proj(x)

    class Decoder(nn.Module):
        def __init__(self, emb=EMB_DIM, w_post=W_POST, n_feat=7):
            super().__init__()
            self.w_post = w_post
            self.n_feat = n_feat
            self.fc = nn.Linear(emb, w_post * n_feat)

        def forward(self, z):
            return self.fc(z).view(-1, self.w_post, self.n_feat)

    enc = Encoder()
    dec = Decoder()
    params = list(enc.parameters()) + list(dec.parameters())
    opt = torch.optim.Adam(params, lr=LR)
    loss_fn = nn.MSELoss()

    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(Ytr))
    dl = DataLoader(ds, batch_size=BATCH, shuffle=True)
    t0 = time.time()
    for ep in range(EPOCHS):
        enc.train(); dec.train()
        tot = 0.0; nb = 0
        for xb, yb in dl:
            opt.zero_grad()
            z = enc(xb)
            yhat = dec(z)
            loss = loss_fn(yhat, yb)
            loss.backward()
            opt.step()
            tot += loss.item() * len(xb); nb += len(xb)
        # test recon
        enc.eval(); dec.eval()
        with torch.no_grad():
            zte = enc(torch.from_numpy(Xte))
            yhte = dec(zte)
            te_loss = loss_fn(yhte, torch.from_numpy(Yte)).item()
        print(f"epoch {ep+1}/{EPOCHS}  train_mse={tot/nb:.5f}  test_mse={te_loss:.5f}  [{time.time()-t0:.0f}s]")

    # Persistir SOLO el encoder (el consumidor en produccion)
    enc.eval()
    path = os.path.join(OUT_DIR, "chooch_encoder.pt")
    torch.save({"encoder_state": enc.state_dict(),
                "meta": {"w_pre": W_PRE, "w_post": W_POST,
                         "n_feat": len(NORM_FEATS), "emb_dim": EMB_DIM,
                         "norm_feats": NORM_FEATS,
                         "trained_on": f"{SYM} {TF} 2022-2026",
                         "n_blocks": n, "test_mse": float(te_loss)}},
               path)
    meta = {"path": path, "w_pre": W_PRE, "w_post": W_POST,
            "n_feat": len(NORM_FEATS), "emb_dim": EMB_DIM,
            "norm_feats": NORM_FEATS, "n_blocks": n,
            "test_mse": float(te_loss),
            "generated_utc": datetime.datetime.utcnow().isoformat() + "Z"}
    with open(os.path.join(OUT_DIR, "encoder_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"ENCODER GUARDADO: {path}")
    print(f"test_mse (reconstruccion ventana futura): {te_loss:.5f}")
    print("Siguiente: scripts/probe_choch_nature.py usa z para medir tu hipotesis.")


if __name__ == "__main__":
    main()
