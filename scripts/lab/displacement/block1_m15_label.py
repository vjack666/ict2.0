#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bloque 1 M15 — etiquetado del profesor 3-capas en M15 (sample)."""
import sys, json
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

from runtime.ai_learning.displacement_teacher import DisplacementTeacher, DisplacementTeacherConfig

M15_PATH = 'data/raw/EURUSD/EURUSD_M15.parquet'
OUT_PARQUET = 'data/learning/pipeline/displacement/m15_displacement_dataset_v1.parquet'
SEED = 17
MOK = 25000  # mismo tamano que M5 para consistencia

# ── 1. Cargar M15 ──────────────────────────────────────────────────────
print('='*60)
print('BLOQUE 1 M15 — Etiquetado de desplazamiento ICT en M15')
print('='*60)

df = pd.read_parquet(M15_PATH)
print(f'M15 crudo: {len(df)} filas')
print(f'Columnas: {df.columns.tolist()}')
print(f'Periodo: {df["time"].min()} -> {df["time"].max()}')

# Estandarizar
for c in ['open','high','low','close']:
    df[c] = pd.to_numeric(df[c], errors='coerce')
df = df.dropna(subset=['open','high','low','close'])
df = df.sort_values('time').reset_index(drop=True)
df['orig_idx'] = np.arange(len(df))
print(f'Despues de limpieza: {len(df)} filas')

# ── 2. Sample estratificado (misma logica que M5) ─────────────────────
N = min(MOK, len(df))
idx = np.linspace(20, len(df)-1, N, dtype=int)  # saltar primeras 20 por HISTORIA_MIN=5
np.random.seed(SEED)
np.random.shuffle(idx)
df_s = df.iloc[idx].copy().reset_index(drop=True)
df_s['idx'] = idx  # guardar posicion original para referencia
print(f'Sample M15: {len(df_s)} velas (desde {len(df)} originales)')
print(f'Primera vela: {df_s["time"].iloc[0]}')
print(f'Ultima vela: {df_s["time"].iloc[-1]}')

# ── 3. Calcular features geometricas ───────────────────────────────────
df_s['body_range'] = (df_s['close'] - df_s['open']).abs()
df_s['bar_range'] = df_s['high'] - df_s['low']
df_s['body_to_range_ratio'] = df_s['body_range'] / df_s['bar_range'].replace(0, np.nan)
df_s['wick_ratio'] = np.minimum(
    (df_s['high'] - df_s[['open','close']].max(axis=1)),
    (df_s[['open','close']].min(axis=1) - df_s['low'])
) / df_s['bar_range'].replace(0, np.nan)

# ── 4. Evaluar con profesor ────────────────────────────────────────────
print('\nEvaluando con profesor 3-capas...')
teacher = DisplacementTeacher(DisplacementTeacherConfig())

def eval_m15_row(i):
    """Evaluar una fila de M15 con contexto None (solo geometria)."""
    ctx = None  # M15 no tiene HTF natural en este sample
    prof = teacher.evaluate(df_s, i, context=ctx)
    return {
        'geometric_strength': prof.geometric_strength.name,
        'direction': prof.direction.name,
        'ict_context_status': prof.ict_context_status.name,
        'episode_status': prof.reasons.get('episode', {}).get('episode_status', 'N/A') if isinstance(prof.reasons.get('episode'), dict) else 'N/A',
        'body_to_range_ratio': prof.body_to_range_ratio,
        'body_pips': prof.body_pips,
        'range_pips': prof.range_pips,
        'wick_ratio': prof.wick_ratio,
        'start_time': prof.start_time,
        'confirmation_time': prof.confirmation_time,
        'available_at': prof.available_at,
        'duration_bars': prof.duration_bars,
    }

results = [eval_m15_row(i) for i in range(len(df_s))]
res = pd.DataFrame(results)
ds_out = pd.concat([df_s, res], axis=1)
ds_out.to_parquet(OUT_PARQUET, index=False)

print(f'\nDataset guardado: {OUT_PARQUET} ({len(ds_out)} filas)')

# ── 5. Resumen ─────────────────────────────────────────────────────────
print('\n' + '='*60)
print('RESUMEN M15')
print('='*60)

n = len(ds_out)
print(f'Total etiquetado: {n} velas (sample de {len(df)} originales)')

# Geometría
geo = ds_out['geometric_strength'].value_counts()
print('\nGeometría:')
for k in ['STRONG','WEAK','NONE','UNKNOWN']:
    v = int(geo.get(k, 0))
    print(f'  {k:>10}: {v:>6} ({v/n*100:5.2f}%)')

# Dirección
dir_counts = ds_out['direction'].value_counts()
print('\nDireccion:')
for k in ['UP','DOWN','NONE','UNKNOWN']:
    v = int(dir_counts.get(k, 0))
    print(f'  {k:>10}: {v:>6} ({v/n*100:5.2f}%)')

# Contexto ICT
ict_counts = ds_out['ict_context_status'].value_counts()
print('\nContexto ICT:')
for k in ['SUPPORTED','NOT_SUPPORTED','PENDING','UNKNOWN']:
    v = int(ict_counts.get(k, 0))
    print(f'  {k:>10}: {v:>6} ({v/n*100:5.2f}%)')

# Episodio
ep_counts = ds_out['episode_status'].value_counts()
print('\nEpisodio:')
for k in ['CONFIRMED','CANDIDATE','N/A']:
    v = int(ep_counts.get(k, 0))
    print(f'  {k:>10}: {v:>6} ({v/n*100:5.2f}%)')

# Desplazamiento usable
usable = (
    (ds_out['geometric_strength'] != 'NONE') &
    (ds_out['direction'] != 'NONE') &
    (ds_out['ict_context_status'] == 'SUPPORTED') &
    (ds_out['episode_status'] == 'CONFIRMED')
)
print(f'\nDesplazamiento usable: {int(usable.sum())} ({int(usable.sum())/n*100:.4f}%)')

# Geometria fuerte sin contexto
strong_no_ctx = (
    (ds_out['geometric_strength'] == 'STRONG') &
    (ds_out['ict_context_status'] != 'SUPPORTED')
)
print(f'Geometría STRONG sin contexto ICT: {int(strong_no_ctx.sum())} ({int(strong_no_ctx.sum())/n*100:.2f}%)')

summary = {
    'task': 'block1_m15_label',
    'timestamp': datetime.now().isoformat(),
    'source': M15_PATH,
    'total_rows': int(len(df)),
    'sample_rows': int(n),
    'sample_strategy': 'stratified_random_seed17',
    'period': {
        'start': str(df_s['time'].iloc[0]),
        'end': str(df_s['time'].iloc[-1]),
    },
    'geometry': {k: int(geo.get(k, 0)) for k in ['STRONG','WEAK','NONE','UNKNOWN']},
    'direction': {k: int(dir_counts.get(k, 0)) for k in ['UP','DOWN','NONE','UNKNOWN']},
    'ict_context': {k: int(ict_counts.get(k, 0)) for k in ['SUPPORTED','NOT_SUPPORTED','PENDING','UNKNOWN']},
    'episode': {k: int(ep_counts.get(k, 0)) for k in ['CONFIRMED','CANDIDATE','N/A']},
    'usable': int(usable.sum()),
    'usable_rate': float(usable.sum()/n*100),
    'strong_without_context': int(strong_no_ctx.sum()),
}

out_json = Path(OUT_PARQUET).parent / 'block1_m15_summary.json'
out_json.parent.mkdir(parents=True, exist_ok=True)
out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
print(f'\nResumen guardado: {out_json}')
print('\n=== BLOQUE 1 M15 COMPLETADO ===')
