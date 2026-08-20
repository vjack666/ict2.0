"""Aislar raiz del no-PIT en run_sequential (FULL vs PREFIX).

Para barras t muestreadas: compara los ATOMOS en t entre run_sequential(FULL) y
run_sequential(PREFIX hasta t). Si los atomos en t difieren FULL vs PREFIX => la raiz
esta en _detect_atomics/_build_eq_pools/_causal_swings (miran adelante). Si son iguales
pero las cadenas en t difieren => raiz en logica de cadena (max_active_chains/caducidad).

Esto decide QUE tocar para engine-seq-v2-causal sin re-arreglar a ciegas.
"""
from __future__ import annotations
import time
import pandas as pd
import engine.sequential_events as SE
from audits.codigo.mtf_seq_funnel import _load_tf

t0 = time.time()
h1 = _load_tf("H1")
print("loaded", round(time.time() - t0, 1))

cfg = SE.SeqConfig(structure_mode="canonical_bos", max_active_chains=128)

print("run_sequential FULL...", flush=True)
full = SE.run_sequential(h1, cfg, symbol="EURUSD", timeframe="H1")
print(f"  full chains={len(full)} {round(time.time()-t0,1)}s", flush=True)

# barras de observacion: rango plano donde el PREFIX hasta t debe tener atomos
sample_bars = list(range(100, 1500, 100))
print(f"barras muestreadas: {sample_bars}", flush=True)

def atomos_en(at, t):
    """Cuenta atomos con barra == t."""
    n_sw = len(at.sweeps.get(t, []))
    n_disp = len(at.displ.get(t, []))
    n_st = len(at.structs.get(t, []))
    n_ob = len(at.obs.get(t, []))
    n_fv = len(at.fvgs.get(t, []))
    return n_sw, n_disp, n_st, n_ob, n_fv

print(f"\n{'barra':>6} | {'FULL sw/disp/st/ob/fvg':>28} | {'PREF sw/disp/st/ob/fvg':>28} | diff?", flush=True)
at_f = SE._detect_atomics(h1, cfg)
for t in sample_bars:
    pre = h1.iloc[: t + 1].copy().reset_index(drop=True)
    at_p = SE._detect_atomics(pre, cfg)
    af = atomos_en(at_f, t)
    ap = atomos_en(at_p, t)
    diff = "  <-- ATOMOS DIFEREN" if af != ap else ""
    print(f"{t:>6} | {str(af):>28} | {str(ap):>28} |{diff}", flush=True)

# Y comparar cadenas con nodos en t
print("\nCadenas con nodo en t (FULL vs PREFIX):", flush=True)
for t in sample_bars[:5]:
    pre = h1.iloc[: t + 1].copy().reset_index(drop=True)
    pref = SE.run_sequential(pre, cfg, symbol="EURUSD", timeframe="H1")
    cf = [ch for ch in full if any(int(nd.bar) == t for nd in ch.nodes)]
    cp = [ch for ch in pref if any(int(nd.bar) == t for nd in ch.nodes)]
    sig_f = {(c.direction, tuple(n.stage.value for n in c.nodes)) for c in cf}
    sig_p = {(c.direction, tuple(n.stage.value for n in c.nodes)) for c in cp}
    only_f = sig_f - sig_p
    only_p = sig_p - sig_f
    print(f"  t={t}: FULL={len(cf)} PREF={len(cp)} solo_FULL={len(only_f)} solo_PREF={len(only_p)}", flush=True)
    if only_f:
        print(f"    solo_FULL sample: {list(only_f)[:2]}", flush=True)
    if only_p:
        print(f"    solo_PREF sample: {list(only_p)[:2]}", flush=True)
