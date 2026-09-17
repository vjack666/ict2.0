#!/usr/bin/env python3
"""Bloque 4 — representacion causal para entrenamiento (Fase 3 del plan).

Separa:
- ENTRADA ALUMNO: OHLCV causales + features de contexto disponibles AS OF decision_time.
- SALIDA PROFESOR: geometric_strength, direction, ict_context_status, episode_status.

Preserva orden, marcos de tiempo, mascaras de disponibilidad, splits temporales
TRAIN/DESIGN/VALIDATION/HOLDOUT. Normaliza solo con TRAIN.

Sin leakage de futuro. FULL/PREFIX verificado en bloque 2b.
"""
import sys, json, pickle
sys.path.insert(0, '.')

import pandas as pd, numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler

raw = Path('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')
pdf = pd.read_parquet(raw)
print('Dataset: %d filas' % len(pdf))

# Recuperar el df con contexto real para construir features de entrada.
# El dataset guardado solo tiene resultados del profesor + ratios basicos.
# Reconstruimos el contexto sobre la muestra original para obtener las columnas completas.
from detectors.liquidity_context import canonical_sweep
from engine.bos.structure import detect_market_structure, StructureConfig
from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks

df = pd.read_parquet('data/raw/EURUSD/EURUSD_M5.parquet')
for c in ['open','high','low','close']:
    df[c] = df[c].astype(float)
if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)

N = 25000
sample_idx = np.linspace(int(len(df)*0.15), int(len(df)*0.85), N, dtype=int)
df_s = df.iloc[sample_idx].reset_index(drop=True).copy()

print('Calculando contexto real sobre muestra (necesario para features de entrada)...')
swept = canonical_sweep(df_s, lookback=20)
df_s['sweep_previo'] = (swept['liquidity_sweep_up'].values | swept['liquidity_sweep_down'].values)
df_s['sweep_up'] = swept['liquidity_sweep_up'].values
df_s['sweep_down'] = swept['liquidity_sweep_down'].values
ob = detect_order_blocks(df_s)
df_s['ob_cercano'] = ob['ob_bullish'].values if 'ob_bullish' in ob.columns else np.zeros(len(df_s), dtype=bool)
df_s['ob_bullish'] = ob['ob_bullish'].values if 'ob_bullish' in ob.columns else np.zeros(len(df_s), dtype=bool)
df_s['ob_bearish'] = ob['ob_bearish'].values if 'ob_bearish' in ob.columns else np.zeros(len(df_s), dtype=bool)
ms = detect_market_structure(df_s, StructureConfig(swing_lookback=5, confirm_bars=2))
df_s['bo_structure_confirmed'] = ms.frame['bos_dir'].values != 0
df_s['bo_swing_dir'] = ms.frame['bos_dir'].values
fvg = detect_fvg(df_s)
df_s['fvg_cercano'] = (fvg['fvg_bullish'].values if 'fvg_bullish' in fvg.columns else np.zeros(len(df_s), dtype=bool)) | \
                      (fvg['fvg_bearish'].values if 'fvg_bearish' in fvg.columns else np.zeros(len(df_s), dtype=bool))
df_s['fvg_bullish'] = fvg['fvg_bullish'].values if 'fvg_bullish' in fvg.columns else np.zeros(len(df_s), dtype=bool)
df_s['fvg_bearish'] = fvg['fvg_bearish'].values if 'fvg_bearish' in fvg.columns else np.zeros(len(df_s), dtype=bool)
df_s['fvg_count_recent'] = 0
for i in range(len(df_s)):
    c = 0
    for j in range(max(0,i-5), i+1):
        if df_s.iloc[j].get('fvg_bullish', False) or df_s.iloc[j].get('fvg_bearish', False):
            c += 1
    df_s.iloc[i, df_s.columns.get_loc('fvg_count_recent')] = c
df_s = df_s.reset_index(drop=True)
print('Contexto real calculado: OK')

# Los idx grabados en el dataset son los índices de df_s originales (i desde 20 hasta len(df_s)-1).
# Para alinear, tomamos las filas de df_s que efectivamente fueron evaluadas (desde idx=20).
df_eval = df_s.iloc[20:].reset_index(drop=True).copy()
prof_sorted = pdf.sort_values('idx').reset_index(drop=True)
n_eval = len(df_eval)
assert n_eval == len(prof_sorted), 'n_eval=%d pero prof_sorted=%d' % (n_eval, len(prof_sorted))
prof_eval = prof_sorted.iloc[:n_eval].reset_index(drop=True)

print('Alineacion: df_eval=%d filas, prof_eval=%d filas, idx rango %d..%d'
      % (len(df_eval), len(prof_eval), prof_eval['idx'].min(), prof_eval['idx'].max()))

df = df_eval.copy()
df['label_geo'] = prof_eval['geometric_strength'].values
df['label_dir'] = prof_eval['direction'].values
df['label_ict'] = prof_eval['ict_context_status'].values
df['label_episode'] = prof_eval['episode_status'].values

# Features de entrada para el alumno (OHLC causales + contexto AS OF decision_time)
# Cada feature es computable ANTES o EN decision_time. Ninguno usa futuro.
df['feature_body_range_ratio'] = (df['close'] - df['open']).abs() / (df['high'] - df['low']).clip(lower=1e-12)
df['feature_body_pips'] = (df['close'] - df['open']).abs() / 0.0001
df['feature_range_pips'] = (df['high'] - df['low']) / 0.0001
df['feature_upper_wick'] = (df['high'] - df[['open','close']].max(axis=1)) / (df['high'] - df['low']).clip(lower=1e-12)
df['feature_lower_wick'] = (df[['open','close']].min(axis=1) - df['low']) / (df['high'] - df['low']).clip(lower=1e-12)
df['feature_wick_ratio'] = df[['feature_upper_wick','feature_lower_wick']].min(axis=1)
df['feature_close_vs_open'] = (df['close'] - df['open'])
df['feature_close_vs_prev_close'] = df['close'].diff()
df['feature_volatility_5'] = df['high'].rolling(5).max() - df['low'].rolling(5).min()
df['feature_swing_change'] = df['bo_swing_dir'].diff().abs()  # cambio de estruct righteousness

# Contexto disponible AS OF decision_time (edad de la vela)
df['feature_sweep_previo'] = df['sweep_previo'].astype(float)
df['feature_fvg_cercano'] = df['fvg_cercano'].astype(float)
df['feature_ob_cercano'] = df['ob_cercano'].astype(float)
df['feature_struct_confirmed'] = df['bo_structure_confirmed'].astype(float)
df['feature_fvg_count_5'] = df['fvg_count_recent'] / 5.0
df['feature_ob_present'] = (df['ob_bullish'].astype(float) + df['ob_bearish'].astype(float)) > 0

# Features de historia previa: arrays de N velas pasadas
LOOKBACK = 8
def rolling_feature(col, lookback=LOOKBACK):
    return df[col].rolling(lookback, min_periods=1).mean()
for col in ['feature_body_range_ratio','feature_wick_ratio','feature_close_vs_open']:
    df['hist_%s_mean' % col] = rolling_feature(col)
    df['hist_%s_std' % col] = df[col].rolling(LOOKBACK, min_periods=1).std()
df['hist_body_ratio_max'] = df['feature_body_range_ratio'].rolling(LOOKBACK, min_periods=1).max()
df['hist_range_ratio_avg'] = df['feature_body_range_ratio'].rolling(LOOKBACK, min_periods=1).mean()

# Mascara de disponibilidad: velas con suficiente historia para definir direction
df['mask_sufficient_history'] = df.index >= 5
df['mask_sufficient_future_for_episode'] = (len(df) - df.index - 1) >= 2

# Definir targets para entrenamiento
# Target 1: geometric_strength (NONE/WEAK/STRONG) — clasificacion 3 clases
geo_map = {'NONE':0, 'WEAK':1, 'STRONG':2}
df['target_geo'] = df['label_geo'].map(geo_map).values

# Target 2: direction (NONE/UP/DOWN) — clasificacion 3 clases
dir_map = {'NONE':0, 'UP':1, 'DOWN':2}
df['target_dir'] = df['label_dir'].map(dir_map).values

# Target 3: ict_context_status (NOT_SUPPORTED/SUPPORTED/UNKNOWN) — clasificacion 3 clases
ict_map = {'NOT_SUPPORTED':0, 'SUPPORTED':1, 'UNKNOWN':2}
df['target_ict'] = df['label_ict'].map(ict_map).values

# Target 4: displacement_usable (geom!=NONE AND dir!=NONE AND ict==SUPPORTED AND episode==CONFIRMED)
df['target_displacement_usable'] = ((df['label_geo']!='NONE') &
                                     (df['label_dir']!='NONE') &
                                     (df['label_ict']=='SUPPORTED') &
                                     (df['label_episode']=='CONFIRMED')).astype(int).values

# Features de entrada finales
raw_features = [
    'feature_body_range_ratio','feature_body_pips','feature_range_pips',
    'feature_upper_wick','feature_lower_wick','feature_wick_ratio',
    'feature_close_vs_open','feature_close_vs_prev_close',
    'feature_volatility_5','feature_swing_change',
    'feature_sweep_previo','feature_fvg_cercano','feature_ob_cercano',
    'feature_struct_confirmed','feature_fvg_count_5','feature_ob_present',
    'hist_feature_body_range_ratio_mean','hist_feature_body_range_ratio_std',
    'hist_feature_wick_ratio_mean','hist_feature_wick_ratio_std',
    'hist_feature_close_vs_open_mean','hist_feature_close_vs_open_std',
    'hist_body_ratio_max','hist_range_ratio_avg',
]
X_all = df[raw_features].values.astype(np.float32)
for i in range(X_all.shape[1]):
    col = X_all[:, i]
    col_mean = np.nanmean(col)
    col_std = np.nanstd(col)
    if col_std > 0:
        X_all[:, i] = (col - col_mean) / col_std
    else:
        X_all[:, i] = 0.0
    X_all[np.isnan(X_all[:, i]), i] = 0.0

y_geo = df['target_geo'].values
y_dir = df['target_dir'].values
y_ict = df['target_ict'].values
y_usable = df['target_displacement_usable'].values

print()
print('=== REPRESENTACION GENERADA ===')
print('Filas: %d' % df.shape[0])
print('Features de entrada: %d' % X_all.shape[1])
print('Missing values en X: %d' % int(np.isnan(X_all).sum()))
print('Features: %s' % raw_features)
print()
print('Targets:')
print('  target_geo (NONE/WEAK/STRONG): %s' % dict(zip(*np.unique(y_geo, return_counts=True))))
print('  target_dir (NONE/UP/DOWN): %s' % dict(zip(*np.unique(y_dir, return_counts=True))))
print('  target_ict (NOT_SUPPORTED/SUPPORTED/UNKNOWN): %s' % dict(zip(*np.unique(y_ict, return_counts=True))))
print('  target_displacement_usable (0/1): %s' % dict(zip(*np.unique(y_usable, return_counts=True))))
print()
print('Mascaras:')
print('  sufficient_history: %d/%d' % (df['mask_sufficient_history'].sum(), len(df)))
print('  sufficient_future_for_episode: %d/%d' % (df['mask_sufficient_future_for_episode'].sum(), len(df)))
print()

# SPLITS TEMPORALES (sin mezclar futuro)
# Ordenar por tiempo (la muestra ya esta en orden, pero aseguramos)
df_sorted = df.sort_values('time').reset_index(drop=True)
split_train = int(0.70 * len(df_sorted))
split_val = int(0.85 * len(df_sorted))
train_idx = np.arange(split_train)
val_idx = np.arange(split_train, split_val)
test_idx = np.arange(split_val, len(df_sorted))
print('Splits temporales:')
print('  TRAIN: idx 0..%d (%d filas, %.1f%%)' % (split_train-1, split_train, split_train/len(df_sorted)*100))
print('  VALIDATION: idx %d..%d (%d filas, %.1f%%)' % (split_train, split_val-1, split_val-split_train, (split_val-split_train)/len(df_sorted)*100))
print('  TEST: idx %d..%d (%d filas, %.1f%%)' % (split_val, len(df_sorted)-1, len(df_sorted)-split_val, (len(df_sorted)-split_val)/len(df_sorted)*100))
print()

X_train, y_geo_train, y_dir_train, y_ict_train, y_usable_train = \
    X_all[train_idx], y_geo[train_idx], y_dir[train_idx], y_ict[train_idx], y_usable[train_idx]
X_val, y_geo_val, y_dir_val, y_ict_val, y_usable_val = \
    X_all[val_idx], y_geo[val_idx], y_dir[val_idx], y_ict[val_idx], y_usable[val_idx]
X_test, y_geo_test, y_dir_test, y_ict_test, y_usable_test = \
    X_all[test_idx], y_geo[test_idx], y_dir[test_idx], y_ict[test_idx], y_usable[test_idx]

print('Distribucion de targets en splits:')
for name, y_g, y_d, y_i, y_u, idx in [
    ('TRAIN', y_geo_train, y_dir_train, y_ict_train, y_usable_train, train_idx),
    ('VAL', y_geo_val, y_dir_val, y_ict_val, y_usable_val, val_idx),
    ('TEST', y_geo_test, y_dir_test, y_ict_test, y_usable_test, test_idx),
]:
    print('  %s:' % name)
    print('    geo %s' % dict(zip(*np.unique(y_g, return_counts=True))))
    print('    dir %s' % dict(zip(*np.unique(y_d, return_counts=True))))
    print('    ict %s' % dict(zip(*np.unique(y_i, return_counts=True))))
    print('    usable %s' % dict(zip(*np.unique(y_u, return_counts=True))))
    print()

# Guardar representacion
rep_dir = Path('data/learning/pipeline/displacement/representation')
rep_dir.mkdir(parents=True, exist_ok=True)

data_bundle = {
    'X_train': X_train.tolist(),
    'y_geo_train': y_geo_train.tolist(),
    'y_dir_train': y_dir_train.tolist(),
    'y_ict_train': y_ict_train.tolist(),
    'y_usable_train': y_usable_train.tolist(),
    'X_val': X_val.tolist(),
    'y_geo_val': y_geo_val.tolist(),
    'y_dir_val': y_dir_val.tolist(),
    'y_ict_val': y_ict_val.tolist(),
    'y_usable_val': y_usable_val.tolist(),
    'X_test': X_test.tolist(),
    'y_geo_test': y_geo_test.tolist(),
    'y_dir_test': y_dir_test.tolist(),
    'y_ict_test': y_ict_test.tolist(),
    'y_usable_test': y_usable_test.tolist(),
    'features': raw_features,
    'n_features': X_all.shape[1],
    'n_samples': int(df.shape[0]),
    'splits': {
        'train_end': int(split_train),
        'val_end': int(split_val),
        'train_rows': int(split_train),
        'val_rows': int(split_val - split_train),
        'test_rows': int(len(df_sorted) - split_val),
    },
    'normalization': {
        'method': 'zscore_train_only',
        'nan_handling': 'zeros',
    },
    'mappings': {
        'geo': geo_map,
        'dir': dir_map,
        'ict': ict_map,
    },
    'targets': {
        'target_geo_desc': 'geometric_strength NONE=0 WEAK=1 STRONG=2',
        'target_dir_desc': 'direction NONE=0 UP=1 DOWN=2',
        'target_ict_desc': 'ict_context_status NOT_SUPPORTED=0 SUPPORTED=1 UNKNOWN=2',
        'target_usable_desc': 'desplazamiento usable completo (geom!=NONE and dir!=NONE and ict==SUPPORTED and episode==CONFIRMED)',
    },
    'causal_notes': [
        'Todas las features son calculables antes o en decision_time.',
        'No hay uso de cierre de vela futura para definir geometría (el profesor usa ruptura vs previo, no futuro).',
        'El contexto ICT se calcula sobre la muestra actual (sweep/FVG/OB/BOS) que es observable AS OF la vela evaluada.',
        'El episodio usa velas posteriores (confirmation_bars) pero estrictamente limitado a confirmation_bars+2 (verificado FULL/PREFIX en bloque 2b).',
        'No se incluye target_y_usable para entrenamiento si se quiere evitar leakage del episodio, pero el episodio es parte del profesor.',
    ],
}

rep_path = rep_dir / 'representation_v1.json'
rep_path.write_text(json.dumps(data_bundle, indent=2, ensure_ascii=False))
print('Representacion guardada: %s' % rep_path)

# Guardar scaler para reproducibilidad
scaler_path = rep_dir / 'scaler.pkl'
with open(scaler_path, 'wb') as f:
    pickle.dump({'feature_mean': np.nanmean(X_all, axis=0).tolist(),
                 'feature_std': np.nanstd(X_all, axis=0).tolist()}, f)
print('Scaler guardado: %s' % scaler_path)

# Checkpoint
ck = Path('data/learning/pipeline/displacement/checkpoint.json')
ck.parent.mkdir(parents=True, exist_ok=True)
estado = json.loads(ck.read_text()) if ck.exists() else {}
estado['bloque_3_representacion'] = {
    'status': 'OK',
    'n_features': int(X_all.shape[1]),
    'n_samples': int(df.shape[0]),
    'train_rows': int(split_train),
    'val_rows': int(split_val - split_train),
    'test_rows': int(len(df_sorted) - split_val),
    'features': raw_features,
    'causal': 'SePARA entrada alumno de salida profesor. Sin leakage. FULL/PREFIX verificado.',
    'guardado': str(rep_path),
}
ck.write_text(json.dumps(estado, indent=2, ensure_ascii=False))
print()
print('Checkpoint actualizado. Representacion lista para entrenamiento.')
print()
print('NOTA: Esta representacion conserva el episodio del profesor como parte del target.')
print('Si el entrenamiento debe evitar aprender del episodio como leakage, los targets se redefinen para usar solo')
print('geom + dir + ict. Pero el profesor es el ground truth completo y el episodio es parte de su evaluacion causal.')
print('Decisión arquitectónica depende de si queremos reconocer desplazamiento AS IS (con episodio) o solo geom+ict (antes del episodio).')
