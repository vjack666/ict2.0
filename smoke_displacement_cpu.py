import os, json, time, multiprocessing as mp
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from pathlib import Path

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

print('=' * 60)
print('SMOKE TEST — Pipeline Displacement ICT en CPU')
print('=' * 60)

# Hardware
cpu_count = mp.cpu_count()
gpus = tf.config.list_physical_devices('GPU')
print(f'CPUs: {cpu_count} | GPUs: {len(gpus)}')

MODE = 'cpu'
NUM_WORKERS = max(2, min(8, cpu_count // 2))
print(f'Modo: {MODE} | Workers: {NUM_WORKERS}')

# Paths
M5_PQ = Path('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')
HTF_PQ = Path('data/learning/pipeline/displacement/m5_htf_context_v1.parquet')
M5_RAW_PQ = Path('data/raw/EURUSD/EURUSD_M5.parquet')

# Configs REDucidas para smoke test
CONFIGS = [
    {'name': 'baseline',    'lr': 0.001, 'batch_size': 256, 'dropout': 0.2, 'hidden': 32, 'epochs': 5},
    {'name': 'lr_low',      'lr': 0.0005, 'batch_size': 256, 'dropout': 0.2, 'hidden': 32, 'epochs': 5},
]

N_CONFIGS = len(CONFIGS)
print(f'Configs (smoke): {N_CONFIGS}')

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

print(f'M5 etiquetado time: {m5_ds["time"].min()} -> {m5_ds["time"].max()}')

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

# Modelo
def build_gru(n_features, hidden, dropout, n_classes):
    model = keras.Sequential([
        layers.GRU(hidden, input_shape=(1, n_features), batch_size=None),
        layers.Dense(hidden, activation='relu'),
        layers.Dropout(dropout),
        layers.Dense(n_classes, activation='softmax')
    ])
    return model

def train_one_config(args):
    (cfg, target_name, y_train, y_val, y_test, n_classes,
     X_tr, X_va, X_te, worker_id) = args
    
    tf.keras.backend.clear_session()
    
    print(f'  [Worker {worker_id}] {cfg["name"]} | {target_name}...')
    t0 = time.time()
    
    model = build_gru(X_tr.shape[2], cfg['hidden'], cfg['dropout'], n_classes)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=cfg['lr']),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    early_stop = keras.callbacks.EarlyStopping(
        monitor='val_loss', patience=3, restore_best_weights=True, verbose=0
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
        'worker_id': worker_id,
    }

# FASE 1 — solo geo y dir para smoke
print('\n' + '=' * 60)
print(f'FASE 1 (SMOKE): {N_CONFIGS} configs x 2 targets')
print(f'Workers: {NUM_WORKERS}')
print('=' * 60)

all_targets = [
    ('geo', y_tr_g, y_va_g, y_te_g, 3),
    ('dir', y_tr_d, y_va_d, y_te_d, 3),
]

results_fase1 = []
worker_counter = 0

for target_name, y_tr, y_va, y_te, n_classes in all_targets:
    print(f'\n=== Target: {target_name} ({n_classes} clases) ===')
    
    tasks = [
        (cfg, target_name, y_tr, y_va, y_te, n_classes,
         X_tr_g, X_va_g, X_te_g, worker_counter + i)
        for i, cfg in enumerate(CONFIGS)
    ]
    worker_counter += len(CONFIGS)
    
    t_start = time.time()
    with mp.Pool(processes=NUM_WORKERS) as pool:
        batch_results = pool.map(train_one_config, tasks)
    results_fase1.extend(batch_results)
    
    elapsed = time.time() - t_start
    print(f'  Time: {len(tasks)} configs en {elapsed:.1f}s ({elapsed/len(tasks):.1f}s por config)')
    
    target_results = [r for r in results_fase1 if r['target'] == target_name]
    sorted_r = sorted(target_results, key=lambda x: x['acc_test'], reverse=True)
    print(f'  Ranking {target_name}:')
    for i, r in enumerate(sorted_r):
        print(f'    {i+1}. [{r["config"]}] acc={r["acc_test"]:.4f}, time={r["time_seconds"]:.1f}s, epochs={r["epochs_run"]}')

print(f'\nSMOKE FASE 1 completada: {len(results_fase1)} resultados')

# FASE 2 — reentrenar top configs
print('\n' + '=' * 60)
print('FASE 2 (SMOKE): Reentrenar top configs')
print('=' * 60)

results_fase2 = []

for target_name, y_tr, y_va, y_te, n_classes in all_targets:
    print(f'\n=== Target: {target_name} ===')
    
    target_results = [r for r in results_fase1 if r['target'] == target_name]
    if not target_results:
        continue
    
    top2 = sorted(target_results, key=lambda x: x['acc_test'], reverse=True)[:2]
    
    print(f'  Top configs:')
    for r in top2:
        print(f'    - [{r["config"]}] acc={r["acc_test"]:.4f}')
    
    tasks_fase2 = []
    for r in top2:
        cfg = next(c for c in CONFIGS if c['name'] == r['config'])
        cfg2 = dict(cfg)
        cfg2['epochs'] = 8  # mas epochs para fase 2
        tasks_fase2.append((cfg2, target_name, y_tr, y_va, y_te, n_classes,
                           X_tr_g, X_va_g, X_te_g, worker_counter))
        worker_counter += 1
    
    t_start = time.time()
    with mp.Pool(processes=NUM_WORKERS) as pool:
        batch_results = pool.map(train_one_config, tasks_fase2)
    results_fase2.extend(batch_results)
    print(f'  Time: {len(tasks_fase2)} configs reentrenados en {time.time()-t_start:.1f}s')

# Resumen
print('\n' + '=' * 60)
print('RESUMEN FINAL (SMOKE TEST)')
print('=' * 60)

all_results = results_fase1 + results_fase2
total_time = sum(r['time_seconds'] for r in all_results)

print(f'\nTotal corridas: {len(all_results)}')
print(f'Tiempo total: {total_time:.1f}s')
print(f'Workers: {NUM_WORKERS} CPUs | GPU: No')

for target_name in ['geo', 'dir']:
    target_results = [r for r in all_results if r['target'] == target_name]
    if not target_results:
        continue
    
    print(f'\n{target_name.upper()} (n={len(target_results)} corridas):')
    top3 = sorted(target_results, key=lambda x: x['acc_test'], reverse=True)[:3]
    for i, r in enumerate(top3):
        print(f'  {i+1}. [{r["config"]}] acc={r["acc_test"]:.4f}, time={r["time_seconds"]:.1f}s, epochs={r["epochs_run"]}, f1_mean={np.mean(r["f1s"]):.4f}')

print('\n--- Configuracion ganadora por target ---')
for target_name in ['geo', 'dir']:
    target_results = [r for r in all_results if r['target'] == target_name]
    if not target_results:
        continue
    best = max(target_results, key=lambda x: x['acc_test'])
    print(f'  {target_name}: {best["config"]} -> acc={best["acc_test"]:.4f}')

print('\n' + '=' * 60)
print('SMOKE TEST COMPLETADO')
print('Para run completo: restaurar epochs=30, configs=8, targets=4')
print('=' * 60)
