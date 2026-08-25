"""PILOTO DE VIABILIDAD — ampliación OOS multi-símbolo (EXP-SEQ-CTX-01).

NO es el preregistro ni la ejecución final. Solo mide si el motor
(run_sequential + MTFNavigator) produce observaciones HOLDOUT válidas en
símbolos distintos de EURUSD, usando EXACTAMENTE la misma lógica de
contexto PIT / bucket / purga +48 que el factory.

Limita H1 a 2021+ para validar rapidez; la ejecución FASE 5 usará H1 completo.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from engine.sequential_events import run_sequential, SeqConfig
import engine.mtf_navigation as M
from scripts.lab.experiments.exp_seq_ctx_01_dataset import (
    h1_alignment, context_bucket, BLOCKS, _block_end, _bias_name,
)

SYMS = ["GBPUSD", "XAUUSD", "AUDUSD"]
TF = "H1"
MODES = ["canonical_bos", "lite"]
HORIZONS = [6, 12, 24, 48]


def load_raw(sym: str, tf: str) -> pd.DataFrame:
    p = ROOT / "data" / "raw" / sym / f"{sym}_{tf}.parquet"
    df = pd.read_parquet(p)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.sort_values("time").reset_index(drop=True)


def block_of(t: pd.Timestamp) -> str:
    for name, a, b in BLOCKS:
        if pd.Timestamp(a, tz="UTC") <= t <= pd.Timestamp(b, tz="UTC"):
            return name
    return "OUT"


def main() -> int:
    t0 = time.time()
    for sym in SYMS:
        frames = {tf: load_raw(sym, tf) for tf in ("D1", "H4", "H1")}
        # Piloto: solo 2021+ para rapidez (FASE 5 usa H1 completo).
        h1 = frames["H1"]
        h1 = h1[h1["time"] >= pd.Timestamp("2021-01-01", tz="UTC")].reset_index(drop=True)
        print(f"[PILOTO] {sym}: H1(2021+)={len(h1)} D1={len(frames['D1'])} H4={len(frames['H4'])}", flush=True)
        for mode in MODES:
            chains = run_sequential(h1, SeqConfig(structure_mode=mode, max_active_chains=10_000_000),
                                    symbol=sym, timeframe=TF)
            seen = set()
            counts = {"ALIGNED": 0, "NEUTRAL": 0, "AGAINST": 0, "OUT": 0}
            h1_time = h1["time"].reset_index(drop=True)
            n_chains = 0
            for ch in chains:
                if str(getattr(ch, "status", ch)) != "COMPLETE":
                    continue
                n_chains += 1
                nodes = ch.nodes
                for k in range(1, len(nodes)):
                    if k + 1 < 4:
                        continue
                    bar_k = int(nodes[k].bar)
                    dir_val = nodes[k].direction.value if hasattr(nodes[k].direction, "value") else int(nodes[k].direction)
                    dk = (bar_k, int(dir_val))
                    if dk in seen:
                        continue
                    seen.add(dk)
                    t = pd.to_datetime(h1.iloc[bar_k]["time"], utc=True)
                    split = block_of(t)
                    if split != "HOLDOUT":
                        continue
                    end48 = min(bar_k + 48, len(h1_time) - 1)
                    t48 = pd.to_datetime(h1_time.iloc[end48], utc=True)
                    if t48 > _block_end("HOLDOUT"):
                        continue
                    pref = {tf: frames[tf].loc[frames[tf]["time"] <= t].copy().reset_index(drop=True)
                            for tf in frames}
                    nav = M.MTFNavigator(pref, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
                    st = nav.navigate(t, exec_tf="H1")
                    d1 = st.layers.get("D1")
                    h4 = st.layers.get("H4")
                    h1l = st.layers.get("H1")
                    d1b = _bias_name(d1.structure_bias) if d1 else "UNKNOWN"
                    h4a = (h4.answers.get(M.NavQuestion.WHERE_IN_CONTEXT.value) or {}) if h4 else {}
                    h4loc = h4a.get("location", "UNKNOWN") if isinstance(h4a, dict) else "UNKNOWN"
                    h1b = _bias_name(h1l.structure_bias) if h1l else "UNKNOWN"
                    h1al = h1_alignment(dir_val, h1b)
                    bucket = context_bucket(dir_val, d1b, h4loc, h1al)
                    counts[bucket] += 1
            print(f"  [{sym}/{mode}] chains={n_chains} HOLDOUT={counts} ({time.time()-t0:.1f}s)", flush=True)
    print(f"[PILOTO] DONE {time.time()-t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
