#!/usr/bin/env python3
"""Probe: que columnas de ESTRUCTURA expone build_features(H4)? (P2-ALT recon)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_features import build_features

df = pd.read_csv(ROOT / "datasets/eurusd_dukascopy_20y/EURUSD_H4.csv")
print("H4 rows:", len(df))
ann = build_features(df)
print("n cols:", len(ann.columns))
for c in ann.columns:
    print("  ", c, "|", ann[c].dtype)

print("\n--- candidatas estructura ---")
for c in ann.columns:
    lc = c.lower()
    if any(k in lc for k in ("bos", "choch", "struct", "break", "trend", "swing", "mss")):
        vc = ann[c].value_counts(dropna=False).head(8)
        print(f"\n{c} ({ann[c].dtype}):")
        print(vc.to_string())
