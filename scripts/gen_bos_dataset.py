"""Genera dataset de features de BOS para etiquetado humano (paralelo a gen_choch_dataset).

Para cada BOS (EURUSD M5/H4/D1) extrae las 4 features de calidad geometrica
de tools/quality_score.py (rescatado de SMC-SYSTEMS/engine/bos/structure.py::
_compute_bos_quality) + estado de tools/bos_validate.py:

  displacement_prev : displacement previo en la direccion del break
  body_ratio       : cuerpo de la vela de break / rango de esa vela
  dist_to_level    : distancia del close al nivel roto / rango prom (cap 1)
  confirmed        : no retorno inmediato (confirm_bars cierres)
  status           : active / invalidated (bos_validate)

Persiste data/learning/bos/<aaaamm>/features.jsonl + resumen. Esto habilita
que scripts/label_human.py aplique tools/teacher_rubric.score_bos_rubric y
llene human_score de BOS SIN que el humano lo haga a mano.

NO usa labels de mercado (eso es el modelo de naturaleza). Solo geometria
pura + estado, igual que la rubric ICT (ICT_RULEBOOK §2, sin indicadores).
"""
from __future__ import annotations
import sys, os, json, time
sys.path.insert(0, ".")
import pandas as pd
import numpy as np

from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.bos_filter import filter_bos_thesis
from tools.displacement import detect_displacement, DisplacementConfig
from tools.quality_score import compute_quality, QualityConfig

SYM = "EURUSD"
MONTH = "2026-08"
OUT_DIR = f"data/learning/bos/{MONTH}"
BOS_W = {"M5": 50, "H4": 20, "D1": 10}


def _process(tf: str) -> list[dict]:
    p = f"data/raw/{SYM}/{SYM}_{tf}.parquet"
    if not os.path.exists(p):
        return []
    d = pd.read_parquet(p)
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    out = detect_displacement(d, DisplacementConfig())
    sw = SwingTool(lookback=5).run(out, symbol=SYM)
    sids = {e.origin_bar: e.id for e in sw}
    bo = BOSTool(lookback=5).run(out, symbol=SYM, context={"swing_ids": sids})
    bo = apply_validation(out, bo)
    bo = filter_bos_thesis(out, bo, confirm_bars=2, max_idle_bars=0)

    bos_dir = np.zeros(len(d), dtype=int)
    bos_level = np.full(len(d), np.nan)
    for e in bo:
        bb = e.break_bar if e.break_bar is not None else e.bar_index
        if bb is None:
            continue
        bos_dir[bb] = 1 if e.signal == "BOS_UP" else -1
        bos_level[bb] = e.price
    dfq = d.copy()
    dfq["bos_dir"] = bos_dir
    dfq["bos_level"] = bos_level
    quality, real = compute_quality(dfq, config=QualityConfig())
    status = {e.id: e.status for e in bo}

    close = d["close"].to_numpy()
    rng = (d["high"] - d["low"]).clip(lower=0.0).rolling(14, min_periods=1).mean().to_numpy()
    body = (d["close"] - d["open"]).abs().to_numpy()
    cr = (d["high"] - d["low"]).replace(0, np.nan).to_numpy()
    body_ratio = np.where(np.isfinite(cr), body / cr, 0.0)

    rows = []
    for e in bo:
        bb = e.break_bar if e.break_bar is not None else e.bar_index
        if bb is None:
            continue
        direction = 1 if e.signal == "BOS_UP" else -1
        lvl = float(e.price)
        if np.isnan(lvl) or rng[bb] <= 1e-9:
            dist = 0.0
        else:
            dist = float(min(1.0, abs(close[bb] - lvl) / rng[bb]))
        rows.append({
            "symbol": SYM, "tf": tf,
            "time": str(d["time"].iloc[bb]),
            "bar": int(bb), "signal": e.signal, "cd": direction,
            "displacement_prev": bool(d.get(f"displacement_{'bullish' if direction == 1 else 'bearish'}", pd.Series(False, index=d.index)).iloc[bb]) if f"displacement_{'bullish' if direction == 1 else 'bearish'}" in d.columns else False,
            "body_ratio": float(body_ratio[bb]),
            "dist_to_level": dist,
            "confirmed": bool(real.iloc[bb]) if bb < len(real) else False,
            "status": e.status,
        })
    return rows


def main():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    all_rows = []
    for tf in ("M5", "H4", "D1"):
        r = _process(tf)
        all_rows.extend(r)
        print(f"{tf}: {len(r)} BOS -> features")
    path = os.path.join(OUT_DIR, "features.jsonl")
    with open(path, "w") as f:
        for x in all_rows:
            f.write(json.dumps(x) + "\n")
    summ = {"n": len(all_rows),
            "by_tf": {tf: sum(1 for x in all_rows if x["tf"] == tf) for tf in ("M5", "H4", "D1")},
            "by_status": {s: sum(1 for x in all_rows if x["status"] == s) for s in ("active", "invalidated")}}
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summ, f, indent=2)
    print(f"TOTAL BOS: {len(all_rows)} -> {path}  [{time.time()-t0:.0f}s]")
    print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
