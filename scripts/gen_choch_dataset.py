"""Genera dataset de CHOCH para calibracion por IA (F4/F5).

Para cada CHOCH REAL (gate abierto A) en M5/H4/D1, extrae features del
score hibrido y un LABEL objetivo de mercado:
  importo = en las N velas posteriores el precio se movio >= k*rango_prom
           en la direccion del giro Y el CHOCH no fue invalidado.

Label es evidencia de mercado (no causa), trazable y reproducible.
Persiste data/learning/choch/YYYY-MM/features.jsonl.
"""
from __future__ import annotations
import sys, os, json
sys.path.insert(0, ".")
import pandas as pd
import numpy as np
from detectors.trend import detect_trend
from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.choch import CHOCHTool
from tools.bos_filter import filter_bos_thesis
from tools.choch_quality import mark_choch_quality
from tools.displacement import detect_displacement

SYM = "EURUSD"
END = "2026-08-14"
TFS = {"M5": 6540, "H4": 1500, "D1": 800}  # velas aprox 1 mes / hist
FWD = {"M5": 50, "H4": 20, "D1": 10}       # velas posteriores a evaluar
K = {"M5": 2.0, "H4": 1.5, "D1": 1.0}      # multiplicador rango promedio


def build(tf: str):
    d = pd.read_parquet(f"data/raw/{SYM}/{SYM}_{tf}.parquet")
    d["time"] = pd.to_datetime(d["time"])
    m = d[d["time"] <= END].tail(TFS[tf]).reset_index(drop=True)
    htf = {f: detect_trend(pd.read_parquet(f"data/raw/{SYM}/{SYM}_{f}.parquet"))
           for f in ("H4", "D1") if f != tf} or {"H4": detect_trend(pd.read_parquet(f"data/raw/{SYM}/{SYM}_H4.parquet"))}
    out = m.copy().reset_index(drop=True)
    out = detect_displacement(out)
    sw = SwingTool(lookback=5); swe = sw.run(out, symbol=SYM)
    sids = {e.origin_bar: e.id for e in swe}
    bo = BOSTool(lookback=5); boe_raw = bo.run(out, symbol=SYM, context={"swing_ids": sids})
    boe_raw = apply_validation(out, boe_raw)
    boe = filter_bos_thesis(out, boe_raw, confirm_bars=2, max_idle_bars=0)
    ch = CHOCHTool(); che = ch.run(out, symbol=SYM, context={"swings": swe, "boses": boe})
    che = filter_bos_thesis(out, che, confirm_bars=2, max_idle_bars=0)
    che = mark_choch_quality(out, che, swe, boe_raw, htf_frames=htf)

    close = out["close"].to_numpy()
    rng = (out["high"] - out["low"]).clip(lower=0).rolling(14, min_periods=1).mean().to_numpy()
    n = len(out)
    rows = []
    for c in che:
        if not c.extra.get("choch_real"):
            continue
        i = c.break_bar if c.break_bar is not None else c.bar_index
        if i is None or i < 0 or i >= n:
            continue
        cd = 1 if c.signal == "CHOCH_UP" else -1
        j = min(i + FWD[tf], n - 1)
        if j <= i:
            continue
        move = (close[j] - close[i]) * cd
        thr = K[tf] * (rng[i] if rng[i] > 1e-9 else 1e-9)
        invalidated = c.status == "invalidated"
        label = 1 if (move >= thr and not invalidated) else 0
        rows.append({
            "symbol": SYM, "tf": tf,
            "time": str(out["time"].iloc[i]),
            "bar": int(i),
            "signal": c.signal,
            "score": float(c.extra.get("choch_score", 0)),
            "momentum": int(bool(c.extra.get("choch_momentum"))),
            "after_bos": int(bool(c.extra.get("choch_after_bos"))),
            "displacement": int(bool(c.extra.get("choch_displacement"))),
            "htf_ctx": c.extra.get("choch_htf_ctx", "neutral"),
            "real": int(bool(c.extra.get("choch_real"))),
            "label": label,
            "move": float(move),
        })
    return rows


if __name__ == "__main__":
    os.makedirs("data/learning/choch/2026-08", exist_ok=True)
    all_rows = []
    for tf in TFS:
        r = build(tf)
        all_rows.extend(r)
        print(f"{tf}: {len(r)} CHOCH REAL, labels=1: {sum(x['label'] for x in r)}")
    path = "data/learning/choch/2026-08/features.jsonl"
    with open(path, "w") as f:
        for x in all_rows:
            f.write(json.dumps(x) + "\n")
    print(f"TOTAL: {len(all_rows)} -> {path}")
