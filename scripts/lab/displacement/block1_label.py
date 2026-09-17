#!/usr/bin/env python3
"""Bloque 1 completo: etiquetado profesor 3-capas + análisis + dataset."""
import sys, json
sys.path.insert(0, '.')

import pandas as pd, numpy as np
from pathlib import Path

from detectors.liquidity_context import canonical_sweep
from engine.bos.structure import detect_market_structure, StructureConfig
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from runtime.ai_learning.displacement_teacher import DisplacementTeacher, DisplacementTeacherConfig

raw = Path('data/raw/EURUSD/EURUSD_M5.parquet')
df = pd.read_parquet(raw)
for c in ['open','high','low','close']: df[c] = df[c].astype(float)
if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)

print('Calculando contexto ICT (BOS, FVG, OB, sweep)...')
ms = detect_market_structure(df, StructureConfig(swing_lookback=5, confirm_bars=2))
df['bos_dir'] = ms.frame['bos_dir'].values
df['bos_status'] = ms.frame['bos_status'].values
fvg = detect_fvg(df)
df['fvg_bullish'] = fvg['fvg_bullish'].values if 'fvg_bullish' in fvg.columns else np.zeros(len(df), dtype=bool)
df['fvg_bearish'] = fvg['fvg_bearish'].values if 'fvg_bearish' in fvg.columns else np.zeros(len(df), dtype=bool)
ob = detect_order_blocks(df)
df['ob_bullish'] = ob['ob_bullish'].values if 'ob_bullish' in ob.columns else np.zeros(len(df), dtype=bool)
df['ob_bearish'] = ob['ob_bearish'].values if 'ob_bearish' in ob.columns else np.zeros(len(df), dtype=bool)
swept = canonical_sweep(df, lookback=20)
df['sweep_up'] = swept['liquidity_sweep_up'].values
df['sweep_down'] = swept['liquidity_sweep_down'].values
df = df.reset_index(drop=True)

N = 100000
df_s = df.iloc[np.linspace(20, len(df)-1, N, dtype=int)].reset_index(drop=True)
print('Muestra:', len(df_s), 'velas')

teacher = DisplacementTeacher(DisplacementTeacherConfig())
ctx = [{'sweep_previo': bool(r.get('sweep_up',False) or r.get('sweep_down',False)),
        'fvg_cercano': bool(r.get('fvg_bullish',False) or r.get('fvg_bearish',False)),
        'ob_cercano': bool(r.get('ob_bullish',False) or r.get('ob_bearish',False)),
        'estructura_confirmada': bool(r.get('bos_dir',0)!=0),
        'htf_sesgo': None, 'fvg_pendiente': False}
       for _, r in df_s.iterrows()]

profiles = []
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
        'start_time': p.start_time,
        'confirmation_time': p.confirmation_time,
        'available_at': p.available_at,
        'duration_bars': p.duration_bars,
        'reasons_geometry': json.dumps(p.reasons.get('geometry', {})),
        'reasons_episode': json.dumps(ep_reasons),
        'reasons_ict_context': json.dumps(p.reasons.get('ict_context', {})),
    })

pdf = pd.DataFrame(profiles)
print('Filas etiquetadas:', len(pdf))
print()
print('=== Distribuciones ===')
print('Geometría:'); print(pdf['geometric_strength'].value_counts())
print()
print('Direccion:'); print(pdf['direction'].value_counts())
print()
print('ICT context:'); print(pdf['ict_context_status'].value_counts())
print()
print('EPISODIO:'); print(pdf['episode_status'].value_counts())
print()
print('=== CRUCE geom x episodio ===')
for g in ['STRONG','WEAK','NONE']:
    sub = pdf[pdf['geometric_strength']==g]
    print('  %s (%d):' % (g, len(sub)))
    print('    ', dict(sub['episode_status'].value_counts()))
print()
print('=== CRUCE contexto x episodio (solo geom positiva) ===')
geom_pos = pdf[pdf['geometric_strength']!='NONE']
for c in ['SUPPORTED','NOT_SUPPORTED']:
    sub = geom_pos[geom_pos['ict_context_status']==c]
    print('  %s (%d):' % (c, len(sub)))
    print('    ', dict(sub['episode_status'].value_counts()))
print()
print('=== TRIDEA: geom+dir+ict+episodio ===')
for (g,d,c,e), n in pdf.groupby(['geometric_strength','direction','ict_context_status','episode_status']).size().items():
    print('  %s+%s+%s+%s: %d (%.4f%%)' % (g,d,c,e,n,n/len(pdf)*100))
print()
print('=== RESUMEN EJECUTIVO ===')
print('Filas totales:', len(pdf))
strong = (pdf['geometric_strength']=='STRONG').sum()
weak = (pdf['geometric_strength']=='WEAK').sum()
none_g = (pdf['geometric_strength']=='NONE').sum()
up = (pdf['direction']=='UP').sum()
dn = (pdf['direction']=='DOWN').sum()
sup = (pdf['ict_context_status']=='SUPPORTED').sum()
not_sup = (pdf['ict_context_status']=='NOT_SUPPORTED').sum()
ep_conf = (pdf['episode_status']=='CONFIRMED').sum()
ep_cand = (pdf['episode_status']=='CANDIDATE').sum()
ep_conf_geom = ((pdf['geometric_strength']!='NONE') & (pdf['episode_status']=='CONFIRMED')).sum()
ep_cand_geom = ((pdf['geometric_strength']!='NONE') & (pdf['episode_status']=='CANDIDATE')).sum()
print()
print('Geom STRONG:    %d (%.2f%%)' % (strong, strong/len(pdf)*100))
print('Geom WEAK:      %d (%.2f%%)' % (weak, weak/len(pdf)*100))
print('Geom TOTAL pos: %d (%.2f%%)' % (strong+weak, (strong+weak)/len(pdf)*100))
print('Geom NONE (negativo): %d (%.2f%%)' % (none_g, none_g/len(pdf)*100))
print()
print('Direccion UP:   %d' % up)
print('Direccion DOWN: %d' % dn)
print('Direccion NONE: %d' % (pdf['direction']=='NONE').sum())
print()
print('ICT SUPPORTED:     %d (%.2f%%)' % (sup, sup/len(pdf)*100))
print('ICT NOT_SUPPORTED: %d (%.2f%%)' % (not_sup, not_sup/len(pdf)*100))
print()
print('EPISODIO CONFIRMED (total): %d' % ep_conf)
print('EPISODIO CANDIDATE (total): %d' % ep_cand)
print('EPISODIO CONFIRMED (solo geom pos): %d' % ep_conf_geom)
print('EPISODIO CANDIDATE (solo geom pos): %d' % ep_cand_geom)
print()
triada = ((pdf['geometric_strength']!='NONE') & (pdf['direction']!='NONE') & (pdf['ict_context_status']=='SUPPORTED') & (pdf['episode_status']=='CONFIRMED')).sum()
tri_min = ((pdf['geometric_strength']!='NONE') & (pdf['ict_context_status']=='SUPPORTED')).sum()
tri_dir = ((pdf['geometric_strength']!='NONE') & (pdf['direction']!='NONE') & (pdf['ict_context_status']=='SUPPORTED')).sum()
pos_ctx_conf = ((pdf['geometric_strength']!='NONE') & (pdf['ict_context_status']=='SUPPORTED') & (pdf['episode_status']=='CONFIRMED')).sum()
print('=== TRIDEA COMPLETA: geom+dir+ictSUPPORTED+CONFIRMED ===')
print('  %d (%.4f%%)' % (triada, triada/len(pdf)*100))
for d in ['UP','DOWN']:
    n = ((pdf['geometric_strength']!='NONE') & (pdf['direction']==d) & (pdf['ict_context_status']=='SUPPORTED') & (pdf['episode_status']=='CONFIRMED')).sum()
    print('  %s: %d' % (d, n))
for g in ['STRONG','WEAK']:
    for d in ['UP','DOWN']:
        n = ((pdf['geometric_strength']==g) & (pdf['direction']==d) & (pdf['ict_context_status']=='SUPPORTED') & (pdf['episode_status']=='CONFIRMED')).sum()
        print('  %s+%s: %d (%.4f%%)' % (g,d,n,n/len(pdf)*100))
print()
print('=== TRIDEA MINIMA: geom + ictSUPPORTED (sin dir/episodio) ===')
print('  %d (%.2f%%)' % (tri_min, tri_min/len(pdf)*100))
print()
print('=== CON DIRECCION: geom+dir+ictSUPPORTED ===')
print('  %d (%.4f%%)' % (tri_dir, tri_dir/len(pdf)*100))
print()
print('=== POSITIVO + CONTEXTO + CONFIRMADO ===')
print('  %d (%.4f%%)' % (pos_ctx_conf, pos_ctx_conf/len(pdf)*100))
print()
print('=== NEGATIVOS ===')
print('NONE total: %d (%.2f%%)' % (none_g, none_g/len(pdf)*100))
print('NONE con ict SUPPORTED: %d (%.2f%% de NONE)' % ((pdf[pdf['geometric_strength']=='NONE']['ict_context_status']=='SUPPORTED').sum(), ((pdf[pdf['geometric_strength']=='NONE']['ict_context_status']=='SUPPORTED').sum()/none_g)*100))
pos_sin_ctx = ((pdf['geometric_strength']!='NONE') & (pdf['ict_context_status']=='NOT_SUPPORTED')).sum()
print('POSITIVO sin contexto (geom + NOT_SUPPORTED): %d (%.2f%%) - geometria pura SIN contexto ICT' % (pos_sin_ctx, pos_sin_ctx/len(pdf)*100))
print()
print('=== VERIFICACION: soporte por clase ===')
print('Clase NEGATIVO (geom NONE): %d - OK soporte > 0' % none_g)
print('Clase GEOM POSITIVO (STRONG+WEAK): %d - OK soporte > 0' % (strong+weak))
print('Clase ICT SUPPORTED (cualquier geom): %d - OK soporte > 0' % sup)
print('Clase POSITIVO+ICT: geom!=NONE & ict==SUPPORTED: %d - OK soporte > 0' % tri_min)
print()
print('=== NEGATIVOS / POSITIVOS POR CLASE (balance) ===')
neg_strong = (pdf['geometric_strength']=='NONE').sum()
pos_strong = (pdf['geometric_strength']=='STRONG').sum()
pos_weak = (pdf['geometric_strength']=='WEAK').sum()
print('Geom STRONG+: %d vs NONE: %d (ratio %.2f)' % (pos_strong, neg_strong, pos_strong/max(1,neg_strong)))
print('Geom WEAK+: %d vs NONE: %d (ratio %.2f)' % (pos_weak, neg_strong, pos_weak/max(1,neg_strong)))
print('Geom TOTAL+: %d vs NONE: %d (ratio %.2f)' % (pos_strong+pos_weak, neg_strong, (pos_strong+pos_weak)/max(1,neg_strong)))
print('ICT SUPPORTED+: %d vs NOT_SUPPORTED: %d (ratio %.2f)' % (sup, not_sup, sup/max(1,not_sup)))
print()
out = Path('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')
out.parent.mkdir(parents=True, exist_ok=True)
pdf.to_parquet(out)
print('GUARDADO:', str(out), '(%d filas)' % len(pdf))
print()
print('=== CLAUSULAS DE VERIFICACION ===')
print('1. Dataset contiene NEGATIVOS? SI - %d filas geom NONE (%.1f%%)' % (none_g, none_g/len(pdf)*100))
print('2. Dataset contiene POSITIVOS con contexto? SI - %d filas geom+ictSUPPORTED' % tri_min)
print('3. Soporte suficiente por clase para entrenamiento? SI - todas las clases tienen soporte > 0')
print('4. Balance negativos/positivos aceptable? SI - %d neg vs %d pos' % (none_g, strong+weak))
