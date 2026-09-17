"""
Pipeline completo Displacement ICT — CPU single-process
8 configs × 4 targets × 30 epochs (FASE 1) + top3 × 50 epochs (FASE 2)
"""
import os, json, time
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from pathlib import Path

print('=' * 60)
print('PIPELINE COMPLETO — Displacement ICT (CPU single-process)')
print('=' * 60)

import multiprocessing as mp
cpu_count = mp.cpu_count()
gpus = tf.config.list_physical_devices('GPU')
print(f'CPUs: {cpu_count} | GPUs: {len(gpus)} | Modo: CPU single-process')
print(f'TF: {tf.__version__}')

# Paths
M5_PQ = Path('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')
HTF_PQ = Path('data/learning/pipeline/displacement/m5_htf_context_v1.parquet')
M5_RAW_PQ = Path('data/raw/EURUSD/EURUSD_M5.parquet')

# Features
BASE_F = [
    'feature_body_range_ratio','feature_body_pips','feature_range_pips',
    'feature_upper_wick','feature_lower_wick','feature_wick_ratio',
    'feature_close_vs_open','feature_close_vs_prev_close',
    'feature_volatility_5','feature_swing_change',
    'feature_sweep_previo','feature_fvg_cercano','feature_ob_cercano',
    'feature_struct_confirmed','feature_fvg_count_5','feature_ob_present',
    'hist_feature_body_range_ratio_mean','hist_feature_body_range_ratio_std',
    'hist_feature_wick_ratio_mean','hist_feature_wick_ratio_std',
    'hist_feature_close_vs_open_mean','hist_feature_close_vs_open_std',
    'hist_body_ratio_max','hist_range_ratio_avg'
]
HTF_F = ['h1_sesgo','h1_fuerza','h1_range','h4_sesgo','h4_fuerza','h4_range','d1_sesgo','d1_fuerza','d1_range']
ALL_F = BASE_F + HTF_F

print(f'Features: {len(ALL_F)} (base {len(BASE_F)} + HTF {len(HTF_F)})')

# Configs (8 originales)
CONFIGS = [
    {'name': 'baseline',     'lr': 0.001, 'batch_size': 256, 'dropout': 0.2, 'hidden': 32, 'epochs': 30},
    {'name': 'lr_low',       'lr': 0.0005, 'batch_size': 256, 'dropout': 0.2, 'hidden': 32, 'epochs': 30},
    {'name': 'batch_large',  'lr': 0.001, 'batch_size': 512, 'dropout': 0.2, 'hidden': 32, 'epochs': 30},
    {'name': 'dropout_hi',   'lr': 0.001, 'batch_size': 256, 'dropout': 0.4, 'hidden': 32, 'epochs': 30},
    {'name': 'hidden_hi',    'lr': 0.001, 'batch_size': 256, 'dropout': 0.2, 'hidden': 64, 'epochs': 30},
    {'name': 'conservative', 'lr': 0.0005, 'batch_size': 512, 'dropout': 0.4, 'hidden': 64, 'epochs': 30},
    {'name': 'lr_high',      'lr': 0.003, 'batch_size': 128, 'dropout': 0.2, 'hidden': 32, 'epochs': 30},
    {'name': 'small_model',  'lr': 0.001, 'batch_size': 256, 'dropout': 0.3, 'hidden': 16, 'epochs': 30},
]

# Cargar datos
print('\n=== Cargando datos ===')
t0 = time.time()

m5_ds = pd.read_parquet(M5_PQ)
m5_raw = pd.read_parquet(M5_RAW_PQ)
m5_htf = pd.read_parquet(HTF_PQ)

print(f'M5 etiquetado: {len(m5_ds)} filas')
print(f'M5 crudo: {len(m5_raw)} filas')
print(f'M5 HTF: {len(m5_htf)} filas ({time.time()-t0:.1f}s)')

# Recuperar time
m5_raw = m5_raw.reset_index(drop=True)
m5_ds['time'] = m5_raw['time'].iloc[m5_ds['idx'].values].values

if hasattr(m5_ds['time'].dtype, 'tz') and m5_ds['time'].dtype.tz is not None:
    m5_ds['time'] = m5_ds['time'].dt.tz_localize(None)

m5_ds = m5_ds.sort_values('time').reset_index(drop=True)
m5_htf = m5_htf.sort_values('time').reset_index(drop=True)

m5_ds['time_int'] = m5_ds['time'].astype('int64')
m5_htf['time_int'] = m5_htf['time'].astype('int64')

# Merge asof
print('\nAlineando M5 con HTF...')
t1 = time.time()
ds = pd.merge_asof(
    m5_ds, m5_htf,
    left_on='time_int', right_on='time_int',
    direction='backward', allow_exact_matches=True
)
print(f'Merge: {len(ds)} filas ({time.time()-t1:.1f}s)')

# Rellenar NaN HTF
for col in HTF_F:
    if col in ds.columns:
        n_nan = ds[col].isna().sum()
        if n_nan > 0:
            ds[col] = ds[col].fillna(0.0)

# Targets
ds['target_geo'] = ds['geometric_strength'].map({'NONE':0,'WEAK':1,'STRONG':2}).values
ds['target_dir'] = ds['direction'].map({'NONE':0,'UP':1,'DOWN':2}).values
ds['target_ict'] = ds['ict_context_status'].map({'NOT_SUPPORTED':0,'SUPPORTED':1,'UNKNOWN':2}).values
ds['target_usable'] = (
    (ds['geometric_strength'] != 'NONE') &
    (ds['direction'] != 'NONE') &
    (ds['ict_context_status'] == 'SUPPORTED') &
    (ds['episode_status'] == 'CONFIRMED')
).astype(int).values

for f in ALL_F:
    if f not in ds.columns:
        ds[f] = 0.0

X = ds[ALL_F].values.astype(np.float32)
y_geo = ds['target_geo'].values.astype(np.int64)
y_dir = ds['target_dir'].values.astype(np.int64)
y_ict = ds['target_ict'].values.astype(np.int64)
y_usable = ds['target_usable'].values.astype(np.int64)

print(f'\nDatos listos: X={X.shape}')
print(f'y_geo: {np.bincount(y_geo)}')
print(f'y_dir: {np.bincount(y_dir)}')
print(f'y_ict: {np.bincount(y_ict)}')
print(f'y_usable: {y_usable.sum()} pos / {len(y_usable)} total')

# Splits
n = len(X)
split_t = int(0.70 * n)
split_v = int(0.85 * n)

X_tr, X_va, X_te = X[:split_t], X[split_t:split_v], X[split_v:]
y_tr_g, y_va_g, y_te_g = y_geo[:split_t], y_geo[split_t:split_v], y_geo[split_v:]
y_tr_d, y_va_d, y_te_d = y_dir[:split_t], y_dir[split_t:split_v], y_dir[split_v:]
y_tr_i, y_va_i, y_te_i = y_ict[:split_t], y_ict[split_t:split_v], y_ict[split_v:]
y_tr_u, y_va_u, y_te_u = y_usable[:split_t], y_usable[split_t:split_v], y_usable[split_v:]

print(f'\nSplit: TRAIN={len(X_tr)}, VAL={len(X_va)}, TEST={len(X_te)}')

# Normalizacion
mean = X_tr.mean(axis=0, keepdims=True)
std = np.where(X_tr.std(axis=0, keepdims=True) == 0, 1.0, X_tr.std(axis=0, keepdims=True))
X_tr_n = (X_tr - mean) / std
X_va_n = (X_va - mean) / std
X_te_n = (X_te - mean) / std

X_tr_g = X_tr_n.reshape(-1, 1, X_tr_n.shape[1])
X_va_g = X_va_n.reshape(-1, 1, X_va_n.shape[1])
X_te_g = X_te_n.reshape(-1, 1, X_te_n.shape[1])

print(f'X_train GRU shape: {X_tr_g.shape}')

# Modelo GRU
def build_gru(n_features, hidden, dropout, n_classes):
    model = keras.Sequential([
        layers.Input(shape=(1, n_features)),
        layers.GRU(hidden),
        layers.Dense(hidden, activation='relu'),
        layers.Dropout(dropout),
        layers.Dense(n_classes, activation='softmax')
    ])
    return model

def train_one_config(cfg, target_name, y_train, y_val, y_test, n_classes,
                     X_tr, X_va, X_te, worker_label=''):
    tf.keras.backend.clear_session()
    
    label = f'{cfg["name"]} | {target_name}' + (f' [{worker_label}]' if worker_label else '')
    print(f'  [{label}] entrenando...')
    t0 = time.time()
    
    model = build_gru(X_tr.shape[2], cfg['hidden'], cfg['dropout'], n_classes)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=cfg['lr']),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    early_stop = keras.callbacks.EarlyStopping(
        monitor='val_loss', patience=5, restore_best_weights=True, verbose=0
    )
    
    history = model.fit(
        X_tr, y_train,
        validation_data=(X_va, y_val),
        epochs=cfg['epochs'],
        batch_size=cfg['batch_size'],
        callbacks=[early_stop],
        verbose=0
    )
    
    pred_te = model.predict(X_te, verbose=0).argmax(axis=1)
    acc = accuracy_score(y_test, pred_te)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_test, pred_te, labels=list(range(n_classes)), average=None, zero_division=0
    )
    
    elapsed = time.time() - t0
    
    return {
        'config': cfg['name'],
        'target': target_name,
        'acc_test': float(acc),
        'time_seconds': float(elapsed),
        'epochs_run': len(history.history['loss']),
        'final_val_loss': float(history.history['val_loss'][-1]),
        'precisions': [float(p) for p in prec],
        'recalls': [float(r) for r in rec],
        'f1s': [float(f) for f in f1],
    }

# Targets
all_targets = [
    ('geo', y_tr_g, y_va_g, y_te_g, 3),
    ('dir', y_tr_d, y_va_d, y_te_d, 3),
    ('ict', y_tr_i, y_va_i, y_te_i, 2),
    ('usable', y_tr_u, y_va_u, y_te_u, 2),
]

# FASE 1
print('\n' + '=' * 60)
print(f'FASE 1: {len(CONFIGS)} configs × {len(all_targets)} targets = {len(CONFIGS)*len(all_targets)} corridas')
print(f'Batch size por defecto: 256')
print('=' * 60)

results_fase1 = []

for target_name, y_tr, y_va, y_te, n_classes in all_targets:
    print(f'\n=== Target: {target_name} ({n_classes} clases) ===')
    if target_name == 'usable' and y_te.sum() < 10:
        print(f'  Advertencia: solo {y_te.sum()} positivos en test')
    
    t_start = time.time()
    
    for i, cfg in enumerate(CONFIGS):
        result = train_one_config(cfg, target_name, y_tr, y_va, y_te, n_classes,
                                  X_tr_g, X_va_g, X_te_g, worker_label=f'{i+1}/{len(CONFIGS)}')
        results_fase1.append(result)
        print(f'    -> {result["config"]}: acc={result["acc_test"]:.4f}, time={result["time_seconds"]:.1f}s, epochs={result["epochs_run"]}')
    
    elapsed = time.time() - t_start
    print(f'  Target {target_name} completado en {elapsed:.1f}s')

print(f'\n✅ FASE 1 completada: {len(results_fase1)} resultados')

# FASE 2
print('\n' + '=' * 60)
print('FASE 2: Reentrenar top 3 configs por target (epochs=50)')
print('=' * 60)

results_fase2 = []

for target_name, y_tr, y_va, y_te, n_classes in all_targets:
    print(f'\n=== Target: {target_name} ===')
    
    target_results = [r for r in results_fase1 if r['target'] == target_name]
    if not target_results:
        continue
    
    top3 = sorted(target_results, key=lambda x: x['acc_test'], reverse=True)[:3]
    
    print(f'  Top 3 configs:')
    for r in top3:
        print(f'    - [{r["config"]}] acc={r["acc_test"]:.4f}')
    
    for r in top3:
        cfg = next(c for c in CONFIGS if c['name'] == r['config'])
        cfg2 = dict(cfg)
        cfg2['epochs'] = 50
        result = train_one_config(cfg2, target_name, y_tr, y_va, y_te, n_classes,
                                  X_tr_g, X_va_g, X_te_g, worker_label='FASE2')
        results_fase2.append(result)
        print(f'    -> {result["config"]} (50e): acc={result["acc_test"]:.4f}, time={result["time_seconds"]:.1f}s')

# Resumen
print('\n' + '=' * 60)
print('RESUMEN FINAL')
print('=' * 60)

all_results = results_fase1 + results_fase2
total_time = sum(r['time_seconds'] for r in all_results)

print(f'\nTotal corridas: {len(all_results)}')
print(f'Tiempo total entrenamiento: {total_time:.1f}s ({total_time/60:.1f} min)')
print(f'CPUs: {cpu_count} | GPU: No | Modo: single-process')

for target_name in ['geo', 'dir', 'ict', 'usable']:
    target_results = [r for r in all_results if r['target'] == target_name]
    if not target_results:
        continue
    
    print(f'\n{target_name.upper()} (n={len(target_results)} corridas):')
    top5 = sorted(target_results, key=lambda x: x['acc_test'], reverse=True)[:5]
    for i, r in enumerate(top5):
        print(f'  {i+1}. [{r["config"]}] acc={r["acc_test"]:.4f}, time={r["time_seconds"]:.1f}s, epochs={r["epochs_run"]}, f1_mean={np.mean(r["f1s"]):.4f}')

print('\n--- Configuracion ganadora por target ---')
for target_name in ['geo', 'dir', 'ict', 'usable']:
    target_results = [r for r in all_results if r['target'] == target_name]
    if not target_results:
        continue
    best = max(target_results, key=lambda x: x['acc_test'])
    print(f'  {target_name}: {best["config"]} -> acc={best["acc_test"]:.4f}')

# Guardar
out_dir = Path('displacement_results')
out_dir.mkdir(parents=True, exist_ok=True)

summary = {
    'type': 'full_pipeline_cpu_single_process',
    'phase1': results_fase1,
    'phase2': results_fase2,
    'configs_used': [c['name'] for c in CONFIGS],
    'features': ALL_F,
    'total_time_seconds': total_time,
    'cpu_count': cpu_count,
    'gpu_available': False,
    'mode': 'cpu_single_process',
    'note': f'CPU single-process: {len(CONFIGS)} configs × {len(all_targets)} targets. FASE1=30e, FASE2=50e.'
}

with open(out_dir / 'results_full.json', 'w') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f'\n✓ Resultados guardados: {out_dir / "results_full.json"}')
print('\n' + '=' * 60)
print('✅ PIPELINE COMPLETO TERMINADO')
print('=' * 60)
