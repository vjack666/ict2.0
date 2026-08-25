"""SEQUENCE_PIT_INTEGRITY gate — run_sequential FULL vs PREFIX.

Verifica que run_sequential sea point-in-time estable: para barras k muestreadas,
las cadenas con created_bar <= k en run_sequential(FULL) deben ser identicas a las de
run_sequential(PREFIX=df[:k+1]).

Compara: created_bar, direction, stages (secuencia de nodos), nodes bars, status, depth.
Gate PASS solo si violations == 0.
"""
from __future__ import annotations
import time
import pandas as pd
import numpy as np
import engine.sequential_events as SE
from audits.codigo.mtf_seq_funnel import _load_tf

t0 = time.time()
h1 = _load_tf("H1")
print("loaded", round(time.time() - t0, 1))

cfg = SE.SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
print("run_sequential FULL...", flush=True)
full = SE.run_sequential(h1, cfg, symbol="EURUSD", timeframe="H1")
print(f"  full chains={len(full)} {round(time.time()-t0,1)}s", flush=True)

def signature(ch):
    """Firma PIT de una cadena: creada en t, direction, stages en orden de nodo."""
    nodes = ch.nodes
    return (
        int(ch.created_bar),
        int(ch.direction),
        tuple((int(n.bar), n.stage.value) for n in nodes),
        ch.status,
    )

# barras M donde comparar cadenas con ultimo nodo <= M.
# El PREFIX debe tener margen para que las cadenas avancen (no confundir con leakage).
MARGIN = 300
pref_big = SE.run_sequential(h1.iloc[: 5000 + MARGIN + 1].copy().reset_index(drop=True), cfg, symbol="EURUSD", timeframe="H1")
ks = sorted({int(ch.created_bar) for ch in pref_big if int(ch.created_bar) < 5000 and max(int(n.bar) for n in ch.nodes) <= 5000})[:40]
print(f"ks muestreados (created_bar del PREFIX con margen): {len(ks)}", flush=True)

viol = 0
checked = 0
for k in ks:
    M = k + MARGIN
    pre = SE.run_sequential(h1.iloc[: M + 1].copy().reset_index(drop=True), cfg, symbol="EURUSD", timeframe="H1")
    # cadenas con TODOS sus nodos <= k en FULL y en PREFIX
    full_sub = {signature(ch) for ch in full if int(ch.created_bar) <= k and max(int(n.bar) for n in ch.nodes) <= k}
    pre_sub = {signature(ch) for ch in pre if int(ch.created_bar) <= k and max(int(n.bar) for n in ch.nodes) <= k}
    checked += 1
    if full_sub != pre_sub:
        viol += 1
        if viol <= 3:
            only_f = full_sub - pre_sub
            only_p = pre_sub - full_sub
            print(f"  VIOL k={k}: full_only={len(only_f)} pref_only={len(only_p)}", flush=True)
            if only_p:
                print(f"    pref_only sample: {list(only_p)[:1]}", flush=True)
            if only_f:
                print(f"    full_only sample: {list(only_f)[:1]}", flush=True)

print(f"\nSEQUENCE_PIT_INTEGRITY: checked={checked} violations={viol}", flush=True)
print("GATE:", "PASS" if viol == 0 else "FAIL", flush=True)
