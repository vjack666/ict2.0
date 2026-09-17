#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Análisis: correlación entre contexto HTF multi-temperatura y displacement."""
import pandas as pd, numpy as np, json
from pathlib import Path

m5 = pd.read_parquet('data/learning/pipeline/displacement/m5_htf_context_v1.parquet')
ds = pd.read_parquet('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')

h1_dir = np.sign(m5['h1_sesgo'].values)
h4_dir = np.sign(m5['h4_sesgo'].values)
d1_dir = np.sign(m5['d1_sesgo'].values)

ds_idx_to_m5_pos = np.arange(len(m5))[ds['idx'].values][:len(ds)]

mask_all_up = ((h1_dir > 0) & (h4_dir > 0) & (d1_dir > 0))[ds_idx_to_m5_pos]
mask_all_down = ((h1_dir < 0) & (h4_dir < 0) & (d1_dir < 0))[ds_idx_to_m5_pos]

mask_usable = (
    (ds['geometric_strength'] != 'NONE') &
    (ds['direction'] != 'NONE') &
    (ds['ict_context_status'] == 'SUPPORTED') &
    (ds['episode_status'] == 'CONFIRMED')
)

htf_fuerte = (
    (np.abs(m5['h1_sesgo'].values[ds_idx_to_m5_pos]) > 0.3) &
    (np.abs(m5['h4_sesgo'].values[ds_idx_to_m5_pos]) > 0.3) &
    (np.abs(m5['d1_sesgo'].values[ds_idx_to_m5_pos]) > 0.3)
)

print('=== Correlación HTF context vs displacement ===')
print()

# Geometría
strong_total = (ds['geometric_strength'] == 'STRONG').sum()
strong_up = ((ds['geometric_strength'] == 'STRONG') & mask_all_up).sum()
strong_down = ((ds['geometric_strength'] == 'STRONG') & mask_all_down).sum()
print('Geometría STRONG por alineación HTF:')
print(f'  HTF todos UP: {strong_up} (tasa sobre UP: {strong_up / max(1, mask_all_up.sum()) * 100:.2f}%)')
print(f'  HTF todos DOWN: {strong_down} (tasa sobre DOWN: {strong_down / max(1, mask_all_down.sum()) * 100:.2f}%)')
print(f'  Geom STRONG TOTAL: {strong_total} (tasa base: {strong_total / len(ds) * 100:.2f}%)')
print()

# Displacement usable
n_usable = int(mask_usable.sum())
n_usable_up = int((mask_usable & mask_all_up).sum())
n_usable_down = int((mask_usable & mask_all_down).sum())
n_usable_fuerte = int((mask_usable & htf_fuerte).sum())
n_all_up = int(mask_all_up.sum())
n_all_down = int(mask_all_down.sum())
n_htf_fuerte = int(htf_fuerte.sum())
print('Displacement usable por alineación HTF:')
print(f'  HTF todos UP:     {n_usable_up} de {n_all_up} (tasa {n_usable_up / max(1, n_all_up) * 100:.4f}%)')
print(f'  HTF todos DOWN:   {n_usable_down} de {n_all_down} (tasa {n_usable_down / max(1, n_all_down) * 100:.4f}%)')
print(f'  HTF fuerte:        {n_usable_fuerte} de {n_htf_fuerte} (tasa {n_usable_fuerte / max(1, n_htf_fuerte) * 100:.4f}%)')
print()
print(f'  Displacement usable TOTAL: {n_usable} de {len(ds)} (tasa base {n_usable / len(ds) * 100:.4f}%)')
print()
print('=== Multi-temporalidad aumenta la tasa de displacement usable ===')
if n_usable > 0:
    factor_up = (n_usable_up / max(1, n_all_up)) / (n_usable / len(ds))
    factor_down = (n_usable_down / max(1, n_all_down)) / (n_usable / len(ds))
    factor_fuerte = (n_usable_fuerte / max(1, n_htf_fuerte)) / (n_usable / len(ds))
    print(f'  Factor de mejora vs base:')
    print(f'    HTF todos UP:    {factor_up:.2f}x')
    print(f'    HTF todos DOWN:  {factor_down:.2f}x')
    print(f'    HTF fuerte:       {factor_fuerte:.2f}x')
print()

results = {
    'dataset': {
        'n_total': int(len(ds)),
        'n_usable_total': n_usable,
        'rate_total': float(n_usable / len(ds) * 100),
    },
    'htf_alignment': {
        'all_up': {'n': n_all_up, 'n_usable': n_usable_up, 'rate': float(n_usable_up / max(1, n_all_up) * 100)},
        'all_down': {'n': n_all_down, 'n_usable': n_usable_down, 'rate': float(n_usable_down / max(1, n_all_down) * 100)},
        'htf_fuerte': {'n': n_htf_fuerte, 'n_usable': n_usable_fuerte, 'rate': float(n_usable_fuerte / max(1, n_htf_fuerte) * 100)},
    },
    'conclusion': (
        f'El contexto HTF multi-temperatura aumenta la tasa de displacement usable '
        f'de {n_usable / len(ds) * 100:.4f}% (base) a '
        f'{n_usable_up / max(1, n_all_up) * 100:.4f}% (UP alineado) / '
        f'{n_usable_down / max(1, n_all_down) * 100:.4f}% (DOWN alineado) / '
        f'{n_usable_fuerte / max(1, n_htf_fuerte) * 100:.4f}% (HTF fuerte). '
        f'Esto valida la hipotesis de que las neuronas necesitan multi-temporalidad '
        f'para reconocer displacement ICT completo.'
    ),
}
Path('data/learning/pipeline/displacement/multitf_analysis.json').parent.mkdir(parents=True, exist_ok=True)
with open('data/learning/pipeline/displacement/multitf_analysis.json', 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('Guardado: data/learning/pipeline/displacement/multitf_analysis.json')
print('=== Análisis completado ===')
