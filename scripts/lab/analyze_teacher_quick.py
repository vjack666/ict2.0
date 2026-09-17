#!/usr/bin/env python3
"""Versión rápida: 5K velas, profesor con contexto ICT real."""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from runtime.ai_learning.displacement_teacher import DisplacementTeacher, DisplacementTeacherConfig

raw = Path('data/raw/EURUSD')
df = pd.read_parquet(raw / 'EURUSD_M5.parquet')
print(f"Cargado M5: {len(df)} filas, {df.time.min()} -> {df.time.max()}")

# Features de contexto ICT (rápidas)
from engine.bos.structure import detect_market_structure, StructureConfig
ms = detect_market_structure(df, StructureConfig(swing_lookback=5, confirm_bars=2))
df['bos_dir'] = ms.frame['bos_dir'].values
df['bos_status'] = ms.frame['bos_status'].values

from detectors.fvg import detect_fvg
fvg = detect_fvg(df)
if 'fvg_bullish' in fvg.columns:
    df['fvg_bullish'] = fvg['fvg_bullish'].values
    df['fvg_bearish'] = fvg['fvg_bearish'].values

from detectors.ob import detect_order_blocks
ob = detect_order_blocks(df)
if 'ob_bullish' in ob.columns:
    df['ob_bullish'] = ob['ob_bullish'].values
    df['ob_bearish'] = ob['ob_bearish'].values

from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
swept = canonical_sweep(df, lookback=DEFAULT_SWEEP_LOOKBACK)
df['sweep_up'] = swept['liquidity_sweep_up'].values
df['sweep_down'] = swept['liquidity_sweep_down'].values

if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)
for c in ['open','high','low','close']:
    df[c] = df[c].astype(float)

# Muestreo 5K
sample = np.linspace(10, len(df)-1, 5000, dtype=int)
df_s = df.iloc[sample].reset_index(drop=True)

teacher = DisplacementTeacher(DisplacementTeacherConfig())

geo = {}
dire = {}
ctx = {}
ep = {}
cruz_gd = {}
cruz_cg = {}

print(f"Evaluando {len(df_s)} velas con contexto ICT...")

for i in range(len(df_s)):
    row = df_s.iloc[i]
    ctx_dict = {
        'sweep_previo': bool(row.get('sweep_down', False) or row.get('sweep_up', False)),
        'fvg_cercano': bool(row.get('fvg_bullish', False) or row.get('fvg_bearish', False)),
        'ob_cercano': bool(row.get('ob_bullish', False) or row.get('ob_bearish', False)),
        'estructura_confirmada': bool(row.get('bos_dir', 0) != 0),
        'htf_sesgo': None,
        'fvg_pendiente': False,
    }
    p = teacher.evaluate(df_s, i, context=ctx_dict)
    g = p.geometric_strength.name
    d = p.direction.name
    c = p.ict_context_status.name
    e = p.reasons.get('episode_status', 'N/A')
    
    geo[g] = geo.get(g, 0) + 1
    dire[d] = dire.get(d, 0) + 1
    ctx[c] = ctx.get(c, 0) + 1
    ep[e] = ep.get(e, 0) + 1
    cruz_gd[f"{g} x {d}"] = cruz_gd.get(f"{g} x {d}", 0) + 1
    cruz_cg[f"{c} | {g}"] = cruz_cg.get(f"{c} | {g}", 0) + 1

T = len(df_s)
print(f"\n{'='*60}")
print(f"PROFESOR 3-CAPAS CON CONTEXTO ICT — 5000 VELAS EURUSD M5")
print(f"{'='*60}")
print(f"Rango: {pd.Timestamp(df_s['time'].min(), unit='s').date()} -> {pd.Timestamp(df_s['time'].max(), unit='s').date()}")

print(f"\n--- GEOMETRÍA ---")
for k, v in sorted(geo.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/T*100:.2f}%)")

print(f"\n--- DIRECCIÓN ---")
for k, v in sorted(dire.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/T*100:.2f}%)")

print(f"\n--- CONTEXTO ICT ---")
for k, v in sorted(ctx.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/T*100:.2f}%)")

print(f"\n--- EPISODIO ---")
for k, v in sorted(ep.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/T*100:.2f}%)")

print(f"\n--- CRUCE GEOMETRÍA x DIRECCIÓN ---")
for k, v in sorted(cruz_gd.items(), key=lambda x: -x[1]):
    if v > 0:
        print(f"  {k}: {v} ({v/T*100:.2f}%)")

print(f"\n--- CRUCE CONTEXTO ICT x GEOMETRÍA ---")
for k, v in sorted(cruz_cg.items(), key=lambda x: -x[1]):
    if v > 0:
        print(f"  {k}: {v} ({v/T*100:.2f}%)")

# Resumen
su = cruz_gd.get('STRONG x UP', 0)
sd = cruz_gd.get('STRONG x DOWN', 0)
wu = cruz_gd.get('WEAK x UP', 0)
wd = cruz_gd.get('WEAK x DOWN', 0)
ts = su + sd
tw = wu + wd

sup_s = cruz_cg.get('SUPPORTED | STRONG', 0)
sup_w = cruz_cg.get('SUPPORTED | WEAK', 0)
ns_s = cruz_cg.get('NOT_SUPPORTED | STRONG', 0)
ns_w = cruz_cg.get('NOT_SUPPORTED | WEAK', 0)

print(f"\n{'='*60}")
print(f"RESUMEN: QUÉ ES DESPLAZAMIENTO ICT")
print(f"{'='*60}")
print(f"Geometría STRONG (cuerpo>=60% + rompe estruct): {ts} ({ts/T*100:.2f}%)")
print(f"  UP: {su}  DOWN: {sd}")
print(f"Geometría WEAK (cuerpo 50-60%): {tw} ({tw/T*100:.2f}%)")
print(f"  UP: {wu}  DOWN: {wd}")
print(f"TOTAL geometría positiva: {ts+tw} ({(ts+tw)/T*100:.2f}%)")
print()
print(f"CONTEXTO ICT SUPPORTED (triada completa): {sup_s+sup_w} ({(sup_s+sup_w)/T*100:.2f}%)")
print(f"  SUPPORTED STRONG: {sup_s}")
print(f"  SUPPORTED WEAK: {sup_w}")
print(f"CONTEXTO ICT NOT_SUPPORTED (geometría sin contexto): {ns_s+ns_w}")
print(f"CONTEXTO ICT UNKNOWN: {ctx.get('UNKNOWN',0)}")
print(f"\nCONCLUSIÓN:")
print(f"  Desplazamiento ICT COMPLETO = geometría fuerte + ruptura estructural + contexto narrativo")
print(f"  Solo {(sup_s+sup_w)/T*100:.1f}% de velas tiene la tríada completa.")
print(f"  Geometría sin contexto NO es desplazamiento ICT usable para entrada.")
print(f"  El profesor es más estricto que el detector simple (4.82%) porque exige ruptura de estructura.")
print(f"  → El detector sencillo marca 4.82% pero el profesor con contexto solo acepta {(sup_s+sup_w)/T*100:.1f}%")
print(f"  → Diferencia: contexto ICT filtra la mayoría de los 'impulsores geométricos' sin narrativa.")
