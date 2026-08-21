"""FASE 2 — revalidar secuencia del funnel 20Y en engine-seq-v2-causal.

Corre run_sequential (fix PIT) sobre H1 20Y y reporta la distribucion:
chains, unique_setups (colapsado por dir+stages+nivel), COMPLETE, depth, status.
Compara contra v1 baseline (1460 chains, 3 COMPLETE) para ver el impacto de PIT.

Escribe reports/audits/experiments/fvg_ob/funnel_v2_seq_20Y.json (NO toca reportes v1 de Grok).
"""
from __future__ import annotations
import time, json
from collections import Counter
from pathlib import Path
import pandas as pd
import numpy as np
import engine.sequential_events as SE
from audits.codigo.mtf_seq_funnel import _load_tf

OUT = Path("reports/audits/experiments/fvg_ob/funnel_v2_seq_20Y.json")
t0 = time.time()
print("loading H1...", flush=True)
h1 = _load_tf("H1")
print(f"  H1 barras={len(h1)} {round(time.time()-t0,1)}s", flush=True)

cfg = SE.SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
print("run_sequential (v2 PIT)...", flush=True)
ch = SE.run_sequential(h1, cfg, symbol="EURUSD", timeframe="H1")
print(f"  chains={len(ch)} {round(time.time()-t0,1)}s", flush=True)

def key(ch):
    nodes = ch.nodes
    lv = [n.level for n in nodes if n.level is not None]
    lvl = round(float(np.mean(lv)), 4) if lv else 0.0
    return (int(ch.direction), tuple(n.stage.value for n in nodes), lvl)

uks = Counter(key(c) for c in ch)
status = Counter(c.status for c in ch)
depth = Counter(len(c.nodes) for c in ch)
complete = [c for c in ch if c.status == "COMPLETE"]

report = {
    "engine": "engine-seq-v2-causal (PIT fix in _build_eq_pools)",
    "symbol": "EURUSD",
    "tf": "H1",
    "span": "20Y dukascopy",
    "n_bars": len(h1),
    "chains": len(ch),
    "unique_setups": len(uks),
    "complete": len(complete),
    "status": dict(status),
    "depth_dist": {str(k): v for k, v in sorted(depth.items())},
    "complete_stage_signatures": [tuple(n.stage.value for n in c.nodes) for c in complete[:20]],
    "baseline_v1": {"chains": 1460, "complete": 3},
    "ratio_vs_v1": round(len(ch) / 1460, 2),
    "elapsed_s": round(time.time() - t0, 1),
    "gate": {
        "chains_positive": len(ch) > 0,
        "has_complete": len(complete) >= 1,
        "not_explosive": len(ch) < 50000,
    },
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2, default=str))
print(json.dumps(report, indent=2), flush=True)
print("GATE:", "PASS" if all(report["gate"].values()) else "FAIL", flush=True)
print(f"JSON -> {OUT}", flush=True)
