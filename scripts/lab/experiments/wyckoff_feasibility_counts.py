"""Conteos de factibilidad EXP-WYCKOFF-ICT-01 — VERSION CORREGIDA (post-auditoria).

Solo conteos; SIN outcomes ni significancia. Corrige las fallas senaladas en la
auditoria externa:

1. Ancla = barra del nodo k (nodes[k].bar), NO created_bar (que es LIQUIDITY_POOL).
2. Deduplicacion por (bar_k, direction) como exige CONTRATO_DATASET_SEQ_CTX_01.md §5.
3. context_bucket RELATIVO a sequence_direction (funcion autoritativa del
   generator exp_seq_ctx_01_dataset.context_bucket), NO BULLISH->ALIGNED.
4. Contabiliza el flag CONFLICT del WyckoffSnapshot y la celda primaria
   ICT_ALIGNED x CONFLICT vs NON_CONFLICT (y analogo AGAINST), segun
   EXP_WYCKOFF_ICT_01_PREREGISTRATION.md §4.

Unidad de observacion: nodo k de SequentialChain (k>=MIN_DEPTH), anclado en su
barra. PIT: navigate(t) sobre MTFNavigator (gate causal FULL==PREFIX PASS).

NOTA DE PROCEDENCIA: este script se commitea y luego se ejecuta; el
generator_commit del JSON es el commit REAL de ejecucion, no a20c66a.
"""
from __future__ import annotations
import json, time, sys, hashlib
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engine.mtf_navigation as M
import engine.sequential_events as SE
from audits.codigo.mtf_seq_funnel import _load_tf
from engine.Wyckoff.adapter import build_wyckoff_snapshot
# Reusa la logica autoritativa del generator (bucket relativo a direccion).
from scripts.lab.experiments.exp_seq_ctx_01_dataset import (
    h1_alignment, context_bucket, _bias_name, _block_of, _block_end,
)

OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "wyckoff_ict_01"
OUT_JSON = OUT_DIR / "feasibility_counts_v2.json"

WINDOW = 1500
AUTHORITY_TF = "H1"
LAYERS = ("H1", "H4", "D1")
MIN_DEPTH = 4
BLOCKS = [
    ("DESIGN", "2006-01-01", "2015-12-31"),
    ("VALIDATION", "2016-01-01", "2020-12-31"),
    ("HOLDOUT", "2021-01-01", "2025-12-31"),
]
TFS = ("H1", "H4", "D1")
N_REQUIRED = 389  # n por grupo (MDE 10pp, potencia 0.80) del prerregistro §5


def _wyckoff_conflict_at(frames, nav, t, window=WINDOW, authority_tf=AUTHORITY_TF, layers=LAYERS):
    """Snapshot Wyckoff PIT (solo close_time<=t) -> (phase_state, conflict)."""
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    trunc = {}
    for tf in layers:
        f = frames[tf]
        ft = pd.to_datetime(f["time"], utc=True, errors="coerce")
        m = ft <= tt
        v = f.loc[m].copy().reset_index(drop=True)
        if len(v) > window:
            v = v.iloc[-window:].copy().reset_index(drop=True)
        trunc[tf] = v
    if trunc[authority_tf].empty:
        return "NEUTRAL", False
    st = nav.navigate(t, exec_tf="H1")
    snap = build_wyckoff_snapshot(trunc, t, context_state=st, authority_tf=authority_tf, layers=layers)
    return snap.phase_state.value, bool(snap.conflict)


def main() -> None:
    t0 = time.time()
    print("FEASIBILITY COUNTS EXP-WYCKOFF-ICT-01 (v2 corregido)", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    print(f"H1 barras: {len(h1)}", flush=True)

    nav = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
    cfg = SE.SeqConfig(structure_mode="canonical_bos", max_active_chains=10_000_000)

    # Celdas: ICT(ALIGNED/NEUTRAL/AGAINST) x WYCKOFF phase(4) y bandera CONFLICT.
    results = {}

    for tf in TFS:
        print(f"\n=== {tf} ===", flush=True)
        tt = time.time()
        chains = SE.run_sequential(frames[tf], cfg, symbol="EURUSD", timeframe=tf)
        print(f"  chains(completas+abiertas)={len(chains)} en {round(time.time()-tt,1)}s", flush=True)

        # conteo por celda primaria (CONFLICT vs NON_CONFLICT) dentro de ICT
        cells = defaultdict(lambda: defaultdict(int))  # block -> cell -> n
        # matriz completa para referencia
        matrix = defaultdict(lambda: defaultdict(int))
        seen = set()  # dedup (bar_k, direction) por variant/tf
        ict_cache = {}  # bar_k -> (bucket,)
        wyck_cache = {}  # bar_k -> (phase, conflict)
        stt = time.time()
        n_nodes = 0
        for ch in chains:
            nodes = ch.nodes
            if len(nodes) < MIN_DEPTH:
                continue
            for k in range(MIN_DEPTH - 1, len(nodes)):
                bar_k = int(nodes[k].bar)
                dir_val = nodes[k].direction.value if hasattr(nodes[k].direction, "value") else int(nodes[k].direction)
                dkey = (bar_k, int(dir_val))
                if dkey in seen:
                    continue
                seen.add(dkey)
                n_nodes += 1
                t = frames[tf]["time"].iloc[bar_k]
                tp = pd.to_datetime(t, utc=True, errors="coerce")
                block = _block_of(tp)
                if block == "OUT":
                    continue
                # Contexto ICT PIT (cache por barra; navigate full == prefix, gate PASS)
                if bar_k not in ict_cache:
                    st = nav.navigate(t, exec_tf="H1")
                    d1 = st.layers.get("D1")
                    h4 = st.layers.get("H4")
                    h1_layer = st.layers.get("H1")
                    d1_bias = _bias_name(d1.structure_bias) if d1 else "UNKNOWN"
                    h4_answer = (h4.answers.get(M.NavQuestion.WHERE_IN_CONTEXT.value) or {}) if h4 else {}
                    h4_loc = h4_answer.get("location", "UNKNOWN") if isinstance(h4_answer, dict) else "UNKNOWN"
                    h1_bias = _bias_name(h1_layer.structure_bias) if h1_layer else "UNKNOWN"
                    h1_align = h1_alignment(dir_val, h1_bias)
                    bucket = context_bucket(dir_val, d1_bias, h4_loc, h1_align)
                    ict_cache[bar_k] = bucket
                else:
                    bucket = ict_cache[bar_k]
                # Wyckoff PIT (cache por barra)
                if bar_k not in wyck_cache:
                    phase, conflict = _wyckoff_conflict_at(frames, nav, t)
                    wyck_cache[bar_k] = (phase, conflict)
                else:
                    phase, conflict = wyck_cache[bar_k]
                conflict_flag = "CONFLICT" if conflict else "NON_CONFLICT"
                matrix[bucket][phase] += 1
                # celda primaria: ICT x (CONFLICT vs NON_CONFLICT)
                cells[bucket][conflict_flag] += 1
                # tambien desagregado CONFLICT/NO por fase para diagnostico
                cells[f"{bucket}|{phase}"][conflict_flag] += 1
            if (n_nodes % 2000) == 0:
                print(f"  ...nodes {n_nodes} ({round(time.time()-stt,1)}s)", flush=True)

        results[tf] = {
            "n_observations_after_dedup": n_nodes,
            "cells_primary": {b: dict(cells[b]) for b in cells},
            "matrix_ict_x_wyckoff_phase": {b: dict(matrix[b]) for b in matrix},
        }
        print(f"  {tf} done {round(time.time()-tt,1)}s total {round(time.time()-t0,1)}s", flush=True)

    report = {
        "experiment": "EXP-WYCKOFF-ICT-01_FEASIBILITY_COUNTS_V2",
        "version": "corregido-post-auditoria",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "symbol": "EURUSD",
        "dataset": "datasets/eurusd_dukascopy_20y",
        "structure_mode": "canonical_bos",
        "anchor": "node k bar (nodes[k].bar), k>=MIN_DEPTH(4)",
        "dedup_key": "(bar_k, direction)",
        "context_bucket": "relativo a sequence_direction (exp_seq_ctx_01_dataset.context_bucket)",
        "n_required_per_group": N_REQUIRED,
        "blocks": [b[0] for b in BLOCKS],
        "timeframes": list(TFS),
        "observational_unit": "SequentialChain node k (k>=4), dedup (bar_k,direction)",
        "counts": results,
        "generator_commit": _git_commit(),
        "generator_worktree": _worktree_state(),
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    # Resumen por consola
    print("\n=== RESUMEN CELDAS PRIMARIAS (ICT x CONFLICT/NON_CONFLICT) ===", flush=True)
    for tf in TFS:
        print(f"\n-- {tf} --", flush=True)
        cells = results[tf]["cells_primary"]
        for ict in ("ALIGNED", "AGAINST", "NEUTRAL"):
            c = cells.get(ict, {})
            print(f"  ICT={ict}: CONFLICT={c.get('CONFLICT',0)} NON_CONFLICT={c.get('NON_CONFLICT',0)}", flush=True)
    print(f"\nJSON -> {OUT_JSON}", flush=True)


def _git_commit() -> str:
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT)).decode().strip()
    except Exception:
        return "unknown"


def _worktree_state() -> str:
    import subprocess
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(ROOT)).decode().strip()
        return "DIRTY" if out else "CLEAN"
    except Exception:
        return "UNKNOWN"


if __name__ == "__main__":
    main()
