"""Aislar raiz del leakage de sequence_depth (paso 4).

Compara run_sequential(df completo) vs run_sequential(df[:i+1]) y muestra las
cadenas con last_bar <= i de ambos. Si difieren, run_sequential subyacente no es
point-in-time estable (ventanas/max_active/caducidad miran adelante).

Barra objetivo: i=853 (primer desajuste del diag_causal_violation).
"""
from __future__ import annotations

import time
import pandas as pd

from engine.sequential_events import run_sequential, SeqConfig
from audits.codigo.mtf_seq_funnel import _load_tf


def chains_at(chains, i):
    out = []
    for ch in chains:
        if ch.last_bar <= i:
            out.append((ch.chain_id, ch.direction, ch.last_bar, ch.status, len(ch.nodes)))
    return out


def main():
    t0 = time.time()
    h1 = _load_tf("H1")
    i = 853
    cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=128)

    print("run_sequential FULL...", flush=True)
    full = run_sequential(h1, cfg, symbol="EURUSD", timeframe="H1")
    print(f"  full chains={len(full)} en {time.time()-t0:.1f}s", flush=True)

    prefix_df = h1.iloc[: i + 1].copy().reset_index(drop=True)
    print("run_sequential PREFIX (hasta i)...", flush=True)
    t1 = time.time()
    pref = run_sequential(prefix_df, cfg, symbol="EURUSD", timeframe="H1")
    print(f"  prefix chains={len(pref)} en {time.time()-t1:.1f}s", flush=True)

    cf = chains_at(full, i)
    cp = chains_at(pref, i)
    print(f"\nBarra i={i}:", flush=True)
    print(f"  FULL  cadenas con last_bar<={i}: {len(cf)}", flush=True)
    print(f"  PREFIX cadenas con last_bar<={i}: {len(cp)}", flush=True)

    sf = set((c[0], c[1], c[2], c[3], c[4]) for c in cf)
    sp = set((c[0], c[1], c[2], c[3], c[4]) for c in cp)
    only_full = sf - sp
    only_pref = sp - sf
    print(f"  Solo en FULL: {len(only_full)}", flush=True)
    for x in list(only_full)[:10]:
        print(f"    {x}", flush=True)
    print(f"  Solo en PREFIX: {len(only_pref)}", flush=True)
    for x in list(only_pref)[:10]:
        print(f"    {x}", flush=True)

    # Verificar si run_sequential usa ventanas que dependen de n total
    print("\nDiff en total chains FULL vs PREFIX:", len(full), "vs", len(pref), flush=True)


if __name__ == "__main__":
    main()
