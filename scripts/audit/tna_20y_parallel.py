"""TNA 20Y — Temporal Navigation Audit (parallel, 20 cores).

Emite TNA-TRACE-INTEGRITY (anti-lookahead: asof_bar <= decision index en cada
capa) y TNA-BEHAVIORAL (duracion por estado, distribucion de bias, zonas, paths).

Usa multiprocessing.Pool(N_CORES) sobre barras H1 completas (124k). Cada worker
crea su propio MTFNavigator (init ~17s, en paralelo) y navega su lote.

Policy: CONTEXT_STATE_NOT_ENTRY. No PnL.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import engine.mtf_navigation as M
from audits.codigo.mtf_seq_funnel import _load_tf

N_CORES = 20
OUT = Path("reports/audits/tna_20y.json")

_frames = None


def _init_worker(frames):
    global _frames
    _frames = frames


def _worker(times_chunk):
    nav = M.MTFNavigator(_frames, M.NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))
    rows = []
    for t in times_chunk:
        st = nav.navigate(t, exec_tf="H1")
        layers = st.layers
        # TRACE-INTEGRITY: cada layer asof_bar <= decision index en su capa
        ok_asof = True
        for lyr, snap in layers.items():
            df = _frames.get(lyr)
            if df is not None and snap is not None:
                di = int(df["time"].searchsorted(pd.Timestamp(t), side="right") - 1)
                if snap.asof_bar > di:
                    ok_asof = False
        rows.append({
            "status": st.status,
            "layers": list(layers.keys()),
            "bias_d1": layers.get("D1").structure_bias.value if layers.get("D1") else None,
            "bias_h4": layers.get("H4").structure_bias.value if layers.get("H4") else None,
            "bias_h1": layers.get("H1").structure_bias.value if layers.get("H1") else None,
            "n_zones": sum(len(s.zones) for s in layers.values()),
            "path_len": len(st.path.steps),
            "asof_ok": ok_asof,
        })
    return rows


def main():
    print(f"loading frames...", flush=True)
    t0 = time.time()
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    print(f"loaded in {time.time()-t0:.1f}s; H1 bars={len(h1)}", flush=True)

    times = [h1["time"].iloc[i] for i in range(0, len(h1), 1)]  # todas las barras H1
    # chunk por core
    chunk = max(1, len(times) // N_CORES)
    chunks = [times[i:i + chunk] for i in range(0, len(times), chunk)]
    print(f"navigating {len(times)} bars over {N_CORES} cores in {len(chunks)} chunks...", flush=True)

    t1 = time.time()
    import multiprocessing as mp
    with mp.Pool(N_CORES, initializer=_init_worker, initargs=(frames,)) as pool:
        results = pool.map(_worker, chunks)
    elapsed = time.time() - t1
    print(f"navigation done in {elapsed:.1f}s ({elapsed/len(times)*1000:.2f} ms/bar effective)", flush=True)

    rows = [r for sub in results for r in sub]

    # TRACE-INTEGRITY
    asof_viol = sum(1 for r in rows if not r["asof_ok"])
    trace_integrity = asof_viol == 0

    # BEHAVIORAL
    status_c = Counter(r["status"] for r in rows)
    bias_d1_c = Counter(r["bias_d1"] for r in rows)
    bias_h1_c = Counter(r["bias_h1"] for r in rows)
    layer_c = Counter(tuple(sorted(r["layers"])) for r in rows)
    avg_zones = sum(r["n_zones"] for r in rows) / len(rows)
    avg_path = sum(r["path_len"] for r in rows) / len(rows)

    report = {
        "audit": "TNA_20Y",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": "CONTEXT_STATE_NOT_ENTRY",
        "n_bars": len(rows),
        "cores": N_CORES,
        "elapsed_s": round(elapsed, 1),
        "gates": {
            "TNA_TRACE_INTEGRITY": "PASS" if trace_integrity else "FAIL",
            "TNA_BEHAVIORAL": "PASS" if status_c.get("OK", 0) > 0 else "FAIL",
        },
        "trace_integrity": {
            "asof_violations": asof_viol,
            "asof_ok_rate": 1.0 - asof_viol / len(rows),
        },
        "behavioral": {
            "status_distribution": dict(status_c),
            "bias_d1_distribution": dict(bias_d1_c),
            "bias_h1_distribution": dict(bias_h1_c),
            "layer_combinations": {str(k): v for k, v in layer_c.most_common(10)},
            "avg_zones_per_state": round(avg_zones, 2),
            "avg_path_steps": round(avg_path, 2),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str), flush=True)
    print(f"TNA REPORT: {report['gates']}", flush=True)


if __name__ == "__main__":
    main()
