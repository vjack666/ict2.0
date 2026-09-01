#!/usr/bin/env python3
"""SMOKE: build_features('trend') sobre D1/H4 + verificacion CAUSAL FULL-vs-PREFIX.

No escribe artefactos de experimento. Solo comprueba que:
 1. build_features corre sobre D1 y H4 del dataset canonico.
 2. La columna 'trend' tiene estados persistentes BULLISH/BEARISH/RANGING.
 3. trend[i] calculado sobre FULL == trend[i] calculado sobre PREFIX iloc[:i+1]
    (si esto se cumple, el sesgo HTF es PIT-safe y NO hay leakage).
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

DS = ROOT / "datasets" / "eurusd_dukascopy_20y"

for tf in ("D1", "H4"):
    p = DS / f"EURUSD_{tf}.csv"
    df = pd.read_csv(p)
    print(f"\n=== {tf}: rows={len(df)} cols={list(df.columns)}")
    t0 = time.time()
    feat = build_features(df)
    print(f"build_features OK in {time.time()-t0:.1f}s  n_cols={len(feat.columns)}")
    print("has 'trend':", "trend" in feat.columns)
    vc = feat["trend"].value_counts(dropna=False).to_dict()
    print("trend value_counts:", vc)
    print("head trend:", list(feat["trend"].head(12)))

    # --- CAUSAL CHECK: FULL vs PREFIX on the trend column ---
    idxs = [len(df) // 5, len(df) // 3, len(df) // 2, int(len(df) * 0.7), len(df) - 50]
    viol = 0
    for i in idxs:
        pref = build_features(df.iloc[: i + 1].copy())
        a = feat["trend"].iloc[i]
        b = pref["trend"].iloc[i]
        ok = a == b
        if not ok:
            viol += 1
        print(f"  bar {i}: FULL={a!r} PREFIX={b!r} {'OK' if ok else 'VIOLATION'}")
    print(f"{tf} causal violations: {viol}/{len(idxs)}")
