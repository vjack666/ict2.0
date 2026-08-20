"""Genera dataset de CHOCH REAL para calibracion por IA (usa TODA la data).

Para cada CHOCH REAL en M5/H4/D1 extrae features del score hibrido + extras
y LABELS objetivos de mercado (trazables, no subjetivos):

  label_ep   : en las N velas posteriores el precio cerró >= k*rango_prom en
               la direccion del giro Y el CHOCH no fue invalidado (spec).
  label_peak : el excursion favorable MAXIMO en las N velas >= k*rango_prom Y
               no invalidado (más tolerante: captura oportunidad real).
  label_dir  : el movimiento neto N velas fue en la direccion del giro
               (sanity, base ~50%).

Invalidacion: CHOCH_UP rompio LH (un high); invalidado si un cierre posterior
cae bajo ese nivel. CHOCH_DOWN rompio HL; invalidado si cierre sube sobre nivel.

M5 (334k velas) se procesa por CHUNKS de ~20000 con solapamiento de lead-in
para no explotar memoria ni cortar swings/BOS en el borde.

Persiste data/learning/choch/<aaaamm>/features.jsonl (append) y un resumen.
"""
from __future__ import annotations
import sys, os, json, time
# La generacion de dataset debe usar SIEMPRE el score geometrico (sin modelo IA)
# para que las features de entrenamiento sean estables.
os.environ.setdefault("CHOCH_IA_DISABLE", "1")
sys.path.insert(0, ".")
import pandas as pd
import numpy as np
from detectors.trend import detect_trend
from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.choch import CHOCHTool
from tools.bos_filter import filter_bos_thesis
from tools.choch_quality import mark_choch_quality, FEATURES
from tools.displacement import detect_displacement

SYM = "EURUSD"
MONTH = "full"
OUT_DIR = f"data/learning/choch/{MONTH}"
FWD = {"M5": 50, "H4": 20, "D1": 10}        # velas posteriores a evaluar
K = {"M5": 2.0, "H4": 1.5, "D1": 1.0}      # multiplicador rango promedio
CHUNK = {"M5": 20000, "H4": 20000, "D1": 20000}
OVERLAP = {"M5": 200, "H4": 200, "D1": 200}
# frames HTF de contexto por tf (None = sin contexto)
HTF_CTX = {
    "M5": ("H4", "D1"),
    "H4": ("D1",),
    "D1": (),
}


def _trend_df(tf: str) -> pd.DataFrame:
    d = pd.read_parquet(f"data/raw/{SYM}/{SYM}_{tf}.parquet")
    d = d.assign(time=pd.to_datetime(d["time"]))
    return detect_trend(d)


def _process_chunk(seg: pd.DataFrame, tf: str, htf: dict, g0: int, rows: list):
    out = detect_displacement(seg)
    sw = SwingTool(lookback=5); swe = sw.run(out, symbol=SYM)
    sids = {e.origin_bar: e.id for e in swe if e.origin_bar is not None}
    bo = BOSTool(lookback=5); boe_raw = bo.run(out, symbol=SYM, context={"swing_ids": sids, "swings": swe})
    boe_raw = apply_validation(out, boe_raw)
    boe = filter_bos_thesis(out, boe_raw, confirm_bars=2, max_idle_bars=0)
    # FIX 2026-08-17: BOS únicos hacia CHOCH (evita padres/flood contaminados)
    boe = [e for e in boe if e.extra.get("is_unique") is True]
    ch = CHOCHTool(); che = ch.run(out, symbol=SYM, context={"swings": swe, "boses": boe})
    # OPCION A (2026-08-20): anti-flood is_unique SOLO en BOS (arriba), NO en CHOCH.
    # filter_bos_thesis aplica reglas de tesis BOS (HTF align/confirm) que anulan CHOCH
    # (0/572 pasaban thesis_valid). CHOCH conserva geometria + choch_real de mark_choch_quality.
    che = mark_choch_quality(out, che, swe, boe_raw, htf_frames=htf)

    close = out["close"].to_numpy()
    rng = (out["high"] - out["low"]).clip(lower=0.0).rolling(14, min_periods=1).mean().to_numpy()
    n = len(out)
    fwd = FWD[tf]
    kk = K[tf]
    # region limpia (excluye lead-in y cola sin ventana de label)
    lo = OVERLAP[tf]
    hi = n - fwd - 1

    for c in che:
        # OPCION A (2026-08-20): NO filtrar por choch_real aqui. Se incluye TODO CHOCH
        # detectado y choch_real queda como feature/flag para que B1 (label audit)
        # decida la definicion real. Antes este `continue` mataba 562/571 CHOCH.
        if c.extra.get("choch_real") is None:
            continue
        i = c.break_bar if c.break_bar is not None else c.bar_index
        if i is None or i < 0:
            continue
        # de-duplicacion por (tf, gbar, signal)
        gbar = g0 + i
        cd = 1 if c.signal == "CHOCH_UP" else -1
        if i < lo or i > hi:
            continue
        level = c.extra.get("choch_pivot_level")
        j = min(i + fwd, n - 1)
        if j <= i:
            continue
        # invalidacion en la ventana
        inv = False
        if level is not None:
            seg_close = close[i + 1: j + 1]
            if cd == 1:
                inv = bool((seg_close < level).any())
            else:
                inv = bool((seg_close > level).any())
        move = (close[j] - close[i]) * cd
        peak_fav = 0.0
        if j > i:
            window = (close[i + 1: j + 1] - close[i]) * cd
            peak_fav = float(np.clip(window.max(), 0, None))
        thr = kk * (rng[i] if rng[i] > 1e-9 else 1e-9)
        label_ep = 1 if (move >= thr and not inv) else 0
        label_peak = 1 if (peak_fav >= thr and not inv) else 0
        label_dir = 1 if (close[j] - close[i]) * cd > 0 else 0

        ctx = c.extra.get("choch_htf_ctx", "neutral")
        ctx_code = {"contra": 0, "neutral": 1, "a_favor": 2}.get(ctx, 1)
        rows.append({
            "symbol": SYM, "tf": tf,
            "time": str(out["time"].iloc[i]),
            "gbar": int(gbar),
            "bar": int(i),
            "signal": c.signal,
            "cd": cd,
            "score": float(c.extra.get("choch_score", 0)),
            "score_n": float(c.extra.get("choch_score", 0)) / 100.0,
            "momentum": int(bool(c.extra.get("choch_momentum"))),
            "after_bos": int(bool(c.extra.get("choch_after_bos"))),
            "displacement": int(bool(c.extra.get("choch_displacement"))),
            "htf_ctx": ctx,
            "htf_ctx_code": ctx_code,
            "htf_trend_int": int(c.extra.get("choch_htf_trend_int", 0)),
            "break_body_ratio": float(c.extra.get("choch_break_body_ratio", 0)),
            "dist_to_level": float(c.extra.get("choch_dist_to_level", 0)),
            "bos_age_bars": int(c.extra.get("choch_bos_age_bars", -1) or -1),
            "tf_code": {"M5": 0, "H4": 1, "D1": 2}.get(tf, 0),
            "real": int(True),
            "label_ep": label_ep,
            "label_peak": label_peak,
            "label_dir": label_dir,
            "move_ep": float(move),
            "peak_fav": peak_fav,
            "avg_range": float(rng[i]),
        })


def build_tf(tf: str, htf_all: dict, seen: set):
    d = pd.read_parquet(f"data/raw/{SYM}/{SYM}_{tf}.parquet")
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    n = len(d)
    htf = {h: htf_all[h] for h in HTF_CTX[tf] if h in htf_all}
    chunk = CHUNK[tf]
    rows = []
    start = 0
    while start < n:
        end = min(start + chunk, n)
        seg = d.iloc[max(0, start - OVERLAP[tf]): end].reset_index(drop=True)
        g0 = max(0, start - OVERLAP[tf])
        _process_chunk(seg, tf, htf, g0, rows)
        start = end
    # dedupe
    out_rows = []
    for r in rows:
        key = (r["tf"], r["gbar"], r["signal"])
        if key in seen:
            continue
        seen.add(key)
        out_rows.append(r)
    return out_rows


def main():
    t0 = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    htf_all = {}
    if os.path.exists(f"data/raw/{SYM}/{SYM}_H4.parquet"):
        htf_all["H4"] = _trend_df("H4")
    if os.path.exists(f"data/raw/{SYM}/{SYM}_D1.parquet"):
        htf_all["D1"] = _trend_df("D1")

    seen = set()
    all_rows = []
    for tf in ("M5", "H4", "D1"):
        r = build_tf(tf, htf_all, seen)
        all_rows.extend(r)
        le = sum(x["label_ep"] for x in r)
        lp = sum(x["label_peak"] for x in r)
        ld = sum(x["label_dir"] for x in r)
        print(f"{tf}: {len(r)} CHOCH REAL | label_ep=1:{le} ({le/max(1,len(r)):.1%}) "
              f"label_peak=1:{lp} ({lp/max(1,len(r)):.1%}) label_dir=1:{ld} ({ld/max(1,len(r)):.1%}) "
              f"[{time.time()-t0:.0f}s]")

    path = os.path.join(OUT_DIR, "features.jsonl")
    with open(path, "w") as f:
        for x in all_rows:
            f.write(json.dumps(x) + "\n")
    # resumen
    summ = {
        "n": len(all_rows),
        "label_ep_rate": sum(x["label_ep"] for x in all_rows) / max(1, len(all_rows)),
        "label_peak_rate": sum(x["label_peak"] for x in all_rows) / max(1, len(all_rows)),
        "label_dir_rate": sum(x["label_dir"] for x in all_rows) / max(1, len(all_rows)),
        "by_tf": {tf: sum(1 for x in all_rows if x["tf"] == tf) for tf in ("M5", "H4", "D1")},
        "features": FEATURES,
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summ, f, indent=2)
    print(f"TOTAL: {len(all_rows)} -> {path}  [{time.time()-t0:.0f}s]")
    print("RESUMEN:", json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
