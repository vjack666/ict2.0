#!/usr/bin/env python3
"""Bloque Multi-TF: alinear contexto HTF (H1/H4/D1) al contexto M5 sin leakage."""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path

M5_PATH = Path('data/raw/EURUSD/EURUSD_M5.parquet')
H1_PATH = Path('datasets/eurusd_dukascopy_20y/EURUSD_H1.csv')
H4_PATH = Path('datasets/eurusd_dukascopy_20y/EURUSD_H4.csv')
D1_PATH = Path('datasets/eurusd_dukascopy_20y/EURUSD_D1.csv')

print('Cargando M5...')
m5 = pd.read_parquet(M5_PATH)
m5['time'] = pd.to_datetime(m5['time'], utc=True)
print('M5 filas:', len(m5), 'rango:', m5.time.min(), '→', m5.time.max())

print('\nCargando H1...')
h1 = pd.read_csv(H1_PATH)
h1['time'] = pd.to_datetime(h1['time'], utc=True)
h1 = h1.sort_values('time').reset_index(drop=True)
print('H1 filas:', len(h1), 'rango:', h1.time.min(), '→', h1.time.max())

print('\nCargando H4...')
h4 = pd.read_csv(H4_PATH)
h4['time'] = pd.to_datetime(h4['time'], utc=True)
h4 = h4.sort_values('time').reset_index(drop=True)
print('H4 filas:', len(h4), 'rango:', h4.time.min(), '→', h4.time.max())

print('\nCargando D1...')
d1 = pd.read_csv(D1_PATH)
d1['time'] = pd.to_datetime(d1['time'], utc=True)
d1 = d1.sort_values('time').reset_index(drop=True)
print('D1 filas:', len(d1), 'rango:', d1.time.min(), '→', d1.time.max())

print('\nVerificando alineación de tiempos...')
print('H1 cubre M5:', h1.time.min() <= m5.time.min() and h1.time.max() >= m5.time.max())
print('H4 cubre M5:', h4.time.min() <= m5.time.min() and h4.time.max() >= m5.time.max())
print('D1 cubre M5:', d1.time.min() <= m5.time.min() and d1.time.max() >= m5.time.max())

# Calcular features HTF as-of cada vela M5 (solo información disponible en ese momento)
print('\nCalculando contexto H1 (as-of decision_time)...')

# Sesgo H1: dirección del cierre relativo al rango de la hora anterior
h1['range'] = h1['high'] - h1['low']
h1['body'] = abs(h1['close'] - h1['open'])
h1['up_strength'] = (h1['close'] - h1['open']) / h1['range'].replace(0, 1e-10)
h1['down_strength'] = (h1['open'] - h1['close']) / h1['range'].replace(0, 1e-10)

# Para cada vela M5, encontrar la vela H1 que ESTA CERRADA en ese momento
# La vela H1 que cierra en o antes del time de la vela M5 es la más reciente cerrada
def get_h1_context(time_m5, h1_df):
    # vela H1 cuya hora de cierre <= time_m5
    mask = h1_df['time'] <= time_m5
    if mask.sum() == 0:
        return None
    h1_closed = h1_df[mask].iloc[-1]
    return h1_closed

def get_h4_context(time_m5, h4_df):
    mask = h4_df['time'] <= time_m5
    if mask.sum() == 0:
        return None
    return h4_df[mask].iloc[-1]

def get_d1_context(time_m5, d1_df):
    mask = d1_df['time'] <= time_m5
    if mask.sum() == 0:
        return None
    return d1_df[mask].iloc[-1]

print('Ejemplo de alineación para primera vela M5...')
first_m5_time = m5.time.iloc[0]
h1_ctx = get_h1_context(first_m5_time, h1)
h4_ctx = get_h4_context(first_m5_time, h4)
d1_ctx = get_d1_context(first_m5_time, d1)
print(f'M5 time: {first_m5_time}')
print(f'H1 context (más reciente cerrada): {h1_ctx.time if h1_ctx is not None else None}')
print(f'H4 context: {h4_ctx.time if h4_ctx is not None else None}')
print(f'D1 context: {d1_ctx.time if d1_ctx is not None else None}')

# Calcular features H1 como serie temporal para join rápido
print('\n=== Construyendo features HTF para todas las velas M5 ===')

# Features H1 para join (renombrar antes del merge)
h1_features = h1[['time', 'close', 'range']].copy()
h1_features['h1_close'] = h1_features['close']
h1_features['h1_range'] = h1_features['range']
h1_features['h1_sesgo'] = (h1['close'] - h1['open']) / h1['range'].replace(0, 1e-10) - (h1['open'] - h1['close']) / h1['range'].replace(0, 1e-10)
h1_features['h1_fuerza'] = np.abs(h1_features['h1_sesgo'])
h1_merge_cols = ['time', 'h1_close', 'h1_range', 'h1_sesgo', 'h1_fuerza']

# Features H4 para join
h4_features = h4[['time', 'close', 'range']].copy()
h4_features['h4_close'] = h4_features['close']
h4_features['h4_range'] = h4_features['range']
h4_features['h4_sesgo'] = (h4['close'] - h4['open']) / h4['range'].replace(0, 1e-10) - (h4['open'] - h4['close']) / h4['range'].replace(0, 1e-10)
h4_features['h4_fuerza'] = np.abs(h4_features['h4_sesgo'])
h4_merge_cols = ['time', 'h4_close', 'h4_range', 'h4_sesgo', 'h4_fuerza']

# Features D1 para join
d1_features = d1[['time', 'close', 'range']].copy()
d1_features['d1_close'] = d1_features['close']
d1_features['d1_range'] = d1_features['range']
d1_features['d1_sesgo'] = (d1['close'] - d1['open']) / d1['range'].replace(0, 1e-10) - (d1['open'] - d1['close']) / d1['range'].replace(0, 1e-10)
d1_features['d1_fuerza'] = np.abs(d1_features['d1_sesgo'])
d1_merge_cols = ['time', 'd1_close', 'd1_range', 'd1_sesgo', 'd1_fuerza']

print('Realizando merge_asof H1 → M5...')
m5_h1 = pd.merge_asof(
    m5.sort_values('time'),
    h1_features[h1_merge_cols].sort_values('time'),
    on='time',
    direction='backward',
    allow_exact_matches=True
)
print('H1 merge completado. Filas:', len(m5_h1))
print('Columnas H1 agregadas:', [c for c in m5_h1.columns if c.startswith('h1_')])

print('\nRealizando merge_asof H4 → M5...')
m5_h1h4 = pd.merge_asof(
    m5_h1.sort_values('time'),
    h4_features[h4_merge_cols].sort_values('time'),
    on='time',
    direction='backward',
    allow_exact_matches=True
)
print('H4 merge completado. Filas:', len(m5_h1h4))
print('Columnas H4 agregadas:', [c for c in m5_h1h4.columns if c.startswith('h4_')])

print('\nRealizando merge_asof D1 → M5...')
m5_h1h4d1 = pd.merge_asof(
    m5_h1h4.sort_values('time'),
    d1_features[d1_merge_cols].sort_values('time'),
    on='time',
    direction='backward',
    allow_exact_matches=True
)
print('D1 merge completado. Filas:', len(m5_h1h4d1))
print('Columnas D1 agregadas:', [c for c in m5_h1h4d1.columns if c.startswith('d1_')])

# Verificar que no hay NaN en las features clave (deberían venir del primer valor disponible)
print('\nVerificando valores nulos en features HTF...')
for col in ['h1_sesgo', 'h4_sesgo', 'd1_sesgo']:
    n_null = m5_h1h4d1[col].isna().sum()
    print(f'  {col}: {n_null} nulos de {len(m5_h1h4d1)}')

# Guardar dataset multi-TF
print('\nGuardando dataset multi-TF...')
output_path = Path('data/learning/pipeline/displacement/m5_htf_context_v1.parquet')
output_path.parent.mkdir(parents=True, exist_ok=True)
m5_h1h4d1.to_parquet(output_path)
print(f'Dataset guardado: {output_path}')
print(f'Filas: {len(m5_h1h4d1)}')
print(f'Columnas: {list(m5_h1h4d1.columns)}')

# Resumen de features HTF calculadas
print('\n=== Resumen de features HTF agregadas ===')
print('H1 features:')
print('  - h1_close: precio de cierre H1 más reciente cerrado')
print('  - h1_sesgo: (up_strength - down_strength), positivo=alcista, negativo=bajista')
print('  - h1_fuerza: |sesgo|, magnitud del impulso H1')
print('  - h1_rango: rango alto-bajo de la vela H1')
print('\nH4 features:')
print('  - h4_close: precio de cierre H4 más reciente cerrado')
print('  - h4_sesgo: sesgo dirección H4')
print('  - h4_fuerza: magnitud del impulso H4')
print('  - h4_rango: rango H4')
print('\nD1 features:')
print('  - d1_close: precio de cierre D1 más reciente cerrado')
print('  - d1_sesgo: sesgo dirección D1')
print('  - d1_fuerza: magnitud del impulso D1')
print('  - d1_rango: rango D1')
print('\n=== TODAS estas features son calculables as-of decision_time ===')
print('(solo utilizando información de velas HTF que YA ESTÁN CERRADAS)')
print('→ NO HAY LEAKAGE de futuro')
print('\nDataset listo para entrenamiento multi-temperatura.')
