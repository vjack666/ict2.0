"""B2 — DATASET FACTORY MULTI-PAR (pipeline científico).

Generaliza la generacion de CHOCH real a varios simbolos y TF, produciendo
datasets INMUTABLES con manifest trazable (tu diseno BLOQUE 2):

  data/learning/pipeline/manifests/DS-<id>.json
    {dataset_id, symbol, tf, period, generator_commit, feature_schema,
     label_schema, rows, sha256}

Cada salida features.jsonl se hashea (sha256) para trazabilidad.

NO entrena. Solo genera + registra. Respeta el aislamiento tools/engine.

Sobre el plan original (EURUSD-multitf PRIMERO, luego 8 simbolos): aqui
hacemos EURUSD + 3 pares adicionales (GBPUSD, USDJPY, XAUUSD) en H1/H4/D1
para aislar la variable simbolo tras la variable TF. M5 se excluye del nucleo
estructural (B6+ decidira si se usa para timing).

Reusa la logica de gen_choch_dataset._process_chunk (label_ep/peak/dir).
"""
from __future__ import annotations
import sys, os, json, time, hashlib, subprocess
sys.path.insert(0, ".")
import pandas as pd
import numpy as np

from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.choch import CHOCHTool
from tools.bos_filter import filter_bos_thesis
from tools.choch_quality import mark_choch_quality, FEATURES
from tools.displacement import detect_displacement

MAN_DIR = "data/learning/pipeline/manifests"
OUT_ROOT = "data/learning/choch"
SYMS = ["EURUSD"]  # B2 fase 1: aislar variable TF primero (plan: EURUSD multitf -> luego 8 simbolos)
TFS = ["M5", "H4", "D1"]
FWD = {"M5": 50, "H4": 20, "D1": 10}
K = {"M5": 2.0, "H4": 1.5, "D1": 1.0}
CHUNK = 20000
OVERLAP = 200


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()[:12]
    except Exception:
        return "unknown"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def _process(df, tf, rows):
    out = detect_displacement(df)
    sw = SwingTool(tf=tf).run(out, symbol="X")
    sids = {e.origin_bar: e.id for e in sw}
    bo = BOSTool(lookback=5).run(out, symbol="X", context={"swing_ids": sids})
    bo = apply_validation(out, bo)
    bo = filter_bos_thesis(out, bo, confirm_bars=2, max_idle_bars=0)
    che = CHOCHTool().run(out, symbol="X", context={"swings": sw, "boses": bo})
    # OPCION A (2026-08-20): NO filter_bos_thesis ni is_unique sobre CHOCH (anulaba CHOCH)
    che = mark_choch_quality(out, che, sw, bo, htf_frames={})
    close = out["close"].to_numpy(float)
    rng = (out["high"] - out["low"]).clip(lower=0).rolling(14, min_periods=1).mean().to_numpy()
    n = len(out); fwd = FWD[tf]; kk = K[tf]
    for c in che:
        # OPCION A: NO filtrar por choch_real; incluir todo CHOCH, choch_real como flag
        if c.extra.get("choch_real") is None:
            continue
        i = c.break_bar if c.break_bar is not None else c.bar_index
        if i is None or i < 0 or i > n - fwd - 1:
            continue
        cd = 1 if c.signal == "CHOCH_UP" else -1
        j = i + fwd
        level = c.extra.get("choch_pivot_level")
        inv = False
        if level is not None:
            seg = close[i + 1: j + 1]
            inv = bool((seg < level).any()) if cd == 1 else bool((seg > level).any())
        move = (close[j] - close[i]) * cd
        peak = float(np.clip(((close[i + 1: j + 1] - close[i]) * cd).max(), 0, None))
        thr = kk * (rng[i] if rng[i] > 1e-9 else 1e-9)
        rows.append({
            "tf": tf, "time": str(out["time"].iloc[i]), "signal": c.signal, "cd": cd,
            "score": float(c.extra.get("choch_score", 0)),
            "momentum": int(bool(c.extra.get("choch_momentum"))),
            "after_bos": int(bool(c.extra.get("choch_after_bos"))),
            "displacement": int(bool(c.extra.get("choch_displacement"))),
            "break_body_ratio": float(c.extra.get("choch_break_body_ratio", 0)),
            "label_ep": 1 if (move >= thr and not inv) else 0,
            "label_peak": 1 if (peak >= thr and not inv) else 0,
            "label_dir": 1 if (close[j] - close[i]) * cd > 0 else 0,
        })


def main():
    t0 = time.time()
    os.makedirs(MAN_DIR, exist_ok=True)
    commit = _commit()
    ds_counter = 0
    summary = {"commit": commit, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "datasets": []}
    for sym in SYMS:
        for tf in TFS:
            p = f"data/raw/{sym}/{sym}_{tf}.parquet"
            if not os.path.exists(p):
                continue
            d = pd.read_parquet(p).assign(time=pd.to_datetime(pd.read_parquet(p)["time"]))
            d = d.reset_index(drop=True)
            rows = []
            # por chunks para no explotar memoria
            n = len(d); start = 0
            while start < n:
                end = min(start + CHUNK, n)
                seg = d.iloc[max(0, start - OVERLAP):end].reset_index(drop=True)
                _process(seg, tf, rows)
                start = end
            # dedupe por (tf, signal, time)
            seen = set(); out_rows = []
            for r in rows:
                key = (r["tf"], r["signal"], r["time"])
                if key in seen:
                    continue
                seen.add(key); out_rows.append(r)
            out_dir = os.path.join(OUT_ROOT, sym, tf)
            os.makedirs(out_dir, exist_ok=True)
            fpath = os.path.join(out_dir, "features.jsonl")
            with open(fpath, "w") as f:
                for r in out_rows:
                    f.write(json.dumps(r) + "\n")
            ds_counter += 1
            did = f"DS-{ds_counter:03d}"
            man = {
                "dataset_id": did, "symbol": sym, "tf": tf, "period": "all",
                "generator_commit": commit, "feature_schema": FEATURES,
                "label_schema": ["label_ep", "label_peak", "label_dir"],
                "rows": len(out_rows), "sha256": _sha(fpath),
            }
            json.dump(man, open(os.path.join(MAN_DIR, f"{did}.json"), "w"), indent=2)
            ep_rate = sum(r["label_ep"] for r in out_rows) / max(1, len(out_rows))
            summary["datasets"].append({"id": did, "sym": sym, "tf": tf,
                                         "rows": len(out_rows), "ep_rate": round(ep_rate, 4)})
            print(f"{did} {sym} {tf}: {len(out_rows)} filas | ep+={ep_rate:.1%}")
    json.dump(summary, open(os.path.join(MAN_DIR, "factory_summary.json"), "w"), indent=2)
    print(f"[{time.time()-t0:.0f}s] {ds_counter} datasets -> {MAN_DIR}")


if __name__ == "__main__":
    main()
