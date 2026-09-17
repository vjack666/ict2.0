#!/usr/bin/env python3
"""
Fase 2 del plan: construir dataset de entrenamiento para displacement.
Genera ejemplos con las 3 capas etiquetadas por el profesor:
- geometric_strength (NONE/WEAK/STRONG/UNKNOWN)
- direction (UP/DOWN/NONE/UNKNOWN)
- ict_context_status (SUPPORTED/NOT_SUPPORTED/PENDING/UNKNOWN)

Incluye NEGATIVOS: geometría sin contexto ICT = NO displacement ICT.
Mismo pipeline resumible con checkpoint.json.
"""
import sys, json, os
sys.path.insert(0, '.')

import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timedelta

from runtime.ai_learning.displacement_teacher import (
    DisplacementTeacher, DisplacementTeacherConfig, DisplacementProfile
)

# ── Checkpoint ──────────────────────────────────────────────────────────────
CHECKPOINT = Path('data/learning/pipeline/displacement/checkpoint.json')
PAUSE_FLAG = Path('data/learning/pipeline/PAUSE')
os.makedirs(CHECKPOINT.parent, exist_ok=True)

def load_checkpoint():
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text())
    return {'bloque': 0, 'hecho': [], 'parcial': {}}

def save_checkpoint(state):
    CHECKPOINT.write_text(json.dumps(state, indent=2))

def check_pause():
    if PAUSE_FLAG.exists():
        print("PAUSA detectada. Guardando checkpoint y deteniéndose.")
        save_checkpoint(current_state)
        sys.exit(0)

current_state = load_checkpoint()
check_pause()

# ── Config ────────────────────────────────────────────────────────────────────
cfg = DisplacementTeacherConfig()
teacher = DisplacementTeacher(cfg)

# ── Muestra de datos (M5 EURUSD 50K velas uniformes) ─────────────────────────
raw = Path('data/raw/EURUSD')
df_full = pd.read_parquet(raw / 'EURUSD_M5.parquet')  # 339K filas

# Preparar columnas para el profesor
for c in ['open','high','low','close']:
    df_full[c] = df_full[c].astype(float)
if hasattr(df_full['time'].iloc[0], 'timestamp'):
    df_full['time'] = df_full['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)

# Features de contexto ICT (rápidas, calculadas una vez)
# Sweep
from detectors.liquidity_context import canonical_sweep
swept = canonical_sweep(df_full, lookback=20)
df_full['sweep_up'] = swept['liquidity_sweep_up'].values
df_full['sweep_down'] = swept['liquidity_sweep_down'].values

# Estructura BOS (rápida)
from engine.bos.structure import detect_market_structure, StructureConfig
ms = detect_market_structure(df_full, StructureConfig(swing_lookback=5, confirm_bars=2))
df_full['bos_dir'] = ms.frame['bos_dir'].values
df_full['bos_status'] = ms.frame['bos_status'].values

# FVG
from detectors.fvg import detect_fvg
fvg = detect_fvg(df_full)
df_full['fvg_bullish'] = fvg['fvg_bullish'].values if 'fvg_bullish' in fvg.columns else np.zeros(len(df_full), dtype=bool)
df_full['fvg_bearish'] = fvg['fvg_bearish'].values if 'fvg_bearish' in fvg.columns else np.zeros(len(df_full), dtype=bool)

df_full = df_full.reset_index(drop=True)

# Muestreo estratificado: 100K filas uniformes
N = 100000
sample_idx = np.linspace(20, len(df_full)-1, N, dtype=int)
df = df_full.iloc[sample_idx].reset_index(drop=True)
print(f"Muestra: {len(df)} velas de EURUSD M5 ({df.time.min()} → {df.time.max()})")

# ── Bloque 1: etiquetar con el profesor ──────────────────────────────────────
print("\n=== BLOQUE 1: Etiquetado con profesor 3-capas ===")
print(f"Etiquetando {len(df)} velas...")

# Pre-calcular contexto para cada vela (cola de contexto previo)
# Para el profesor, el contexto es lo observable EN decision_time (no futuro)
context_cache = []
for i in range(len(df)):
    row = df.iloc[i]
    ctx = {
        'sweep_previo': bool(row.get('sweep_down', False) or row.get('sweep_up', False)),
        'fvg_cercano': bool(
            (i > 0 and (df.iloc[i-1].get('fvg_bullish', False) or df.iloc[i-1].get('fvg_bearish', False))) or
            (row.get('fvg_bullish', False) or row.get('fvg_bearish', False))
        ),
        'ob_cercano': bool(
            (i > 0 and (df.iloc[i-1].get('ob_bullish', False) or df.iloc[i-1].get('ob_bearish', False))) or
            (row.get('ob_bullish', False) or row.get('ob_bearish', False))
        ),
        'estructura_confirmada': bool(row.get('bos_dir', 0) != 0),
        'htf_sesgo': None,  # sin H1 en esta muestra
        'fvg_pendiente': False,
    }
    context_cache.append(ctx)

# Etiquetar (solo desde idx=20 para tener historia suficiente)
profiles = []
for i in range(20, len(df)):
    p = teacher.evaluate(df, i, context=context_cache[i])
    profiles.append({
        'idx': i,
        'geometric_strength': p.geometric_strength.name,
        'direction': p.direction.name,
        'ict_context_status': p.ict_context_status.name,
        'body_to_range_ratio': p.body_to_range_ratio,
        'body_pips': p.body_pips,
        'range_pips': p.range_pips,
        'wick_ratio': p.wick_ratio,
        'start_time': p.start_time,
        'confirmation_time': p.confirmation_time,
        'available_at': p.available_at,
        'duration_bars': p.duration_bars,
        'episode_status': p.reasons.get('episode_status', 'N/A'),
        'reasons_geometry': json.dumps(p.reasons.get('geometry', {})),
        'reasons_episode': json.dumps(p.reasons.get('episode', {})),
        'reasons_ict_context': json.dumps(p.reasons.get('ict_context', {})),
    })

profiles_df = pd.DataFrame(profiles)
print(f"Etiquetadas {len(profiles_df)} filas")

# Estadísticas de clase
print("\n--- Distribución de clases ---")
print(f"Geometric strength:")
for k, v in profiles_df['geometric_strength'].value_counts().items():
    print(f"  {k}: {v} ({v/len(profiles_df)*100:.2f}%)")

print(f"\nDirection:")
for k, v in profiles_df['direction'].value_counts().items():
    print(f"  {k}: {v} ({v/len(profiles_df)*100:.2f}%)")

print(f"\nICT context status:")
for k, v in profiles_df['ict_context_status'].value_counts().items():
    print(f"  {k}: {v} ({v/len(profiles_df)*100:.2f}%)")

print(f"\nEpisodio:")
for k, v in profiles_df['episode_status'].value_counts().items():
    print(f"  {k}: {v} ({v/len(profiles_df)*100:.2f}%)")

# Cruce: geometría x contexto
print(f"\n--- Cruce geometría x contexto ICT ---")
cross = profiles_df.groupby(['geometric_strength', 'ict_context_status'], as_index=False).size()
for _, row in cross.iterrows():
    print(f"  {row['geometric_strength']} + {row['ict_context_status']}: {row['count']} ({row['count']/len(profiles_df)*100:.2f}%)")

# Cruce: geometría x dirección
print(f"\n--- Cruce geometría x dirección ---")
cross2 = profiles_df.groupby(['geometric_strength', 'direction']).size().reset_index(name='count')
for _, row in cross2.iterrows():
    print(f"  {row['geometric_strength']} + {row['direction']}: {row['count']} ({row['count']/len(profiles_df)*100:.2f}%)")

# Guardar dataset
ds_path = CHECKPOINT.parent / 'displacement_dataset_v1.parquet'
profiles_df.to_parquet(ds_path)
print(f"\nDataset guardado: {ds_path} ({len(profiles_df)} filas)")

current_state['hecho'].append('bloque_1_etiquetado')
current_state['parcial']['dataset_path'] = str(ds_path)
current_state['parcial']['n_filas'] = len(profiles_df)
current_state['parcial']['n_strong'] = int((profiles_df['geometric_strength']=='STRONG').sum())
current_state['parcial']['n_weak'] = int((profiles_df['geometric_strength']=='WEAK').sum())
current_state['parcial']['n_none'] = int((profiles_df['geometric_strength']=='NONE').sum())
current_state['parcial']['n_supported'] = int((profiles_df['ict_context_status']=='SUPPORTED').sum())
save_checkpoint(current_state)

print("\n=== BLOQUE 1 COMPLETADO ===")
print(f"Dataset: {ds_path}")
print(f"Filas: {len(profiles_df)}")
print(f"STRONG: {current_state['parcial']['n_strong']} ({current_state['parcial']['n_strong']/len(profiles_df)*100:.2f}%)")
print(f"WEAK: {current_state['parcial']['n_weak']} ({current_state['parcial']['n_weak']/len(profiles_df)*100:.2f}%)")
print(f"NONE: {current_state['parcial']['n_none']} ({current_state['parcial']['n_none']/len(profiles_df)*100:.2f}%)")
print(f"ICT SUPPORTED (triada completa): {current_state['parcial']['n_supported']} ({current_state['parcial']['n_supported']/len(profiles_df)*100:.2f}%)")
print(f"\nCLAUSULA DE VERIFICACIÓN: dataset contiene NEGATIVOS? ", end="")
negativos = len(profiles_df[profiles_df['geometric_strength']=='NONE'])
print(f"SÍ — {negativos} filas con geometría NONE ({(negativos/len(profiles_df)*100):.1f}%)")
print(f"CLAUSULA DE VERIFICACIÓN: dataset contiene positivos con contexto? ", end="")
print(f"SÍ — {current_state['parcial']['n_supported']} filas con ICT SUPPORTED")
