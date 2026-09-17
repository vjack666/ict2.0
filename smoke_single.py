"""Smoke test SINGLE PROCESS — Pipeline Displacement ICT en CPU"""
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
print('SMOKE TEST SINGLE PROCESS — Displacement ICT')
print('=' * 60)

# Hardware
import multiprocessing as mp
cpu_count = mp.cpu_count()
gpus = tf.config.list_physical_devices('GPU')
print(f'CPUs: {cpu_count} | GPUs: {len(gpus)} | Modo: CPU')
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

print(f'Features: {len(ALL_F)}')

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

for f in ALL_F:
    if f not in ds.columns:
        ds[f] = 0.0

X = ds[ALL_F].values.astype(np.float32)
y_geo = ds['target_geo'].values.astype(np.int64)
y_dir = ds['target_dir'].values.astype(np.int64)

print(f'\nDatos listos: X={X.shape}')
print(f'y_geo: {np.bincount(y_geo)}')
print(f'y_dir: {np.bincount(y_dir)}')

# Splits
n = len(X)
split_t = int(0.70 * n)
split_v = int(0.85 * n)

X_tr, X_va, X_te = X[:split_t], X[split_t:split_v], X[split_v:]
y_tr_g, y_va_g, y_te_g = y_geo[:split_t], y_geo[split_t:split_v], y_geo[split_v:]
y_tr_d, y_va_d, y_te_d = y_dir[:split_t], y_dir[split_t:split_v], y_dir[split_v:]

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

# Entrenar solo target GEO con baseline
print('\n' + '=' * 60)
print('ENTRENANDO: baseline | target=geo | epochs=5')
print('=' * 60)

cfg = {'name': 'baseline', 'lr': 0.001, 'batch_size': 256, 'dropout': 0.2, 'hidden': 32, 'epochs': 5}

tf.keras.backend.clear_session()

model = build_gru(X_tr_g.shape[2], cfg['hidden'], cfg['dropout'], 3)
model.compile(
    optimizer=keras.optimizers.Adam(learning_rate=cfg['lr']),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

early_stop = keras.callbacks.EarlyStopping(
    monitor='val_loss', patience=3, restore_best_weights=True, verbose=0
)

t0 = time.time()
history = model.fit(
    X_tr_g, y_tr_g,
    validation_data=(X_va_g, y_va_g),
    epochs=cfg['epochs'],
    batch_size=cfg['batch_size'],
    callbacks=[early_stop],
    verbose=1
)

elapsed = time.time() - t0
print(f'\n⏱ Tiempo entrenamiento: {elapsed:.1f}s')
print(f'   Epochs ejecutados: {len(history.history["loss"])}')
print(f'   Val loss final: {history.history["val_loss"][-1]:.4f}')
print(f'   Val acc final: {history.history["accuracy"][-1]:.4f}')

# Evaluar en test
pred_te = model.predict(X_te_g, verbose=0).argmax(axis=1)
acc = accuracy_score(y_te_g, pred_te)
prec, rec, f1, _ = precision_recall_fscore_support(
    y_te_g, pred_te, labels=[0, 1, 2], average=None, zero_division=0
)

print(f'\n=== RESULTADOS TEST ===')
print(f'Accuracy: {acc:.4f}')
print(f'Precision por clase: {prec}')
print(f'Recall por clase: {rec}')
print(f'F1 por clase: {f1}')
print(f'F1 mean: {np.mean(f1):.4f}')

# Guardar resultados
results = {
    'config': cfg['name'],
    'target': 'geo',
    'acc_test': float(acc),
    'time_seconds': float(elapsed),
    'epochs_run': len(history.history['loss']),
    'final_val_loss': float(history.history['val_loss'][-1]),
    'final_val_acc': float(history.history['accuracy'][-1]),
    'precisions': [float(p) for p in prec],
    'recalls': [float(r) for r in rec],
    'f1s': [float(f) for f in f1],
}

out_dir = Path('displacement_results')
out_dir.mkdir(parents=True, exist_ok=True)
with open(out_dir / 'smoke_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f'\n✓ Resultados guardados: {out_dir / "smoke_results.json"}')
print('\n' + '=' * 60)
print('✅ SMOKE TEST COMPLETADO')
print('=' * 60)
