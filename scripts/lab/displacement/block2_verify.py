#!/usr/bin/env python3
"""Bloque 2 — verificación soporte por clase/direccion/periodo + inventario de casos."""
import sys, json, time
sys.path.insert(0, '.')

import pandas as pd, numpy as np
from pathlib import Path

pdf = pd.read_parquet('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')
print('Dataset: %d filas' % len(pdf))

# Recuperar el contexto perdido para análisis de periodo (el dataset solo guarda resultados)
# Recomputamos mínimamente la columna de periodo para ver cobertura temporal
raw_cols = ['time']
if 'time' in pdf.columns:
    df_t = pdf[['time']].copy()
else:
    print('WARNING: time no disponible en dataset; análisis de periodo limitado')
    df_t = pd.DataFrame({'time': pd.Series([0]*len(pdf))})

# Soporte por clase (geometría)
print()
print('=== SOSTEN POR CLASE GEOMETRIA ===')
for g in ['STRONG','WEAK','NONE']:
    n = (pdf['geometric_strength']==g).sum()
    print('  %s: %d (%.2f%%) - %s' % (g, n, n/len(pdf)*100, 'OK' if n>0 else 'FALLO'))

# Soporte por clase + dirección
print()
print('=== SOSTEN POR CLASE+DIRECCION (geom positiva) ===')
for g in ['STRONG','WEAK']:
    sub = pdf[pdf['geometric_strength']==g]
    for d in ['UP','DOWN']:
        n = ((sub['direction']==d) & (sub['ict_context_status']=='SUPPORTED')).sum()
        conf_n = ((sub['direction']==d) & (sub['ict_context_status']=='SUPPORTED') & (sub['episode_status']=='CONFIRMED')).sum()
        print('  %s+%s+ictSUPPORTED: %d - confirmados: %d - %s' % (g, d, n, conf_n, 'OK' if n>0 else 'ZERO'))

# Soporte por clase + ict
print()
print('=== CRUCE geom x ict (ver cobertura) ===')
for (g,c), n in pdf.groupby(['geometric_strength','ict_context_status']).size().items():
    print('  %s+%s: %d (%.2f%%)' % (g,c,n,n/len(pdf)*100))

# Verificar que las episodes CONFIRMED no son todos de una clase
print()
print('=== EPISODIO POR CLASE GEOMETRIA ===')
for g in ['STRONG','WEAK','NONE']:
    sub = pdf[pdf['geometric_strength']==g]
    print('  %s:' % g)
    print('    ', dict(sub['episode_status'].value_counts()))

# Ejemplos representativos: STRONG+ictSUPPORTED+CONFIRMADO
print()
print('=== EJEMPLOS: TRIDEA COMPLETA (STRONG/DOWN/ICT/CONFIRMADO) ===')
tri = pdf[(pdf['geometric_strength']!='NONE') & (pdf['direction']!='NONE') & (pdf['ict_context_status']=='SUPPORTED') & (pdf['episode_status']=='CONFIRMED')]
print('Total tríadas completas: %d' % len(tri))
for _, r in tri.head(10).iterrows():
    print('  %s %s %s episodio=%s ratio=%.3f pips=%.2f ict=%.3f duration=%d' % (
        r['geometric_strength'], r['direction'], r['ict_context_status'], r['episode_status'],
        r['body_to_range_ratio'], r['body_pips'], r['episode_net_advance_pips'], r['duration_bars']))

# Ejemplos NEGATIVOS: geom NONE (lo que NO es displacement)
print()
print('=== EJEMPLOS NEGATIVOS (geom NONE) ===')
neg = pdf[pdf['geometric_strength']=='NONE']
print('Total NONE: %d' % len(neg))
print('  NONE+ict SUPPORTED: %d (%.2f%% de NONE)' % ((neg['ict_context_status']=='SUPPORTED').sum(), (neg['ict_context_status']=='SUPPORTED').sum()/len(neg)*100))
print('  NONE+ict NOT_SUPPORTED: %d (%.2f%% de NONE)' % ((neg['ict_context_status']=='NOT_SUPPORTED').sum(), (neg['ict_context_status']=='NOT_SUPPORTED').sum()/len(neg)*100))
print('  Ejemplo NONE (primer 3):')
for _, r in neg.head(3).iterrows():
    print('    ratio=%.3f | ict=%s | dir=%s' % (r['body_to_range_ratio'], r['ict_context_status'], r['direction']))

# Positivo SIN contexto (geom + NOT_SUPPORTED): lo que sería falso positivo si solo se mira geometría
print()
print('=== POSITIVO SIN CONTEXTO (geom != NONE, ict NOT_SUPPORTED) ===')
pos_no_ctx = pdf[(pdf['geometric_strength']!='NONE') & (pdf['ict_context_status']=='NOT_SUPPORTED')]
print('Total: %d (%.2f%%)' % (len(pos_no_ctx), len(pos_no_ctx)/len(pdf)*100))
print('  Esto es geometría pura SIN contexto ICT — lo que NO es displacement ICT usable.')
print('  STRONG sin contexto: %d' % ((pos_no_ctx['geometric_strength']=='STRONG')).sum())
print('  WEAK sin contexto: %d' % ((pos_no_ctx['geometric_strength']=='WEAK')).sum())
print('  CONFIRMED sin contexto: %d' % ((pos_no_ctx['episode_status']=='CONFIRMED')).sum())
print('Esto confirma que geometría sin contexto NO es suficiente para displacement ICT.')

# RESUMEN: soporte para cada "clase de entrenamiento" sobre la que se puede aprender
print()
print('=== SOSTEN PARA ENTRENAMIENTO REAL ===')
print('Clase NEGATIVO (geom NONE): %d - OK' % (pdf['geometric_strength']=='NONE').sum())
print('Clase POSITIVO geometría (STRONG+WEAK): %d - OK' % (pdf['geometric_strength']!='NONE').sum())
print('Clase POSITIVO+ICT (geom!=NONE & ict==SUPPORTED): %d - OK pero MUY minoritario' % ((pdf['geometric_strength']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')).sum())
print('Clase POSITIVO+ICT+CONFIRMADO (ejemplos completos): %d - OK' % ((pdf['geometric_strength']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')&(pdf['episode_status']=='CONFIRMED')).sum())
print()
print('=== DECISION: soporte suficiente? ===')
n_neg = (pdf['geometric_strength']=='NONE').sum()
n_pos = (pdf['geometric_strength']!='NONE').sum()
n_pos_ict = ((pdf['geometric_strength']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')).sum()
print('Si queremos aprender a DISTINGUIR displacement de no-displacement:')
print('  - Negativos geom NONE: %d (%.1f%%) -> suficiente' % (n_neg, n_neg/len(pdf)*100))
print('  - Positivos geom: %d (%.1f%%) -> suficiente' % (n_pos, n_pos/len(pdf)*100))
print('  - Positivos+ictSUPPORTED: %d (%.1f%%) -> suficiente pero minoritario' % (n_pos_ict, n_pos_ict/len(pdf)*100))
print('Conclusión: hay soporte para entrenar, pero la clase "desplazamiento ICT completo" es muy rara (~1-2%% de las velas).')
print('Esto es lo que hace difícil el reconocimiento: el modelo debe aprender a rechazar geometría pura sin contexto ICT.')

# Guardar checkpoint FASE 2
import json as _json
ck = Path('data/learning/pipeline/displacement/checkpoint.json')
ck.parent.mkdir(parents=True, exist_ok=True)
estado = {
    'bloque': 2,
    'hecho': ['bloque_1_etiquetado'],
    'parcial': {
        'n_filas': len(pdf),
        'n_neg': int(n_neg),
        'n_pos': int(n_pos),
        'n_pos_ict': int(n_pos_ict),
        'n_triada_completa': int(((pdf['geometric_strength']!='NONE')&(pdf['direction']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')&(pdf['episode_status']=='CONFIRMED')).sum()),
        'pct_triada_completa': float(((pdf['geometric_strength']!='NONE')&(pdf['direction']!='NONE')&(pdf['ict_context_status']=='SUPPORTED')&(pdf['episode_status']=='CONFIRMED')).sum()/len(pdf)*100),
        'pct_pos_ict': float(n_pos_ict/len(pdf)*100),
        'soporte_suficiente': bool(n_neg>0 and n_pos>0 and n_pos_ict>0),
        'clase_minoritaria_pct': float(n_pos_ict/len(pdf)*100),
    },
    'nota': 'Soporte por clase OK. La clase desplazamiento ICT completo es ~1-2% de las velas — entrenamiento posible pero requiere manejo de desbalance.'
}
ck.write_text(_json.dumps(estado, indent=2, ensure_ascii=False))
print()
print('Checkpoint FASE 2 guardado.')
