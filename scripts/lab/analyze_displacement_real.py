#!/usr/bin/env python3
"""Análisis rápido de displacement sobre datos reales — muestreo representativo."""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path

raw = Path('data/raw/EURUSD')

print("=" * 60)
print("ANÁLISIS DE DISPLACEMENT SOBRE DATOS REALES")
print("=" * 60)

# M5: muestreo de 50K filas espaciadas uniformemente
print("\n--- EURUSD M5 (50K muestra uniforme de 339K) ---")
df5 = pd.read_parquet(raw / 'EURUSD_M5.parquet')
sample_idx = np.linspace(0, len(df5)-1, 50000, dtype=int)
df5_s = df5.iloc[sample_idx]
print(f"  {len(df5_s)} filas, {df5_s.time.min().date()} -> {df5_s.time.max().date()}")

from detectors.displacement import detect_displacement as det_disp
r = det_disp(df5_s)
bull = int(r['displacement_bullish'].sum())
bear = int(r['displacement_bearish'].sum())
t = bull + bear
print(f"  det_disp (1.5x rango 14v, wick<0.4):")
print(f"    bull={bull} ({bull/len(df5_s)*100:.2f}%)  bear={bear} ({bear/len(df5_s)*100:.2f}%)")
print(f"    TOTAL={t} ({t/len(df5_s)*100:.2f}%)")
m = r.loc[r.displacement_bullish | r.displacement_bearish, 'displacement_magnitude']
if len(m):
    print(f"    magnitud: media={m.mean():.2f}x  mediana={m.median():.2f}x")
    print(f"    >=2x:{int((m>=2).sum())}  >=3x:{int((m>=3).sum())}  >=4x:{int((m>=4).sum())}  >=5x:{int((m>=5).sum())}")

from engine.detectors.displacement import detect_displacement as eng_disp
r2 = eng_disp(df5_s)
if len(r2):
    tb = int(r2['displacement_bullish'].sum())
    te = int(r2['displacement_bearish'].sum())
    tt = tb + te
    print(f"  eng_disp (0.50, lookback 2, min 1.5 pips, rompe estructura):")
    print(f"    bull={tb} ({tb/len(df5_s)*100:.2f}%)  bear={te} ({te/len(df5_s)*100:.2f}%)")
    print(f"    TOTAL={tt} ({tt/len(df5_s)*100:.2f}%)")
    print(f"    body/range medio: {r2['body_to_range_ratio'].mean():.2%}")
    print(f"    body pips medio:  {r2['body'].mean()/0.0001:.1f}")
    print(f"    broke_high: {r2['broke_high'].notna().sum()}  broke_low: {r2['broke_low'].notna().sum()}")
else:
    print(f"  eng_disp: VACIO")

print()
print("=" * 60)
print("VISTA DE EJEMPLOS REALES (primeros 10 displacement det_disp)")
print("=" * 60)
disp_rows = r[r.displacement_bullish | r.displacement_bearish].head(10)
for _, row in disp_rows.iterrows():
    direction = "BULL" if row.displacement_bullish else "BEAR"
    print(f"  {row.time}  {direction}  body/range={row.displacement_magnitude:.2f}x  "
          f"open={row.open:.5f} close={row.close:.5f}  "
          f"high={row.high:.5f} low={row.low:.5f}")
