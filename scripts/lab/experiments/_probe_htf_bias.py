#!/usr/bin/env python3
"""PROBE (no experimento): valida que se puede precomputar el timeline de sesgo
HTF equivalente EXACTO a engine.plan._bias_from_frame.

Motivo: _bias_from_frame hace un bucle Python con .iloc sobre todas las filas
<= t. Llamarlo una vez por entrada (cientos de entradas x 2 TFs x miles de
filas) es inviable. Precomputamos un array bias_by_bar[k] en UNA pasada y
VERIFICAMOS equivalencia contra la funcion del motor en una muestra.
Si no es equivalente -> el experimento se declara BLOCKED (no se inventa).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_features import build_features
from engine.plan import _bias_from_frame

DATA = ROOT / "datasets" / "eurusd_dukascopy_20y"


def bias_timeline(df: pd.DataFrame) -> list[str]:
    """Replica EXACTA de _bias_from_frame en una pasada acumulativa.

    Semantica del motor (engine/plan.py:_bias_from_frame): recorre todas las
    filas con time <= t; guarda el ULTIMO bos activo y el ULTIMO choch activo;
    si existe CUALQUIER choch activo -> manda el choch; si no, manda el bos.
    """
    has_bos = "bos_dir" in df.columns and "bos_status" in df.columns
    if not has_bos:
        raise RuntimeError("frame sin anotar (falta bos_dir/bos_status)")
    has_real = "bos_real" in df.columns
    bd = df["bos_dir"].tolist()
    bs = df["bos_status"].astype(str).tolist()
    br = df["bos_real"].tolist() if has_real else [None] * len(df)
    cd = df["choch_dir"].tolist() if "choch_dir" in df.columns else [0] * len(df)
    cs = (
        df["choch_status"].astype(str).tolist()
        if "choch_status" in df.columns
        else ["none"] * len(df)
    )
    out: list[str] = []
    last_bos_dir = 0
    last_choch_dir = 0
    for i in range(len(df)):
        if bd[i] not in (0, "0", None) and bs[i] == "active" and (not has_real or bool(br[i])):
            last_bos_dir = int(bd[i])
        if cd[i] not in (0, "0", None) and cs[i] == "active":
            last_choch_dir = int(cd[i])
        if last_choch_dir != 0:
            out.append("BULLISH" if last_choch_dir > 0 else "BEARISH")
        elif last_bos_dir != 0:
            out.append("BULLISH" if last_bos_dir > 0 else "BEARISH")
        else:
            out.append("RANGING")
    return out


def main() -> None:
    for tf in ("D1", "H4"):
        t0 = time.time()
        raw = pd.read_csv(DATA / f"EURUSD_{tf}.csv")
        print(f"[{tf}] raw rows={len(raw)}", flush=True)
        ann = build_features(raw)
        print(f"[{tf}] build_features OK in {time.time()-t0:.1f}s cols={len(ann.columns)}", flush=True)
        need = ["bos_dir", "bos_status", "choch_dir", "choch_status", "trend"]
        print(f"[{tf}] required cols present: {[c in ann.columns for c in need]}", flush=True)
        print(f"[{tf}] bos_real present: {'bos_real' in ann.columns}", flush=True)

        tl = bias_timeline(ann)
        times = pd.to_datetime(ann["time"], utc=True, errors="coerce")
        # muestra de barras repartidas por todo el frame
        n = len(ann)
        sample = [int(round(x)) for x in
                  [n * f for f in (0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95)]]
        sample = [min(max(k, 0), n - 1) for k in sample]
        bad = 0
        for k in sample:
            t = times.iloc[k]
            ref = _bias_from_frame(ann, t)
            got = tl[k]
            if ref != got:
                bad += 1
                print(f"[{tf}] MISMATCH bar={k} t={t} engine={ref} timeline={got}", flush=True)
        print(f"[{tf}] equivalence sample={len(sample)} mismatches={bad}", flush=True)
        dist = pd.Series(tl).value_counts().to_dict()
        print(f"[{tf}] bias distribution over bars: {dist}", flush=True)
        print("-" * 60, flush=True)


if __name__ == "__main__":
    main()
