"""EXP-SEQ-CTX-01 — DIAG RAÍZ v3 (definitivo): compara lo que navigate() USA.

El diag v1 (recalculo externo) dijo swings <=BAR iguales; el diag v2 (navigate
real) da bias distinto. Contradiccion -> no declaro raiz hasta resolverla.
Aqui extraemos pre["sh"] del navigator FULL y del PREFIX exactamente como los
usa _snapshot (bisect_right(sh_b, i) -> pre["sh"][:si]) y comparamos los
ultimos swings <=BAR de cada uno.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engine.mtf_navigation as M
from audits.codigo.mtf_seq_funnel import _load_tf

BAR = 2600


def build_pre(df_h1):
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    frames["H1"] = df_h1
    nav = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=True, sequence_tf="H1"))
    return nav


def used_swings(nav, bar):
    pre = nav._pre["H1"]
    sh_b = pre["sh_b"]
    import bisect
    si = bisect.bisect_right(sh_b, bar)
    return pre["sh"][:si]


def main():
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    pref = h1.iloc[: BAR + 1].copy().reset_index(drop=True)

    nav_full = build_pre(h1)
    nav_pref = build_pre(pref)

    sh_full_used = used_swings(nav_full, BAR)
    sh_pref_used = used_swings(nav_pref, BAR)

    print(f"BAR={BAR}")
    print(f"swings H1 altos USADOS por navigate <=BAR: full={len(sh_full_used)} pref={len(sh_pref_used)}")
    print("ULT 5 full:", sh_full_used[-5:])
    print("ULT 5 pref:", sh_pref_used[-5:])

    # diff elemento a elemento
    n = min(len(sh_full_used), len(sh_pref_used))
    diffs = []
    for k in range(n):
        if sh_full_used[k] != sh_pref_used[k]:
            diffs.append((k, sh_full_used[k], sh_pref_used[k]))
    if len(sh_full_used) != len(sh_pref_used):
        diffs.append(("LEN", len(sh_full_used), len(sh_pref_used)))
    print(f"\nPRIMER diff en posicion k (barra,precio):")
    for d in diffs[:6]:
        print("  ", d)

    # recomputar bias con los swings USADOS (no el array completo)
    from engine.mtf_navigation import _structure_bias_from_swings
    sl_full_used = used_swings_sl(nav_full, BAR)
    sl_pref_used = used_swings_sl(nav_pref, BAR)
    bias_f = _structure_bias_from_swings(sh_full_used, sl_full_used, BAR)
    bias_p = _structure_bias_from_swings(sh_pref_used, sl_pref_used, BAR)
    print(f"\nbias con swings USADOS: full={bias_f.value} pref={bias_p.value}")

    if sh_full_used == sh_pref_used:
        print("\nCONCLUSION: swings usados IGUALES -> la raiz NO es _causal_swings.")
        print("  El bias diverge por OTRO productor (revisar _structure_bias_from_swings")
        print("  o si navigate usa otra fuente).")
    else:
        print("\nCONCLUSION: swings usados DIFIEREN -> raiz en _causal_swings (ventana centrada).")


def used_swings_sl(nav, bar):
    pre = nav._pre["H1"]
    sl_b = pre["sl_b"]
    import bisect
    si = bisect.bisect_right(sl_b, bar)
    return pre["sl"][:si]


if __name__ == "__main__":
    main()
