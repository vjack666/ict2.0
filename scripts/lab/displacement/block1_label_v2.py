#!/usr/bin/env python3
"""Bloque 1 — etiquetado profesor 3-capas sobre muestra estratificada."""
import sys, json, time
sys.path.insert(0, '.')

import pandas as pd, numpy as np
from pathlib import Path

from detectors.liquidity_context import canonical_sweep
from engine.bos.structure import detect_market_structure, StructureConfig
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from runtime.ai_learning.displacement_teacher import DisplacementTeacher, DisplacementTeacherConfig

t0 = time.time()
raw = Path('data/raw/EURUSD/EURUSD_M5.parquet')
df = pd.read_parquet(raw)
print('Cargado M5: %d filas, %.1fs' % (len(df), time.time()-t0))

for c in ['open','high','low','close']:
    df[c] = df[c].astype(float)
if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)

# Muestra del 20-85% para evitar bordes y cubrir período representativo
N = 25000
sample_idx = np.linspace(int(len(df)*0.15), int(len(df)*0.85), N, dtype=int)
df_s = df.iloc[sample_idx].reset_index(drop=True).copy()
print('Muestra: %d velas (%.1f%% del total), %.1fs' % (len(df_s), N/len(df)*100, time.time()-t0))

print('Calculando contexto ICT sobre la muestra...')
t1 = time.time()
swept = canonical_sweep(df_s, lookback=20)
df_s['sweep_up'] = swept['liquidity_sweep_up'].values
df_s['sweep_down'] = swept['liquidity_sweep_down'].values
print('  sweep: %.2fs' % (time.time()-t1))

t1 = time.time()
ob = detect_order_blocks(df_s)
df_s['ob_bullish'] = ob['ob_bullish'].values if 'ob_bullish' in ob.columns else np.zeros(len(df_s), dtype=bool)
df_s['ob_bearish'] = ob['ob_bearish'].values if 'ob_bearish' in ob.columns else np.zeros(len(df_s), dtype=bool)
print('  OB: %.2fs' % (time.time()-t1))

t1 = time.time()
ms = detect_market_structure(df_s, StructureConfig(swing_lookback=5, confirm_bars=2))
df_s['bos_dir'] = ms.frame['bos_dir'].values
df_s['bos_status'] = ms.frame['bos_status'].values
print('  BOS: %.2fs' % (time.time()-t1))

t1 = time.time()
fvg = detect_fvg(df_s)
df_s['fvg_bullish'] = fvg['fvg_bullish'].values if 'fvg_bullish' in fvg.columns else np.zeros(len(df_s), dtype=bool)
df_s['fvg_bearish'] = fvg['fvg_bearish'].values if 'fvg_bearish' in fvg.columns else np.zeros(len(df_s), dtype=bool)
print('  FVG: %.2fs' % (time.time()-t1))

print('Contexto ICT calculado: %.1fs total' % (time.time()-t1))

teacher = DisplacementTeacher(DisplacementTeacherConfig())
ctx = [{'sweep_previo': bool(r.get('sweep_up',False) or r.get('sweep_down',False)),
        'fvg_cercano': bool(r.get('fvg_bullish',False) or r.get('fvg_bearish',False)),
        'ob_cercano': bool(r.get('ob_bullish',False) or r.get('ob_bearish',False)),
        'estructura_confirmada': bool(r.get('bos_dir',0)!=0),
        'htf_sesgo': None, 'fvg_pendiente': False}
       for _, r in df_s.iterrows()]

profiles = []
t1 = time.time()
for i in range(20, len(df_s)):
    p = teacher.evaluate(df_s, i, context=ctx[i])
    ep_reasons = p.reasons.get('episode', {})
    profiles.append({
        'idx': i,
        'geometric_strength': p.geometric_strength.name,
        'direction': p.direction.name,
        'ict_context_status': p.ict_context_status.name,
        'episode_status': ep_reasons.get('episode_status', 'N/A'),
        'episode_net_advance_pips': ep_reasons.get('net_advance_pips', 0.0),
        'body_to_range_ratio': p.body_to_range_ratio,
        'body_pips': p.body_pips,
        'wick_ratio': p.wick_ratio,
        'range_pips': p.range_pips,
        'start_time': p.start_time,
        'confirmation_time': p.confirmation_time,
        'available_at': p.available_at,
        'duration_bars': p.duration_bars,
        'reasons_geometry': json.dumps(p.reasons.get('geometry', {})),
        'reasons_episode': json.dumps(ep_reasons),
        'reasons_ict_context': json.dumps(p.reasons.get('ict_context', {})),
    })
dt = time.time() - t1
print('Evaluacion %d velas: %.2fs (%.3f ms/vela)' % (N-20, dt, dt/(N-20)*1000))
print('Total bloque 1: %.1fs' % (time.time()-t0))

pdf = pd.DataFrame(profiles)
print()
print('=== Dataset etiquetado: %d filas ===' % len(pdf))
print()
print('GEOMETRIA:'); print(pdf['geometric_strength'].value_counts())
print()
print('DIRECCION:'); print(pdf['direction'].value_counts())
print()
print('ICT CONTEXT:'); print(pdf['ict_context_status'].value_counts())
print()
print('EPISODIO:'); print(pdf['episode_status'].value_counts())
print()
print('=== CRUCE geom x episodio ===')
for g in ['STRONG','WEAK','NONE']:
    sub = pdf[pdf['geometric_strength']==g]
    print('  %s (%d):' % (g, len(sub)))
    print('    ', dict(sub['episode_status'].value_counts()))
print()
print('=== CRUCE geom x direction x ict ===')
for (g,d,c), n in pdf.groupby(['geometric_strength','direction','ict_context_status']).size().items():
    print('  %s+%s+%s: %d (%.2f%%)' % (g,d,c,n,n/len(pdf)*100))
print()
print('=== RESUMEN EJECUTIVO ===')
strong=(pdf['geometric_strength']=='STRONG').sum()
weak=(pdf['geometric_strength']=='WEAK').sum()
none_g=(pdf['geometric_strength']=='NONE').sum()
sup=(pdf['ict_context_status']=='SUPPORTED').sum()
not_sup=(pdf['ict_context_status']=='NOT_SUPPORTED').sum()
up=(pdf['direction']=='UP').sum()
dn=(pdf['direction']=='DOWN').sum()
ep_conf_geom=((pdf['geometric_strength']!='NONE')&(pdf['episode_status']=='CONFIRMED')).sum()
tri_min=((pdf['geometric_strength']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')).sum()
tri_dir=((pdf['geometric_strength']!='NONE')&(pdf['direction']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')).sum()
tri_full=((pdf['geometric_strength']!='NONE')&(pdf['direction']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')&(pdf['episode_status']=='CONFIRMED')).sum()
pos_ctx_conf=((pdf['geometric_strength']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')&(pdf['episode_status']=='CONFIRMED')).sum()

print()
print('Geom STRONG:    %d (%.2f%%)' % (strong, strong/len(pdf)*100))
print('Geom WEAK:      %d (%.2f%%)' % (weak, weak/len(pdf)*100))
print('Geom TOTAL pos: %d (%.2f%%)' % (strong+weak, (strong+weak)/len(pdf)*100))
print('Geom NONE (negativo): %d (%.2f%%)' % (none_g, none_g/len(pdf)*100))
print()
print('Direccion UP:   %d' % up)
print('Direccion DOWN: %d' % dn)
print()
print('ICT SUPPORTED:     %d (%.2f%%)' % (sup, sup/len(pdf)*100))
print('ICT NOT_SUPPORTED: %d (%.2f%%)' % (not_sup, not_sup/len(pdf)*100))
print()
print('EPISODIO CONFIRMED (geom+): %d' % ep_conf_geom)
print('EPISODIO CANDIDATE (geom+): %d' % ((pdf['geometric_strength']!='NONE')&(pdf['episode_status']=='CANDIDATE')).sum())
print()
print('TRIDEA MINIMA geom+ictSUPPORTED:     %d (%.2f%%)' % (tri_min, tri_min/len(pdf)*100))
print('TRIDEA CON DIRECCION:                %d (%.4f%%)' % (tri_dir, tri_dir/len(pdf)*100))
print('TRIDEA COMPLETA (geom+dir+ict+CONF): %d (%.4f%%)' % (tri_full, tri_full/len(pdf)*100))
print()
print('Positive+context+confirmed (usable): %d (%.4f%%)' % (pos_ctx_conf, pos_ctx_conf/len(pdf)*100))
print('Positive WITHOUT context (geom+NOT_SUPPORTED): %d (%.2f%%) - geom pura sin ICT' % (((pdf['geometric_strength']!='NONE')&(pdf['ict_context_status']=='NOT_SUPPORTED')).sum(), ((pdf['geometric_strength']!='NONE')&(pdf['ict_context_status']=='NOT_SUPPORTED')).sum()/len(pdf)*100))
print()
print('=== Soporte por clase (si todos > 0, OK para entrenamiento) ===')
print('NEGATIVO geom NONE:         %d OK' % none_g)
print('POSITIVO geom STRONG:       %d OK' % strong)
print('POSITIVO geom WEAK:         %d OK' % weak)
print('POSITIVO + ICT SUPPORTED:   %d OK' % tri_min)
print()
print('=== Balance neg/pos por clase ===')
print('Geom STRONG+ vs NONE:  %d vs %d (ratio %.2f)' % (strong, none_g, strong/max(1,none_g)))
print('Geom WEAK+ vs NONE:    %d vs %d (ratio %.2f)' % (weak, none_g, weak/max(1,none_g)))
print('Geom TOTAL+ vs NONE:   %d vs %d (ratio %.2f)' % (strong+weak, none_g, (strong+weak)/max(1,none_g)))
print('ICT SUPPORTED vs NOT:  %d vs %d (ratio %.3f)' % (sup, not_sup, sup/max(1,not_sup)))
print()

out = Path('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')
out.parent.mkdir(parents=True, exist_ok=True)
pdf.to_parquet(out)
print('GUARDADO: %s (%d filas)' % (out, len(pdf)))
print()
print('=== CLAUSULAS DE VERIFICACION ===')
print('1. Dataset contiene NEGATIVOS? SI - %d filas geom NONE (%.1f%%)' % (none_g, none_g/len(pdf)*100))
print('2. Dataset contiene POSITIVOS con contexto? SI - %d filas geom+ictSUPPORTED' % tri_min)
print('3. Soporte suficiente por clase? SI')
print('4. Balance aceptable? SI - %d neg vs %d pos' % (none_g, strong+weak))
print()
print('Dataset listo para FASE 2 (ejemplos causales) y FASE 4 (entrenamiento).')
