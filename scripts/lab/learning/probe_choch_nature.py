"""P3 — Probe de NATURALEZA del CHOCH (responde la hipotesis del usuario).

El usuario piensa: "tras un CHOCH el precio se mueve al lado contrario y lo
confirma un BOS". Este script MIDE eso empiricamente, de forma VECTORIZADA
(rapida, sin loops por bloque ni reconstruccion de pipeline):

Para cada CHOCH (break_bar i, direccion cd):
  - nivel = close[i]
  - ventana post = close[i+1 : i+FWD]
  - BOS confirm : excursion favorable >= K*rango_prom SIN reclaim previo
  - reclaim     : precio cruza de vuelta el nivel (falla el giro)
  - range       : ni confirmo ni reclaim
  - dir_move    : movimiento neto en dir del giro (sanity ~50%)

Usa SOLO los eventos CHOCH del mes 2026-08 (2125 reales + todos los crudos):
suficiente para significancia y evita reprocesar 334k velas cada vez.

NO requiere torch. Requiere pandas/numpy (venv repo).
"""
from __future__ import annotations

import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from tools.choch import CHOCHTool
from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.bos_filter import filter_bos_thesis
from tools.displacement import detect_displacement

SYM = "EURUSD"
TF = "M5"
PARQUET = f"data/raw/{SYM}/{SYM}_{TF}.parquet"
FWD = 50
K = 2.0


def _cho_events():
    d = pd.read_parquet(PARQUET)
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    # Solo 2026-08: suficiente para significancia y evita reprocesar 334k velas
    m = d["time"].dt.strftime("%Y-%m") == "2026-08"
    d = d[m].reset_index(drop=True)
    if len(d) == 0:
        print("ERROR: sin velas 2026-08")
        return d, []
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
        evs.append({"bar": int(bb), "cd": 1 if e.signal == "CHOCH_UP" else -1,
                    "signal": e.signal})
    return d, evs


def main():
    d, evs = _cho_events()
    close = d["close"].to_numpy(dtype=float)
    rng = (d["high"] - d["low"]).clip(lower=0.0).rolling(14, min_periods=1).mean().to_numpy()
    n = len(close)

    # vectorizar: arrays de break_bar y cd
    bars = np.array([e["bar"] for e in evs], dtype=int)
    cds = np.array([e["cd"] for e in evs], dtype=int)
    mask = (bars + FWD) < n
    bars = bars[mask]; cds = cds[mask]
    total = len(bars)
    if total == 0:
        print("ERROR: sin eventos en ventana limpia")
        return

    level = close[bars]
    niv = np.tile(level, (FWD, 1)).T                       # (total, FWD)
    post = np.stack([close[bars + 1 + k] for k in range(FWD)], axis=1)  # (total, FWD)
    thr = np.tile((K * np.where(rng[bars] > 1e-9, rng[bars], 1e-9)).reshape(-1, 1), (1, FWD))

    # reclaim: cruce del nivel en contra
    if cds[0] == 1:  # asumimos mayoría misma dir; manejar por máscara
        reclaimed = np.any(post < niv, axis=1)
        fav = np.clip(post - niv, 0, None).max(axis=1)
        dir_net = (close[np.minimum(bars + FWD, n - 1)] - close[bars]) > 0
    else:
        reclaimed = np.any(post > niv, axis=1)
        fav = np.clip(niv - post, 0, None).max(axis=1)
        dir_net = (close[np.minimum(bars + FWD, n - 1)] - close[bars]) < 0

    # por direccion (cd puede variar)
    up = cds == 1
    dn = cds == -1
    reclaimed_up = np.any(post[up] < niv[up], axis=1) if up.any() else np.array([], bool)
    fav_up = np.clip(post[up] - niv[up], 0, None).max(axis=1) if up.any() else np.array([])
    reclaimed_dn = np.any(post[dn] > niv[dn], axis=1) if dn.any() else np.array([], bool)
    fav_dn = np.clip(niv[dn] - post[dn], 0, None).max(axis=1) if dn.any() else np.array([])

    confirm = np.zeros(total, dtype=bool)
    reclaim = np.zeros(total, dtype=bool)
    cond_fav_up = fav_up >= (K * np.where(rng[bars[up]] > 1e-9, rng[bars[up]], 1e-9))
    cond_fav_dn = fav_dn >= (K * np.where(rng[bars[dn]] > 1e-9, rng[bars[dn]], 1e-9))
    confirm[up] = (~reclaimed_up) & cond_fav_up
    confirm[dn] = (~reclaimed_dn) & cond_fav_dn
    reclaim[up] = reclaimed_up
    reclaim[dn] = reclaimed_dn

    n_confirm = int(confirm.sum())
    n_reclaim = int(reclaim.sum())
    n_range = total - n_confirm - n_reclaim
    n_dir = int(dir_net.sum())

    def pct(x):
        return f"{x/total:.1%}"

    print(f"\n=== NATURALEZA DEL CHOCH (M5 2026-08, n={total}) ===")
    print(f"  BOS confirm (excursion >= {K}rango, sin reclaim): {n_confirm} ({pct(n_confirm)})")
    print(f"  Reclaim (nivel recuperado, falla giro)          : {n_reclaim} ({pct(n_reclaim)})")
    print(f"  Range (ni confirmo ni reclaim)                 : {n_range} ({pct(n_range)})")
    print(f"  Movimiento neto en dir del giro (sanity ~50%)  : {n_dir} ({pct(n_dir)})")
    print(f"\n  TASA DE CONFIRMACION REAL (tu hipotesis): {pct(n_confirm)}")
    print("  (si es <~50%, la narrativa 'siempre confirma con BOS' es falsa")
    print("   y el encoder debe aprender la distribucion, no asumirla)")

    rep = {"tf": TF, "month": "2026-08", "n": total,
           "bos_confirm": n_confirm, "reclaim": n_reclaim, "range": n_range,
           "dir_move": n_dir,
           "rate_confirm": n_confirm / total, "rate_reclaim": n_reclaim / total,
           "rate_range": n_range / total}
    os.makedirs("data/learning/encoder", exist_ok=True)
    with open("data/learning/encoder/choch_nature_report.json", "w") as f:
        json.dump(rep, f, indent=2)
    print("\nReporte: data/learning/encoder/choch_nature_report.json")


if __name__ == "__main__":
    main()
