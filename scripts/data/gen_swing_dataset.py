"""Genera datasets de SWING por TF (M5/H4/D1) para el sistema de aprendizaje.

Fase 3 del plan de jerarquia: la tesis (SPEC §42-47) dice que el sesgo viene
del ULTIMO SWING ESTRUCTURAL MAYOR (D1/H4/H1), no de M5. El dataset previo
tenia 614k swings TODOS M5 y 0 de H4/D1. Este script llena el vacio.

Usa tools/swing.SwingTool con lookback ADAPTATIVO por TF (Fase 1) y marca
estado de vida del nivel (Fase 2: fresh/mitigated via swing_state geometria).

Escribe data/learning/swing/EURUSD_<TF>_<mes>.jsonl (un archivo por mes/TF).
NO usa ATR ni medias (narrative.py:25, SPEC: geometria pura). Sin look-ahead.
"""
from __future__ import annotations
import sys, os, json, time
sys.path.insert(0, ".")
import pandas as pd

from tools.swing import SwingTool

SYM = "EURUSD"
MONTH = "2026-08"
OUT_DIR = f"data/learning/swing"
TFS = ["M5", "H4", "D1"]


def _process(tf: str) -> list[dict]:
    p = f"data/raw/{SYM}/{SYM}_{tf}.parquet"
    if not os.path.exists(p):
        return []
    d = pd.read_parquet(p)
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    m = d["time"].dt.strftime("%Y-%m") == MONTH
    d = d[m].reset_index(drop=True)
    if len(d) == 0:
        return []
    # F1: lookback adaptativo por TF; F2: estado fresh/mitigated cableado
    sw = SwingTool(tf=tf).run(d, symbol=SYM)
    rows = []
    for e in sw:
        rows.append({
            "id": e.id, "tf": tf, "symbol": SYM,
            "time": e.time, "signal": e.signal,
            "origin_bar": e.origin_bar, "confirmation_bar": e.confirmation_bar,
            "price": e.price, "status": e.status,
            "detail": e.detail,
        })
    return rows


def main():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    for tf in TFS:
        rows = _process(tf)
        path = os.path.join(OUT_DIR, f"{SYM}_{tf}_{MONTH}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        total += len(rows)
        print(f"{tf}: {len(rows)} swings -> {path}")
    summ = {"month": MONTH, "total": total,
            "by_tf": {tf: len(_process(tf)) for tf in TFS}}
    with open(os.path.join(OUT_DIR, f"{SYM}_swing_summary_{MONTH}.json"), "w") as f:
        json.dump(summ, f, indent=2)
    print(f"TOTAL swings: {total} [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
