"""Diagnostico de violacion causal (pasos 1-4 de correccion 2026-08-20).

Reproduce exactamente la barra donde navigate(full) != navigate(prefix_through_t),
hace diff COMPLETO del MarketState (no solo outcome) y reporta el primer campo
divergente para rastrear el productor (detect_bos / detect_displacement /
_causal_swings / _eq_pools / run_sequential / indice de secuencias).

NO es smoke test: recorre muestra amplia y acumula violaciones.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

import engine.mtf_navigation as M
from audits.codigo.mtf_seq_funnel import _load_tf

N_SAMPLES = 15
ROOT = Path(__file__).resolve().parents[1]


def dict_diff(a, b, path=""):
    """Devuelve lista de (ruta, val_a, val_b) para primeras diferencias."""
    diffs = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a) | set(b):
            diffs += dict_diff(a.get(k), b.get(k), f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((path + f"[len]", len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diffs += dict_diff(x, y, f"{path}[{i}]")
    else:
        if a != b:
            diffs.append((path, a, b))
    return diffs


def layer_diff(name, la, lb):
    if la is None or lb is None:
        return [(f"{name}.EXISTS", la is not None, lb is not None)]
    da = la.to_dict()
    db = lb.to_dict()
    return dict_diff(da, db, name)


def main():
    t0 = time.time()
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    times = h1["time"]

    nav_full = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))

    viol = 0
    first_diff = None
    checked = 0
    # muestra amplia y deterministica
    import numpy as np
    rng = np.random.default_rng(7)
    idxs = sorted(rng.integers(200, len(h1) - 50, N_SAMPLES).tolist())

    for i in idxs:
        checked += 1
        t = times.iloc[i]
        st_full = nav_full.navigate(t, exec_tf="H1")
        trunc = {tf: frames[tf].iloc[: i + 1].copy().reset_index(drop=True) for tf in frames}
        nav_pref = M.MTFNavigator(trunc, M.NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))
        st_pref = nav_pref.navigate(t, exec_tf="H1")

        # diff capa por capa
        all_diff = []
        for lyr in ("D1", "H4", "H1", "M15", "M5"):
            la = st_full.layers.get(lyr)
            lb = st_pref.layers.get(lyr)
            all_diff += layer_diff(lyr, la, lb)
        # constraints
        ca = st_full.constraints.to_dict() if st_full.constraints else None
        cb = st_pref.constraints.to_dict() if st_pref.constraints else None
        all_diff += dict_diff(ca, cb, "constraints")
        # path
        all_diff += dict_diff(st_full.path.to_dict(), st_pref.path.to_dict(), "path")

        if all_diff:
            viol += 1
            if first_diff is None:
                first_diff = (i, t, all_diff[:20])

    print(f"checked={checked} violations={viol} in {time.time()-t0:.1f}s", flush=True)
    if first_diff:
        i, t, diffs = first_diff
        print(f"\n=== PRIMERA VIOLACION en barra i={i} time={t} ===", flush=True)
        for path, va, vb in diffs[:20]:
            print(f"  {path}: full={va}  prefix={vb}", flush=True)
    else:
        print("SIN VIOLACIONES", flush=True)


if __name__ == "__main__":
    main()
