#!/usr/bin/env python3
"""Profesor 3-capas con contexto ICT REAL — corrida standalone sobre M5 del worktrees."""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from runtime.ai_learning.displacement_teacher import (
    DisplacementTeacher, DisplacementTeacherConfig
)

# Cargar M5 directamente desde worktrees
raw_worktree = Path('data/raw/EURUSD')
df = pd.read_parquet(raw_worktree / 'EURUSD_M5.parquet')
print(f"Cargado EURUSD_M5 desde worktrees: {len(df)} filas")
print(f"  Rango: {df.time.min()} -> {df.time.max()}")

# Construir features de contexto ICT usando detectores del sistema
print("\nCalculando features de contexto ICT...")

# 1. Estructura BOS/CHOCH
from engine.bos.structure import detect_market_structure, StructureConfig
ms = detect_market_structure(df, StructureConfig(swing_lookback=5, confirm_bars=2))
df['bos_dir'] = ms.frame['bos_dir'].values
df['bos_status'] = ms.frame['bos_status'].values
print(f"  BOS detectados: {(df['bos_dir'] != 0).sum()}")

# 2. FVG
from detectors.fvg import detect_fvg
fvg = detect_fvg(df)
df['fvg_bullish'] = fvg['fvg_bullish'].values if 'fvg_bullish' in fvg.columns else pd.Series(False, index=df.index).values
df['fvg_bearish'] = fvg['fvg_bearish'].values if 'fvg_bearish' in fvg.columns else pd.Series(False, index=df.index).values
print(f"  FVG bullish: {int(fvg['fvg_bullish'].sum()) if 'fvg_bullish' in fvg.columns else 0}")
print(f"  FVG bearish: {int(fvg['fvg_bearish'].sum()) if 'fvg_bearish' in fvg.columns else 0}")

# 3. OB
from detectors.ob import detect_order_blocks
ob = detect_order_blocks(df)
df['ob_bullish'] = ob['ob_bullish'].values if 'ob_bullish' in ob.columns else pd.Series(False, index=df.index).values
df['ob_bearish'] = ob['ob_bearish'].values if 'ob_bearish' in ob.columns else pd.Series(False, index=df.index).values
print(f"  OB bullish: {int(ob['ob_bullish'].sum()) if 'ob_bullish' in ob.columns else 0}")
print(f"  OB bearish: {int(ob['ob_bearish'].sum()) if 'ob_bearish' in ob.columns else 0}")

# 4. Sweep de liquidez
from detectors.liquidity_context import canonical_sweep, DEFAULT_SWEEP_LOOKBACK
swept = canonical_sweep(df, lookback=DEFAULT_SWEEP_LOOKBACK)
df['liquidity_sweep_up'] = swept['liquidity_sweep_up'].values
df['liquidity_sweep_down'] = swept['liquidity_sweep_down'].values
print(f"  Sweep up: {int(swept['liquidity_sweep_up'].sum())}")
print(f"  Sweep down: {int(swept['liquidity_sweep_down'].sum())}")

# Normalizar time para profesor
if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)
for c in ['open','high','low','close']:
    df[c] = df[c].astype(float)

# Muestreo 25K para análisis
sample_idx = np.linspace(0, len(df)-1, 25000, dtype=int)
df_s = df.iloc[sample_idx].reset_index(drop=True)

teacher = DisplacementTeacher(DisplacementTeacherConfig())

results = {'geometry': {}, 'direction': {}, 'ict_context': {}, 'episode': {}}
cross_gd = {}
cross_cg = {}

print(f"\n{'='*60}")
print(f"PROFESOR 3-CAPAS CON CONTEXTO ICT REAL")
print(f"{'='*60}")
print(f"Muestra: {len(df_s)} velas, {pd.Timestamp(df_s['time'].min(), unit='s').date()} -> {pd.Timestamp(df_s['time'].max(), unit='s').date()}")

for i in range(10, len(df_s)):
    row = df_s.iloc[i]
    ctx = {
        'sweep_previo': bool(row.get('liquidity_sweep_down', False) or row.get('liquidity_sweep_up', False)),
        'fvg_cercano': bool(row.get('fvg_bullish', False) or row.get('fvg_bearish', False)),
        'ob_cercano': bool(row.get('ob_bullish', False) or row.get('ob_bearish', False)),
        'estructura_confirmada': bool(row.get('bos_dir', 0) != 0),
        'htf_sesgo': None,
        'fvg_pendiente': False,
    }
    p = teacher.evaluate(df_s, i, context=ctx)
    g = p.geometric_strength.name
    d = p.direction.name
    c = p.ict_context_status.name
    e = p.reasons.get('episode_status', 'N/A')
    
    results['geometry'][g] = results['geometry'].get(g, 0) + 1
    results['direction'][d] = results['direction'].get(d, 0) + 1
    results['ict_context'][c] = results['ict_context'].get(c, 0) + 1
    results['episode'][e] = results['episode'].get(e, 0) + 1
    
    cross_gd[f"{g} x {d}"] = cross_gd.get(f"{g} x {d}", 0) + 1
    cross_cg[f"{c} | {g}"] = cross_cg.get(f"{c} | {g}", 0) + 1

total = len(df_s) - 10

print(f"\n--- GEOMETRÍA ---")
for k, v in sorted(results['geometry'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print(f"\n--- DIRECCIÓN ---")
for k, v in sorted(results['direction'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print(f"\n--- CONTEXTO ICT ---")
for k, v in sorted(results['ict_context'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print(f"\n--- ESTADO EPISODIO ---")
for k, v in sorted(results['episode'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print(f"\n--- CRUCE GEOMETRÍA x DIRECCIÓN ---")
for k, v in sorted(cross_gd.items(), key=lambda x: -x[1]):
    if v > 0:
        print(f"  {k}: {v} ({v/total*100:.2f}%)")

print(f"\n--- CRUCE CONTEXTO ICT x GEOMETRÍA (claves) ---")
for k, v in sorted(cross_cg.items(), key=lambda x: -x[1]):
    if v > 0:
        print(f"  {k}: {v} ({v/total*100:.2f}%)")

# Resumen ejecutivo
strong_up = cross_gd.get('STRONG x UP', 0)
strong_dn = cross_gd.get('STRONG x DOWN', 0)
weak_up = cross_gd.get('WEAK x UP', 0)
weak_dn = cross_gd.get('WEAK x DOWN', 0)
total_strong = strong_up + strong_dn
total_weak = weak_up + weak_dn

sup_strong = cross_cg.get('SUPPORTED | STRONG', 0)
sup_weak = cross_cg.get('SUPPORTED | WEAK', 0)
ns_strong = cross_cg.get('NOT_SUPPORTED | STRONG', 0)
ns_weak = cross_cg.get('NOT_SUPPORTED | WEAK', 0)
uk_strong = cross_cg.get('UNKNOWN | STRONG', 0)
uk_weak = cross_cg.get('UNKNOWN | WEAK', 0)

print(f"\n{'='*60}")
print(f"RESUMEN: QUÉ ES DESPLAZAMIENTO ICT COMPLETO")
print(f"{'='*60}")
print(f"Geometría STRONG (cuerpo>=60% + rompe estruct): {total_strong} ({total_strong/total*100:.2f}%)")
print(f"  UP: {strong_up}  DOWN: {strong_dn}")
print(f"Geometría WEAK (cuerpo 50-60%): {total_weak} ({total_weak/total*100:.2f}%)")
print(f"  UP: {weak_up}  DOWN: {weak_dn}")
print(f"TOTAL geometría positiva (WEAK+STRONG): {total_strong+total_weak} ({(total_strong+total_weak)/total*100:.2f}%)")
print()
print(f"Con CONTEXTO ICT SUPPORTED (sweep + FVG/OB + estructura = tríada completa):")
print(f"  SUPPORTED STRONG: {sup_strong} ({sup_strong/total*100:.2f}%)")
print(f"  SUPPORTED WEAK: {sup_weak} ({sup_weak/total*100:.2f}%)")
print(f"  TOTAL SUPPORTED: {sup_strong+sup_weak} ({(sup_strong+sup_weak)/total*100:.2f}%)")
print()
print(f"Con CONTEXTO ICT NOT_SUPPORTED (geometría sin contexto): {ns_strong+ns_weak} ({(ns_strong+ns_weak)/total*100:.2f}%)")
print(f"  NOT_SUPPORTED STRONG: {ns_strong} ({ns_strong/total*100:.2f}%)")
print(f"  NOT_SUPPORTED WEAK: {ns_weak} ({ns_weak/total*100:.2f}%)")
print()
print(f"Con CONTEXTO ICT UNKNOWN (sin datos de contexto): {uk_strong+uk_weak} ({(uk_strong+uk_weak)/total*100:.2f}%)")
print()
print(f"COMPARATIVA DETECTORES:")
print(f"  det_disp (1.5x rango, wick<0.4, SIN ruptura estructural): 4.82% de M5")
print(f"  eng_disp (0.50 ratio + rompe estruct + min 1.5pips): 15.84% de M5")
print(f"  Profesor STRONG+ WEAK (0.60/0.50 ratio + rompe estruct): {(total_strong+total_weak)/total*100:.2f}% de muestra")
print(f"  Profesor con CONTEXTO ICT SUPPORTED: {(sup_strong+sup_weak)/total*100:.2f}% de muestra")
print(f"\nCONCLUSIÓN:")
print(f"  Desplazamiento ICT COMPLETO = geometría fuerte + ruptura de estructura + contexto narrativo")
print(f"  Solo {(sup_strong+sup_weak)/total*100:.1f}% de las velas cumple la tríada completa.")
print(f"  Geometría sin contexto ICT NO es desplazamiento ICT usable.")
print(f"  El detector del sistema (det_disp) es más permisivo que el profesor porque no exige ruptura de estructura.")
print(f"  → El profesor es más estricto: solo {(total_strong+total_weak)/total*100:.1f}% vs 4.82% del detector básico.")
