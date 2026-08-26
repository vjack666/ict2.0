"""Conteos de factibilidad EXP-WYCKOFF-ICT-01 (solo conteos; SIN outcomes ni significancia).

Matriz ICT (ALIGNED/NEUTRAL/AGAINST) x Wyckoff (PRO_TREND/COUNTERTREND/
TRANSITION/NEUTRAL) por bloque temporal DESIGN/VALIDATION/HOLDOUT, sobre
EURUSD Dukascopy 20Y, H1/H4/D1, structure_mode=canonical_bos.

Unidad de observación: nodo de SequentialChain (como fija el prerregistro).
Ancla: barra de estructura (created_bar) de cada cadena.

PIT: cada snapshot usa solo barras con indice <= barra de estructura
(equivalente a close_time <= t para datos ordenados; truncate por iloc O(1)).
NO calcula outcomes ni significancia. NO modifica el universo tras los conteos.
"""
from __future__ import annotations
import json, time, sys
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

OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "wyckoff_ict_01"
OUT_JSON = OUT_DIR / "feasibility_counts.json"

WINDOW = 1500
AUTHORITY_TF = "H1"
LAYERS = ("H1", "H4", "D1")

BLOCKS = {
    "DESIGN": ("2006-01-01", "2015-12-31"),
    "VALIDATION": ("2016-01-01", "2020-12-31"),
    "HOLDOUT": ("2021-01-01", "2025-12-31"),
}
TFS = ("H1", "H4", "D1")
N_REQUIRED = 389  # n por grupo (MDE 10pp, potencia 0.80) del prerregistro §5


def _bias_str(b):
    if b is None:
        return "NEUTRAL"
    s = b.value if hasattr(b, "value") else str(b)
    s = s.upper()
    if s in ("ALIGNED", "BULLISH"):
        return "ALIGNED"
    if s in ("AGAINST", "BEARISH"):
        return "AGAINST"
    return "NEUTRAL"


def _precompute_cut_indices(frames, tf_exec, exec_times):
    """Para cada barra de estructura del TF de ejecución, indices de corte en cada capa
    por timestamp <= t (usando bisect sobre tiempos ordenados)."""
    import bisect
    cut = {}
    for tf in LAYERS:
        tt = pd.to_datetime(frames[tf]["time"], utc=True, errors="coerce")
        cut[tf] = np.array([bisect.bisect_right(tt.values, pd.Timestamp(ts).to_datetime64()) for ts in exec_times])
    return cut


def main() -> None:
    t0 = time.time()
    print("FEASIBILITY COUNTS EXP-WYCKOFF-ICT-01", flush=True)
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    n_total = len(h1)
    print(f"H1 barras: {n_total}", flush=True)

    nav = M.MTFNavigator(frames, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
    cfg = SE.SeqConfig(structure_mode="canonical_bos", max_active_chains=256)

    results = {}

    for tf in TFS:
        print(f"\n=== {tf} ===", flush=True)
        tt = time.time()
        chains = SE.run_sequential(frames[tf], cfg, symbol="EURUSD", timeframe=tf)
        print(f"  chains={len(chains)} en {round(time.time()-tt,1)}s", flush=True)

        need = sorted({int(c.created_bar) for c in chains})
        exec_times = [frames[tf]["time"].iloc[bar] for bar in need]
        cut = _precompute_cut_indices(frames, tf, exec_times)

        ict_by_bar = {}
        wyck_by_bar = {}
        stt = time.time()
        for k, bar in enumerate(need):
            ci = {tf2: cut[tf2][k] for tf2 in LAYERS}
            # Context State ICT (una sola llamada navigate por barra)
            t = frames[tf]["time"].iloc[bar]
            st = nav.navigate(t, exec_tf="H1")
            ict_by_bar[bar] = _bias_str(st.constraints.direction_hint) if st.constraints and st.constraints.direction_hint is not None else "NEUTRAL"
            if bar not in wyck_by_bar:
                # Truncate por indice (O(1) slice) = barras con time <= t,
                # luego ventana deslizante de WINDOW barras (PIT-valido: solo pasado).
                raw = {tf2: frames[tf2].iloc[:ci[tf2]] for tf2 in LAYERS}
                trunc = {tf2: (v.iloc[-WINDOW:] if len(v) > WINDOW else v).copy().reset_index(drop=True) for tf2, v in raw.items()}
                if trunc[AUTHORITY_TF].empty:
                    wyck_by_bar[bar] = "NEUTRAL"
                else:
                    snap = build_wyckoff_snapshot(trunc, t, context_state=st, authority_tf=AUTHORITY_TF, layers=LAYERS)
                    wyck_by_bar[bar] = snap.phase_state.value
            if k % 500 == 0:
                print(f"  ...{k}/{len(need)} ({round(time.time()-stt,1)}s)", flush=True)

        # conteo por bloque
        counts = {}
        for bname, (bs, be) in BLOCKS.items():
            bs_p = pd.Timestamp(bs, tz="UTC"); be_p = pd.Timestamp(be, tz="UTC")
            mat = defaultdict(lambda: defaultdict(int))
            for c in chains:
                bar = int(c.created_bar)
                tp = pd.to_datetime(frames[tf]["time"].iloc[bar], utc=True, errors="coerce")
                if not (bs_p <= tp <= be_p):
                    continue
                ict = ict_by_bar.get(bar, "NEUTRAL")
                wy = wyck_by_bar.get(bar, "NEUTRAL")
                mat[ict][wy] += 1
            counts[bname] = {ict: dict(mat[ict]) for ict in mat}
        results[tf] = counts
        print(f"  {tf} counts done {round(time.time()-tt,1)}s total {round(time.time()-t0,1)}s", flush=True)

    primary = results["H1"]
    print("\n=== RESUMEN (H1, matriz ICT x Wyckoff) ===", flush=True)
    for bname, mat in primary.items():
        print(f"\nBloque {bname}:", flush=True)
        for ict in ("ALIGNED", "NEUTRAL", "AGAINST"):
            row = mat.get(ict, {})
            tot = sum(row.values())
            print(f"  ICT={ict}: {dict(row)} total={tot}", flush=True)

    report = {
        "experiment": "EXP-WYCKOFF-ICT-01_FEASIBILITY_COUNTS",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "symbol": "EURUSD",
        "dataset": "datasets/eurusd_dukascopy_20y",
        "structure_mode": "canonical_bos",
        "n_required_per_group": N_REQUIRED,
        "blocks": BLOCKS,
        "timeframes": list(TFS),
        "observational_unit": "SequentialChain.structure_bar (created_bar)",
        "counts": results,
        "generator_commit": "a20c66aaf5d56126850701b93296cd651d04b993",
        "generator_worktree": "CLEAN",
        "elapsed_s": round(time.time() - t0, 1),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nJSON -> {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
