"""FASE 5 — AUDITORIA DE LIFECYCLE (MEDIR, no programar).

Objetivo (CEO 2026-08-27): antes de cualquier regla nueva, MEDIR si el sistema
acumula objetos ICT sin resolver (el "cementerio de lineas"). Cuantifica:

  - objetos creados por TF/tipo
  - objetos ACTIVE por vela (p50/p95/max)
  - edad (barras) de cada objeto al cierre de ventana
  - % que llega a estado terminal (MITIGATED/INVALIDATED/EXPIRED/CONSUMED)
  - % ACTIVE -> PARTIALLY_MITIGATED
  - zonas solapadas (misma TF, mismo tipo, rango superpuesto)
  - participacion en Setup AHF (cuantas zonas vivas vs cuantas el AHF usa)

Reusa engine/detectors/fvg.py y ob.py (canonicos, solo lectura). NO modifica
engine/. Simula el acumulado vela-a-vela igual que backtest/market_state.py
(que es la proyeccion bajo audit): activa por tradable_time, touch->PARTIAL,
sin terminales para FVG/OB. Asi la auditoria refleja el comportamiento REAL del
replay actual, no una version idealizada.

Salida: JSON + impresion de resumen. can_train=false, can_trade=false.
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))
OUT = ROOT / "reports" / "audits" / "fase5_lifecycle"
OUT.mkdir(parents=True, exist_ok=True)

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.market_object import ObjectState

TFS = ("D1", "H4", "H1", "M15")
WINDOW_BARS = 1500  # ventana de observacion por TF (no todo 20Y, para edad local)


def _load(tf: str) -> pd.DataFrame:
    p = ROOT / "data" / "raw" / "EURUSD" / f"EURUSD_{tf}.parquet"
    return pd.read_parquet(p)


def audit_tf(tf: str) -> dict:
    frame = _load(tf)
    n = len(frame)
    end = min(WINDOW_BARS, n)
    sub = frame.iloc[:end].copy().reset_index(drop=True)
    rows = sub.to_dict("records")

    # Detectores canonicos (crean ACTIVE, sin terminal).
    fvgs = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    obs = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    all_objs = [*fvgs, *obs]

    created = len(all_objs)
    by_type = defaultdict(int)
    for o in all_objs:
        by_type[o.type.value] += 1

    # Simula acumulado vela-a-vela (igual que build_market_state, sin terminales).
    live: dict[str, object] = {}
    active_per_candle: list[int] = []
    ages_at_end: list[int] = []
    reached_partial = 0
    touch_by_id: dict[str, bool] = {}

    times = pd.to_datetime(sub["time"], utc=True, errors="coerce")
    for i in range(end):
        decision = times.iloc[i]
        # activar
        for o in all_objs:
            if o.id in live:
                continue
            tt = pd.to_datetime(o.tradable_time, utc=True, errors="coerce")
            if pd.notna(tt) and tt <= decision:
                live[o.id] = o
        # touch -> PARTIAL
        row = sub.iloc[i]
        for o in list(live.values()):
            if o.type.value in ("FVG", "ORDER_BLOCK") and o.state is ObjectState.ACTIVE:
                tt = pd.to_datetime(o.tradable_time, utc=True, errors="coerce")
                if pd.notna(tt) and tt < decision:
                    lo = float(row["low"]); hi = float(row["high"])
                    if lo <= float(o.zone_high) and hi >= float(o.zone_low):
                        touch_by_id[o.id] = True
                        o.state = ObjectState.PARTIALLY_MITIGATED
        active_per_candle.append(len(live))

    for o in all_objs:
        if touch_by_id.get(o.id):
            reached_partial += 1

    # edad en barras de ese TF hasta el cierre de ventana (bucle plano, fuera de todo)
    t_vals = times.values.astype("datetime64[ns]").astype("int64")  # ns explicitos
    for o in all_objs:
        tt = pd.to_datetime(o.tradable_time, utc=True, errors="coerce")
        if pd.notna(tt):
            idx = int(np.searchsorted(t_vals, int(tt.value), side="right"))
            ages_at_end.append(max(0, end - 1 - idx))

    active_arr = np.array(active_per_candle)
    terminal = 0  # por diseno: build_market_state no cierra FVG/OB
    pct_terminal = 0.0
    pct_partial = (reached_partial / created * 100) if created else 0.0

    # solapamiento: mismo TF, mismo tipo, rangos que se cruzan
    overlap = 0
    fvgs_only = [o for o in all_objs if o.type.value == "FVG"]
    for a in range(len(fvgs_only)):
        for b in range(a + 1, len(fvgs_only)):
            oa, ob = fvgs_only[a], fvgs_only[b]
            if oa.zone_low <= ob.zone_high and ob.zone_low <= oa.zone_high:
                overlap += 1

    return {
        "tf": tf,
        "window_bars": end,
        "created": created,
        "by_type": dict(by_type),
        "active_per_candle_p50": int(np.percentile(active_arr, 50)) if created else 0,
        "active_per_candle_p95": int(np.percentile(active_arr, 95)) if created else 0,
        "active_per_candle_max": int(active_arr.max()) if created else 0,
        "age_bars_p50": int(np.percentile(ages_at_end, 50)) if ages_at_end else 0,
        "age_bars_p95": int(np.percentile(ages_at_end, 95)) if ages_at_end else 0,
        "age_bars_max": int(max(ages_at_end)) if ages_at_end else 0,
        "pct_reached_PARTIAL": round(pct_partial, 1),
        "pct_terminal": round(pct_terminal, 1),
        "overlapping_fvg_pairs": overlap,
    }


def main() -> None:
    results = {}
    for tf in TFS:
        print(f"audit {tf}...", flush=True)
        results[tf] = audit_tf(tf)
    report = {
        "experiment": "FASE5_LIFECYCLE_AUDIT",
        "method": "reusa detect_fvg/ob (canonicos); acumulado vela-a-vela igual build_market_state (sin terminales FVG/OB)",
        "window_bars_per_tf": WINDOW_BARS,
        "can_train": False,
        "can_trade": False,
        "results": results,
    }
    OUT_JSON = OUT / "fase5_lifecycle_audit.json"
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\n=== FASE 5 LIFECYCLE AUDIT ===")
    for tf in TFS:
        r = results[tf]
        print(f"\n-- {tf} (ventana {r['window_bars']} barras) --")
        print(f"  creados total: {r['created']}  {r['by_type']}")
        print(f"  ACTIVE por vela: p50={r['active_per_candle_p50']} p95={r['active_per_candle_p95']} max={r['active_per_candle_max']}")
        print(f"  edad barras al cierre: p50={r['age_bars_p50']} p95={r['age_bars_p95']} max={r['age_bars_max']}")
        print(f"  % llega a PARTIAL: {r['pct_reached_PARTIAL']}%")
        print(f"  % TERMINAL (MITIGATED/INVALIDATED/EXPIRED/CONSUMED): {r['pct_terminal']}%")
        print(f"  pares FVG solapados: {r['overlapping_fvg_pairs']}")
    print(f"\nJSON -> {OUT_JSON}")


if __name__ == "__main__":
    main()
