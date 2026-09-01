"""Diagnostico directo: por que run_sequential(FULL) no genera cadenas tempranas.

Compara run_sequential(FULL) vs run_sequential(PREFIX) contando cadenas con
CUALQUIER nodo en <=853 (no last_bar). Si FULL=0 y PREFIX>0, el motor no genera
esas cadenas en el FULL. Luego compara atomos (sweeps) en barra 200 FULL vs PREFIX
para aislar si el bug esta en _causal_atomics (no causal) o en la logica de cadena.
"""
from __future__ import annotations
import time
import pandas as pd
import engine.sequential_events as SE
from audits.codigo.mtf_seq_funnel import _load_tf

t0 = time.time()
h1 = _load_tf("H1")
print("loaded", round(time.time() - t0, 1))

cfg = SE.SeqConfig(structure_mode="canonical_bos", max_active_chains=10_000_000)

print("run_sequential FULL...", flush=True)
full = SE.run_sequential(h1, cfg, symbol="EURUSD", timeframe="H1")
print(f"  full chains={len(full)} {round(time.time()-t0,1)}s", flush=True)

pre = h1.iloc[:854].copy().reset_index(drop=True)
print("run_sequential PREFIX...", flush=True)
pref = SE.run_sequential(pre, cfg, symbol="EURUSD", timeframe="H1")
print(f"  pref chains={len(pref)}", flush=True)

def n_con_nodos_le(chains, i):
    return sum(1 for ch in chains if any(int(nd.bar) <= i for nd in ch.nodes))

print(f"\nCadenas con CUALQUIER nodo <=853:", flush=True)
print(f"  FULL  = {n_con_nodos_le(full, 853)}", flush=True)
print(f"  PREFIX= {n_con_nodos_le(pref, 853)}", flush=True)

# Comparar atomos en barra 200
print("\nAtomos sweeps barra 200:", flush=True)
a_full = SE._detect_atomics(h1, cfg)
a_pref = SE._detect_atomics(pre, cfg)
sw_full = a_full.sweeps.get(200, [])
sw_pref = a_pref.sweeps.get(200, [])
print(f"  FULL sweeps@200 = {len(sw_full)}", flush=True)
print(f"  PREF sweeps@200 = {len(sw_pref)}", flush=True)
print(f"  FULL primeros: {sw_full[:3]}", flush=True)
print(f"  PREF primeros: {sw_pref[:3]}", flush=True)
