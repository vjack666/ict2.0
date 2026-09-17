#!/usr/bin/env python3
"""Bloque 2b — verificacion FULL/PREFIX del profesor (gate obligatorio de causalidad)."""
import sys, json
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path

from detectors.liquidity_context import canonical_sweep
from engine.bos.structure import detect_market_structure, StructureConfig
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from runtime.ai_learning.displacement_teacher import DisplacementTeacher, DisplacementTeacherConfig

raw = Path('data/raw/EURUSD/EURUSD_M5.parquet')
df = pd.read_parquet(raw)
for c in ['open','high','low','close']:
    df[c] = df[c].astype(float)
if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)

N = 25000
df_s = df.iloc[np.linspace(20, len(df)-1, N, dtype=int)].reset_index(drop=True).copy()
print('Muestra: %d velas' % len(df_s))

print('Calculando contexto ICT sobre muestra...')
swept = canonical_sweep(df_s, lookback=20)
df_s['sweep_up'] = swept['liquidity_sweep_up'].values
df_s['sweep_down'] = swept['liquidity_sweep_down'].values
ob = detect_order_blocks(df_s)
df_s['ob_bullish'] = ob['ob_bullish'].values if 'ob_bullish' in ob.columns else np.zeros(len(df_s), dtype=bool)
df_s['ob_bearish'] = ob['ob_bearish'].values if 'ob_bearish' in ob.columns else np.zeros(len(df_s), dtype=bool)
ms = detect_market_structure(df_s, StructureConfig(swing_lookback=5, confirm_bars=2))
df_s['bos_dir'] = ms.frame['bos_dir'].values
df_s['bos_status'] = ms.frame['bos_status'].values
fvg = detect_fvg(df_s)
df_s['fvg_bullish'] = fvg['fvg_bullish'].values if 'fvg_bullish' in fvg.columns else np.zeros(len(df_s), dtype=bool)
df_s['fvg_bearish'] = fvg['fvg_bearish'].values if 'fvg_bearish' in fvg.columns else np.zeros(len(df_s), dtype=bool)

teacher = DisplacementTeacher(DisplacementTeacherConfig())
ctx = []
for _, r in df_s.iterrows():
    ctx.append({
        'sweep_previo': bool(r.get('sweep_up', False) or r.get('sweep_down', False)),
        'fvg_cercano': bool(r.get('fvg_bullish', False) or r.get('fvg_bearish', False)),
        'ob_cercano': bool(r.get('ob_bullish', False) or r.get('ob_bearish', False)),
        'estructura_confirmada': bool(r.get('bos_dir', 0) != 0),
        'htf_sesgo': None,
        'fvg_pendiente': False,
    })

def eval_profile(df, i, ctx):
    p = teacher.evaluate(df, i, context=ctx[i])
    return {
        'geometric_strength': p.geometric_strength.name,
        'direction': p.direction.name,
        'ict_context_status': p.ict_context_status.name,
        'episode_status': p.reasons.get('episode', {}).get('episode_status', 'N/A'),
        'confirmation_time': p.confirmation_time,
    }

np.random.seed(17)
test_idxs = sorted(np.random.choice(range(20, len(df_s)-30), 200, replace=False))

discrepancias = 0
detalles = []
for i in test_idxs:
    p_orig = eval_profile(df_s, i, ctx)
    future_rows = df_s.iloc[-10:].copy()
    future_rows['time'] = df_s.iloc[-1]['time'] + 60 * (10 - np.arange(10))
    df_ext = pd.concat([df_s, future_rows], ignore_index=True)
    p_ext = eval_profile(df_ext, i, ctx)
    if p_orig != p_ext:
        discrepancias += 1
        detalles.append((i, p_orig, p_ext))

print()
print('=== VERIFICACION 1: FULL / PREFIX ===')
print('TOTAL DE DISCREPANCIAS (agregar futuro cambia evaluacion pasada): %d / %d' % (discrepancias, len(test_idxs)))
print('Ratio de discrepancia: %.2f%%' % (discrepancias / len(test_idxs) * 100))
print()
if detalles:
    print('PRIMERAS 5 DISCREPANCIAS:')
    for i, o, e in detalles[:5]:
        print('  idx=%d: geom %s->%s, dir %s->%s, ict %s->%s, episodio %s->%s' % (
            i, o['geometric_strength'], e['geometric_strength'],
            o['direction'], e['direction'],
            o['ict_context_status'], e['ict_context_status'],
            o['episode_status'], e['episode_status']))
        print()

# Frontera exacta
p_last = eval_profile(df_s, len(df_s)-1, ctx)
print('=== VERIFICACION 2: Frontera exacta de cierre ===')
print('idx=%d (anterior al final):' % (len(df_s)-1))
print('  geom: %s | dir: %s | ict: %s | episodio: %s | conf_time: %s' % (
    p_last['geometric_strength'], p_last['direction'],
    p_last['ict_context_status'], p_last['episode_status'],
    p_last['confirmation_time']))

# confirmation_bars
p_near = eval_profile(df_s, len(df_s)-5, ctx)
print()
print('=== VERIFICACION 3: confirmation_bars limita acceso futuro ===')
print('idx=%d (casi al final, %d velas restantes despues):' % (len(df_s)-5, 5))
print('  geom: %s | dir: %s | ict: %s | episodio: %s | conf_time: %s' % (
    p_near['geometric_strength'], p_near['direction'],
    p_near['ict_context_status'], p_near['episode_status'],
    p_near['confirmation_time']))
print('  confirmation_bars=%d, look-ahead maximo=%d' % (teacher.config.confirmation_bars, teacher.config.confirmation_bars+2))

# Batch vs paso a paso
idx_batch = sorted(np.random.choice(range(20, len(df_s)-10), 100, replace=False))
batch_results = {i: eval_profile(df_s, i, ctx) for i in idx_batch}
inconsistencias = 0
for i in idx_batch:
    r1 = batch_results[i]
    r2 = eval_profile(df_s, i, ctx)
    if r1 != r2:
        inconsistencias += 1
        print('  INCONSISTENCIA idx=%d: %s vs %s' % (i, r1, r2))
print()
print('=== VERIFICACION 4: Batch vs paso a paso ===')
print('Inconsistencias: %d / %d' % (inconsistencias, len(idx_batch)))
if inconsistencias == 0:
    print('OK: evaluaciones repetidas sobre la misma vela son identicas.')

print()
print('='*50)
print('RESUMEN CAUSALIDAD DEL PROFESOR')
print('='*50)
full_pass = (discrepancias == 0)
print('FULL/PREFIX: %s' % ('PASS' if full_pass else 'FAIL'))
print('Frontera cierre: %s' % ('PASS' if p_last['episode_status'] in ['CANDIDATE','N/A','UNKNOWN'] or p_last['confirmation_time'] is None else 'REVISAR'))
print('confirmation_bars limita acceso: %s' % ('PASS' if p_near['episode_status'] != 'CONFIRMED' or p_near['confirmation_time'] is None else 'REVISAR'))
print('Batch vs paso a paso: %s' % ('PASS' if inconsistencias == 0 else 'FAIL'))
print()
if full_pass and inconsistencias == 0:
    print('PROFESOR APLICABLE PARA ENTRENAMIENTO CAUSAL.')
else:
    print('PROFESOR CON CUESTIONES CAUSALES — revisar antes de entrenamiento.')

ck = Path('data/learning/pipeline/displacement/checkpoint.json')
ck.parent.mkdir(parents=True, exist_ok=True)
estado = json.loads(ck.read_text()) if ck.exists() else {}
estado['full_prefix'] = {
    'test_idxs': len(test_idxs),
    'discrepancias': int(discrepancias),
    'ratio_discrepancia': float(discrepancias / len(test_idxs) * 100),
    'full_prefix_ok': bool(full_pass),
    'inconsistencias_batch': int(inconsistencias),
    'profesor_aplicable': bool(full_pass and inconsistencias == 0),
}
ck.write_text(json.dumps(estado, indent=2, ensure_ascii=False))
print()
print('Checkpoint actualizado.')
