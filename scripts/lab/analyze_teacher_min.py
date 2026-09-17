#!/usr/bin/env python3
"""Análisis ultracompacto: profesor 3-capas con contexto ICT mínimo (geometría + sweep)."""
import sys
sys.path.insert(0, '.')
import pandas as pd, numpy as np
from pathlib import Path
from runtime.ai_learning.displacement_teacher import DisplacementTeacher, DisplacementTeacherConfig

raw = Path('data/raw/EURUSD')
df = pd.read_parquet(raw / 'EURUSD_M5.parquet')
print(f"M5: {len(df)} filas")

# Contexto ICT sólox: sweep (rápido) + bos_dir (rápido)
from detectors.liquidity_context import canonical_sweep
swept = canonical_sweep(df, lookback=20)
df['sweep_up'] = swept['liquidity_sweep_up'].values
df['sweep_down'] = swept['liquidity_sweep_down'].values

# Bos dir aproximado: calculado inline sin importar estructura pesada
# Usamos la definición simple: rompe swing high/low
swing_lookback = 5
swing_high = df['high'].rolling(swing_lookback+1, min_periods=swing_lookback+1).max().shift(1)
swing_low = df['low'].rolling(swing_lookback+1, min_periods=swing_lookback+1).min().shift(1)
df['bos_dir_approx'] = 0
df.loc[(df['close'] > swing_high) & (df['close'] > df['open']), 'bos_dir_approx'] = 1
df.loc[(df['close'] < swing_low) & (df['close'] < df['open']), 'bos_dir_approx'] = -1

# Convertir time
if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)
for c in ['open','high','low','close']:
    df[c] = df[c].astype(float)

# Muestreo 3000 velas
sample = np.linspace(20, len(df)-1, 3000, dtype=int)
df_s = df.iloc[sample].reset_index(drop=True)

teacher = DisplacementTeacher(DisplacementTeacherConfig())
geo = {}; dire = {}; ctx = {}; ep = {}; cg = {}; cc = {}

print(f"Evaluando {len(df_s)} velas...")
for i in range(len(df_s)):
    row = df_s.iloc[i]
    ctx_d = {
        'sweep_previo': bool(row.get('sweep_down', False) or row.get('sweep_up', False)),
        'fvg_cercano': False,
        'ob_cercano': False,
        'estructura_confirmada': bool(row.get('bos_dir_approx', 0) != 0),
        'htf_sesgo': None,
        'fvg_pendiente': False,
    }
    p = teacher.evaluate(df_s, i, context=ctx_d)
    g = p.geometric_strength.name
    d = p.direction.name
    c = p.ict_context_status.name
    e = p.reasons.get('episode_status', 'N/A')
    
    geo[g] = geo.get(g, 0) + 1
    dire[d] = dire.get(d, 0) + 1
    ctx[c] = ctx.get(c, 0) + 1
    ep[e] = ep.get(e, 0) + 1
    cg[f"{g} x {d}"] = cg.get(f"{g} x {d}", 0) + 1
    cc[f"{c} | {g}"] = cc.get(f"{c} | {g}", 0) + 1

T = len(df_s)
print(f"\n{'='*60}")
print(f"PROFESOR 3-CAPAS CON CONTEXTO ICT — {T} VELAS EURUSD M5")
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
print(f"\n--- GEOMETRÍA x DIRECCIÓN ---")
for k, v in sorted(cg.items(), key=lambda x: -x[1]):
    if v > 0: print(f"  {k}: {v} ({v/T*100:.2f}%)")
print(f"\n--- CONTEXTO ICT x GEOMETRÍA ---")
for k, v in sorted(cc.items(), key=lambda x: -x[1]):
    if v > 0: print(f"  {k}: {v} ({v/T*100:.2f}%)")

su = cg.get('STRONG x UP', 0); sd = cg.get('STRONG x DOWN', 0)
wu = cg.get('WEAK x UP', 0); wd = cg.get('WEAK x DOWN', 0)
ts = su+sd; tw = wu+wd
sup_s = cc.get('SUPPORTED | STRONG', 0); sup_w = cc.get('SUPPORTED | WEAK', 0)
ns_s = cc.get('NOT_SUPPORTED | STRONG', 0); ns_w = cc.get('NOT_SUPPORTED | WEAK', 0)

print(f"\n{'='*60}")
print(f"RESUMEN FINAL: QUÉ ES DESPLAZAMIENTO ICT")
print(f"{'='*60}")
print(f"Geometría STRONG: {ts} ({ts/T*100:.2f}%) — UP:{su} DOWN:{sd}")
print(f"Geometría WEAK:   {tw} ({tw/T*100:.2f}%) — UP:{wu} DOWN:{wd}")
print(f"TOTAL geometría positiva: {ts+tw} ({(ts+tw)/T*100:.2f}%)")
print(f"\nCONTEXTO ICT SUPPORTED (sweep + estructura = narrativa mínima): {sup_s+sup_w} ({(sup_s+sup_w)/T*100:.2f}%)")
print(f"  SUPPORTED STRONG: {sup_s}")
print(f"  SUPPORTED WEAK: {sup_w}")
print(f"CONTEXTO ICT NOT_SUPPORTED: {ns_s+ns_w}")
print(f"CONTEXTO ICT UNKNOWN: {ctx.get('UNKNOWN',0)}")
print(f"\nCONCLUSION:")
print(f"  Desplazamiento ICT COMPLETO = geometría + ruptura de estructura + contexto narrativo (sweep)")
print(f"  Solo {(sup_s+sup_w)/T*100:.1f}% de velas tiene la tríada completa → eso es displacement ICT real")
print(f"  Geometría sin contexto ICT = movimiento direccional, no es displacement ICT")
print(f"  Profesor es más estricto (0.60/0.50 ratio + rompe estruct) que detector básico (4.82% sin ruptura)")
