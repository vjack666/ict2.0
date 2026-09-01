#!/usr/bin/env python3
"""Probe P2-ALT: (a) semantica de timestamps H1/H4, (b) PIT FULL==PREFIX de las
columnas de ESTRUCTURA de build_features(H4) (bos_direction / choch_signal /
bos_status / choch_status).

Comparacion FULL vs PREFIX sobre TODO el prefijo (no solo la ultima barra):
detecta reescritura retroactiva de etiquetas.
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

DS = ROOT / "datasets/eurusd_dukascopy_20y"
h1 = pd.read_csv(DS / "EURUSD_H1.csv")
h4 = pd.read_csv(DS / "EURUSD_H4.csv")

print("H1 head times:", list(h1["time"].head(4)))
print("H4 head times:", list(h4["time"].head(4)))
print("H4 hours seen:", sorted(pd.to_datetime(h4["time"]).dt.hour.unique())[:12])
print("H1 hours seen:", sorted(pd.to_datetime(h1["time"]).dt.hour.unique())[:6], "...")
d = pd.to_datetime(h4["time"]).diff().dropna().value_counts().head(4)
print("H4 time deltas:\n", d.to_string())

t0 = time.time()
full = build_features(h4)
print(f"\nbuild_features(H4 full, {len(h4)} rows) took {time.time()-t0:.1f}s")

COLS = ["bos_direction", "choch_signal", "bos_dir", "choch_dir",
        "bos_status", "choch_status", "trend"]
n = len(h4)
cuts = [int(n * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
viol = {c: 0 for c in COLS}
lastbar_viol = {c: 0 for c in COLS}
for cut in cuts:
    pref = build_features(h4.iloc[: cut + 1].copy())
    for c in COLS:
        a = full[c].iloc[: cut + 1].astype(str).to_numpy()
        b = pref[c].astype(str).to_numpy()
        nv = int((a != b).sum())
        viol[c] += nv
        if str(full[c].iloc[cut]) != str(pref[c].iloc[cut]):
            lastbar_viol[c] += 1
    print(f"cut={cut}: " + " ".join(
        f"{c}={int((full[c].iloc[:cut+1].astype(str).to_numpy() != pref[c].astype(str).to_numpy()).sum())}"
        for c in COLS))

print("\n=== TOTAL prefix-wide violations (FULL vs PREFIX) ===")
for c in COLS:
    print(f"  {c}: whole_prefix={viol[c]}  last_bar_only={lastbar_viol[c]}")
