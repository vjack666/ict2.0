"""ict_backtest/_diag_signals.py — Diagnostico rapido: cuantas senales genera
sequence.py en distintas porciones de la serie y con distintos params.

Sirve para calibrar la Capa 3 (optimize.py) sin esperar 60 min: encontramos
que ventana y que rango de params dan senales suficientes (>=5) para que
Optuna no penalice todo con -1.0.

Uso:
  python ict_backtest/_diag_signals.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames
from engine.market_structure import detect_market_structure
from ict_backtest.sequence import run_sequence, SequenceConfig, _row_at_time


# Mapea indice del LTF -> timestamp (busqueda por tiempo, robusta a slices).
_ltf_time_fn = lambda i: i


def _est(htf_df):
    def f(i):
        t = _ltf_time_fn(i)
        r = _row_at_time(htf_df, t)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return f


def n_senales(ltf_df, htf_df, cfg):
    global _ltf_time_fn
    _ltf_time_fn = lambda i: ltf_df.iloc[i]["time"]
    sigs, _ = run_sequence(ltf_df, _est(htf_df), cfg)
    return len(sigs)


def main():
    fr = load_frames("EURUSD", ("H4", "M15", "D1"))
    # CRITICO: aplicar detect_market_structure IGUAL que run_backtest.py
    ms = {tf: detect_market_structure(df) for tf, df in fr.items()}
    ltf = ms["M15"].reset_index(drop=True)
    htf = ms["H4"].reset_index(drop=True)
    n = len(ltf)
    print(f"LTF total: {n} velas", flush=True)

    base = SequenceConfig(counter_trend=False, tp_mode="fixed2r", require_displacement=True)
    for i in range(3):
        a = i * n // 3
        b = (i + 1) * n // 3
        sub = ltf.iloc[a:b].reset_index(drop=True)
        tmin = sub["time"].min()
        hsub = htf[htf["time"] >= tmin].reset_index(drop=True)
        cnt = n_senales(sub, hsub, base)
        print(f"  tramo {i+1} [{a}:{b}] ({len(sub)} velas): {cnt} senales (config base)", flush=True)

    print("\nBarrido require_displacement en tramo 1 (primer tercio):", flush=True)
    for rd in (True, False):
        for p in ("fixed2r", "liquidity"):
            cfg = SequenceConfig(counter_trend=False, tp_mode=p, require_displacement=rd)
            sub = ltf.iloc[: n // 3].reset_index(drop=True)
            tmin = sub["time"].min()
            hsub = htf[htf["time"] >= tmin].reset_index(drop=True)
            cnt = n_senales(sub, hsub, cfg)
            print(f"  require_displacement={rd} tp_mode={p}: {cnt} senales", flush=True)

    print("\nBarrido gaps en tramo 1 (require_displacement=False, fixed2r):", flush=True)
    for dg in (1, 3, 6, 12):
        for bg in (1, 3, 8, 16):
            cfg = SequenceConfig(counter_trend=False, tp_mode="fixed2r",
                                require_displacement=False, displace_gap=dg, bos_gap=bg)
            sub = ltf.iloc[: n // 3].reset_index(drop=True)
            tmin = sub["time"].min()
            hsub = htf[htf["time"] >= tmin].reset_index(drop=True)
            cnt = n_senales(sub, hsub, cfg)
            print(f"  displace_gap={dg:2d} bos_gap={bg:2d}: {cnt} senales", flush=True)


if __name__ == "__main__":
    main()
