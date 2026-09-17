#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reentrenamiento con features HTF multi-temperatura agregadas."""
import sys, json, time
sys.path.insert(0, '.')

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
import pandas as pd
from pathlib import Path

np.random.seed(17)
torch.manual_seed(17)

# ── Cargar datasets ─────────────────────────────────────────────────────
print('Cargando dataset multi-TF...')
m5_htf = pd.read_parquet('data/learning/pipeline/displacement/m5_htf_context_v1.parquet')
print(f'M5+HTF: {len(m5_htf)} filas, {len(m5_htf.columns)} columnas')

print('\nCargando dataset etiquetado...')
ds = pd.read_parquet('data/learning/pipeline/displacement/displacement_dataset_v1.parquet')
print(f'Dataset etiquetado: {len(ds)} filas')

# Alinear por tiempo (como en el análisis)
m5_orig = pd.read_parquet('data/raw/EURUSD/EURUSD_M5.parquet')
m5_orig['time'] = pd.to_datetime(m5_orig['time']).dt.tz_localize(None)
m5_orig = m5_orig.sort_values('time').reset_index(drop=True)
m5_orig['orig_idx'] = np.arange(len(m5_orig))

ds['time'] = m5_orig['time'].iloc[ds['idx'].values].values
ds_htf = pd.merge_asof(
    ds.sort_values('time'),
    m5_htf.sort_values('time'),
    on='time',
    direction='backward',
    allow_exact_matches=True
)
print(f'Merge: {len(ds_htf)} filas etiquetadas con HTF context')
print(f'NaN en h1_sesgo: {ds_htf["h1_sesgo"].isna().sum()}')
print(f'NaN en h4_sesgo: {ds_htf["h4_sesgo"].isna().sum()}')
print(f'NaN en d1_sesgo: {ds_htf["d1_sesgo"].isna().sum()}')

# Rellenar NaN con 0 (primera vela antes del primer HTF disponible)
ds_htf['h1_sesgo'] = ds_htf['h1_sesgo'].fillna(0)
ds_htf['h1_fuerza'] = ds_htf['h1_fuerza'].fillna(0)
ds_htf['h4_sesgo'] = ds_htf['h4_sesgo'].fillna(0)
ds_htf['h4_fuerza'] = ds_htf['h4_fuerza'].fillna(0)
ds_htf['d1_sesgo'] = ds_htf['d1_sesgo'].fillna(0)
ds_htf['d1_fuerza'] = ds_htf['d1_fuerza'].fillna(0)

# Features de HTF para añadir al modelo
htf_features = ['h1_sesgo', 'h1_fuerza', 'h1_range', 'h4_sesgo', 'h4_fuerza', 'h4_range', 'd1_sesgo', 'd1_fuerza', 'd1_range']
print(f'\nFeatures HTF agregadas: {htf_features}')

# Combinar con features existentes (del bloque 4)
with open('data/learning/pipeline/displacement/representation/representation_v1.json') as f:
    data = json.load(f)
existing_features = data['features']
print(f'Features existentes: {len(existing_features)}')

# Añadir features HTF como nuevas columnas (simuladas desde el dataset alineado)
# Necesitamos reconstruir las features existentes desde el dataset etiquetado
print('\nReconstruyendo features existentes desde dataset etiquetado...')

# Reconstruir features básicas (las que se calcularon en block4)
ds_htf['feature_body_range_ratio'] = (ds_htf['close'] - ds_htf['open']).abs() / (ds_htf['high'] - ds_htf['low']).clip(lower=1e-12)
ds_htf['feature_body_pips'] = (ds_htf['close'] - ds_htf['open']).abs() / 0.0001
ds_htf['feature_range_pips'] = (ds_htf['high'] - ds_htf['low']) / 0.0001
ds_htf['feature_upper_wick'] = (ds_htf['high'] - ds_htf[['open','close']].max(axis=1)) / (ds_htf['high'] - ds_htf['low']).clip(lower=1e-12)
ds_htf['feature_lower_wick'] = (ds_htf[['open','close']].min(axis=1) - ds_htf['low']) / (ds_htf['high'] - ds_htf['low']).clip(lower=1e-12)
ds_htf['feature_wick_ratio'] = ds_htf[['feature_upper_wick','feature_lower_wick']].min(axis=1)
ds_htf['feature_close_vs_open'] = (ds_htf['close'] - ds_htf['open'])
ds_htf['feature_close_vs_prev_close'] = ds_htf['close'].diff()
ds_htf['feature_volatility_5'] = ds_htf['high'].rolling(5).max() - ds_htf['low'].rolling(5).min()
ds_htf['feature_swing_change'] = 0.0  # placeholder (no tenemos BOS en esta muestra)

# Contexto M5 local (sweep, FVG, OB) — no tenemos estos datos en la muestra multi-TF
# Usaremos features HTF como proxy de contexto
ds_htf['feature_sweep_previo'] = 0.0  # sin datos
ds_htf['feature_fvg_cercano'] = 0.0
ds_htf['feature_ob_cercano'] = 0.0
ds_htf['feature_struct_confirmed'] = 0.0
ds_htf['feature_fvg_count_5'] = 0.0
ds_htf['feature_ob_present'] = 0.0

# Features de historia (rolling)
LOOKBACK = 8
for col in ['feature_body_range_ratio', 'feature_wick_ratio', 'feature_close_vs_open']:
    ds_htf['hist_%s_mean' % col] = ds_htf[col].rolling(LOOKBACK, min_periods=1).mean()
    ds_htf['hist_%s_std' % col] = ds_htf[col].rolling(LOOKBACK, min_periods=1).std()
ds_htf['hist_body_ratio_max'] = ds_htf['feature_body_range_ratio'].rolling(LOOKBACK, min_periods=1).max()
ds_htf['hist_range_ratio_avg'] = ds_htf['feature_body_range_ratio'].rolling(LOOKBACK, min_periods=1).mean()

# Recortar primeras filas con NaN por diff/rolling
ds_htf = ds_htf.iloc[20:].reset_index(drop=True)

# Targets
geo_map = {'NONE': 0, 'WEAK': 1, 'STRONG': 2}
dir_map = {'NONE': 0, 'UP': 1, 'DOWN': 2}
ict_map = {'NOT_SUPPORTED': 0, 'SUPPORTED': 1, 'UNKNOWN': 2}

ds_htf['target_geo'] = ds_htf['geometric_strength'].map(geo_map).values
ds_htf['target_dir'] = ds_htf['direction'].map(dir_map).values
ds_htf['target_ict'] = ds_htf['ict_context_status'].map(ict_map).values
ds_htf['target_usable'] = (
    (ds_htf['geometric_strength'] != 'NONE') &
    (ds_htf['direction'] != 'NONE') &
    (ds_htf['ict_context_status'] == 'SUPPORTED') &
    (ds_htf['episode_status'] == 'CONFIRMED')
).astype(int).values

# Features de entrada
base_features = [
    'feature_body_range_ratio', 'feature_body_pips', 'feature_range_pips',
    'feature_upper_wick', 'feature_lower_wick', 'feature_wick_ratio',
    'feature_close_vs_open', 'feature_close_vs_prev_close',
    'feature_volatility_5', 'feature_swing_change',
    'feature_sweep_previo', 'feature_fvg_cercano', 'feature_ob_cercano',
    'feature_struct_confirmed', 'feature_fvg_count_5', 'feature_ob_present',
    'hist_feature_body_range_ratio_mean', 'hist_feature_body_range_ratio_std',
    'hist_feature_wick_ratio_mean', 'hist_feature_wick_ratio_std',
    'hist_feature_close_vs_open_mean', 'hist_feature_close_vs_open_std',
    'hist_body_ratio_max', 'hist_range_ratio_avg',
]
new_features = base_features + htf_features
print(f'Total features con HTF: {len(new_features)} ({(len(new_features) - len(base_features))} nuevas de HTF)')

X_all = ds_htf[new_features].values.astype(np.float32)
y_geo = ds_htf['target_geo'].values.astype(np.int64)
y_dir = ds_htf['target_dir'].values.astype(np.int64)
y_ict = ds_htf['target_ict'].values.astype(np.int64)
y_usable = ds_htf['target_usable'].values.astype(np.int64)

print(f'\nDatos listos: X={X_all.shape}, y_geo={len(y_geo)}, y_usable={y_usable.sum()}')

# Splits temporales (mismo corte que antes: 70/15/15)
split_train = int(0.70 * len(X_all))
split_val = int(0.85 * len(X_all))
X_train, X_val, X_test = X_all[:split_train], X_all[split_train:split_val], X_all[split_val:]
y_geo_train, y_geo_val, y_geo_test = y_geo[:split_train], y_geo[split_train:split_val], y_geo[split_val:]
y_dir_train, y_dir_val, y_dir_test = y_dir[:split_train], y_dir[split_train:split_val], y_dir[split_val:]
y_ict_train, y_ict_val, y_ict_test = y_ict[:split_train], y_ict[split_train:split_val], y_ict[split_val:]
y_usable_train, y_usable_val, y_usable_test = y_usable[:split_train], y_usable[split_train:split_val], y_usable[split_val:]

print(f'\nSplit: TRAIN={len(X_train)}, VAL={len(X_val)}, TEST={len(X_test)}')
print(f'USABLE en TEST: {y_usable_test.sum()}')

# ── Normalización (solo con train) ──────────────────────────────────────
mean = X_train.mean(axis=0, keepdims=True)
std = np.where(X_train.std(axis=0, keepdims=True) == 0, 1.0, X_train.std(axis=0, keepdims=True))
X_train_n = (X_train - mean) / std
X_val_n = (X_val - mean) / std
X_test_n = (X_test - mean) / std

print('\n=== Entrenamiento TABULAR con HTF features ===')
print('='*60)

tabular_results_htf = {}
for target_name, y_tr, y_v, y_te in [
    ('geo', y_geo_train, y_geo_val, y_geo_test),
    ('dir', y_dir_train, y_dir_val, y_dir_test),
    ('ict', y_ict_train, y_ict_val, y_ict_test),
    ('usable', y_usable_train, y_usable_val, y_usable_test),
]:
    labels = sorted(set(list(y_tr) + list(y_v) + list(y_te)))
    lr = LogisticRegression(max_iter=2000, class_weight='balanced', solver='lbfgs', random_state=17)
    lr.fit(X_train_n, y_tr)
    pred_v = lr.predict(X_val_n)
    pred_t = lr.predict(X_test_n)
    acc_v = accuracy_score(y_v, pred_v)
    acc_t = accuracy_score(y_te, pred_t)
    prec, rec, f1, _ = precision_recall_fscore_support(y_te, pred_t, labels=labels, average=None, zero_division=0)
    tabular_results_htf[target_name] = {
        'acc_val': float(acc_v),
        'acc_test': float(acc_t),
        'labels': [int(l) for l in labels],
        'prec_test': [float(p) for p in prec],
        'rec_test': [float(r) for r in rec],
        'f1_test': [float(f) for f in f1],
    }
    print(f'\n[{target_name}] acc_test={acc_t:.4f}')
    for li, lab in enumerate(labels):
        print(f'  label={lab}: prec={prec[li]:.4f}, rec={rec[li]:.4f}, f1={f1[li]:.4f}')

print('\n=== Entrenamiento GRU con HTF features ===')
print('='*60)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Device: {device}')

import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

class SimpleGRU(nn.Module):
    def __init__(self, n_features, hidden=32, n_classes=3, dropout=0.2):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, num_layers=1, batch_first=True)
        self.fc1 = nn.Linear(hidden, hidden)
        self.drop = nn.Dropout(dropout)
        self.out = nn.Linear(hidden, n_classes)
        self.relu = nn.ReLU()
    def forward(self, x):
        h, _ = self.gru(x)
        h = h[:, -1, :]
        h = self.drop(self.relu(self.fc1(h)))
        return self.out(h)

def train_gru(target_name, y_tr, y_te, n_classes, n_epochs=30):
    X_tr_t = torch.tensor(X_train_n.reshape(-1, 1, X_train_n.shape[1]), dtype=torch.float32)
    X_te_t = torch.tensor(X_test_n.reshape(-1, 1, X_test_n.shape[1]), dtype=torch.float32)
    y_tr_t = torch.tensor(y_tr, dtype=torch.long)
    train_ds = TensorDataset(X_tr_t, y_tr_t)
    train_ldr = DataLoader(train_ds, batch_size=256, shuffle=True)
    X_val_t = torch.tensor(X_val_n.reshape(-1, 1, X_val_n.shape[1]), dtype=torch.float32)
    
    if target_name == 'geo':
        y_val_ref = torch.tensor(y_geo_val, dtype=torch.long)
    elif target_name == 'dir':
        y_val_ref = torch.tensor(y_dir_val, dtype=torch.long)
    elif target_name == 'ict':
        y_val_ref = torch.tensor(y_ict_val, dtype=torch.long)
    else:
        y_val_ref = torch.tensor(y_usable_val, dtype=torch.long)
    
    model = SimpleGRU(X_train_n.shape[1], hidden=32, n_classes=n_classes).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    crit = nn.CrossEntropyLoss()
    best_state = None
    best_acc = -1.0
    
    for ep in range(n_epochs):
        model.train()
        for xb, yb in train_ldr:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = crit(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            pred_v = model(X_val_t.to(device)).argmax(1).cpu().numpy()
            acc_v = float(accuracy_score(y_val_ref.numpy(), pred_v))
        if acc_v > best_acc:
            best_acc = acc_v
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        if (ep+1) % 10 == 0:
            print(f'  [{target_name}] epoch {ep+1}/{n_epochs} val_acc={acc_v:.4f}')
    
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        logits_te = model(torch.tensor(X_test_n.reshape(-1, 1, X_test_n.shape[1]), dtype=torch.float32).to(device))
        pred_te = logits_te.argmax(1).cpu().numpy()
    
    labels = sorted(set(list(y_tr) + list(y_te)))
    prec, rec, f1, _ = precision_recall_fscore_support(y_te, pred_te, labels=labels, average=None, zero_division=0)
    return {
        'acc_test': float(accuracy_score(y_te, pred_te)),
        'labels': [int(l) for l in labels],
        'prec_test': [float(p) for p in prec],
        'rec_test': [float(r) for r in rec],
        'f1_test': [float(f) for f in f1],
    }

gru_results_htf = {}
for target_name, y_tr, y_te, n_classes in [
    ('geo', y_geo_train, y_geo_test, 3),
    ('dir', y_dir_train, y_dir_test, 3),
    ('ict', y_ict_train, y_ict_test, 2),
    ('usable', y_usable_train, y_usable_test, 2),
]:
    if target_name == 'usable' and n_classes == 2 and y_usable_test.sum() < 10:
        print(f'\n[Training GRU] {target_name}: SALTADO (demasiadas pocas muestras positivas en test: {y_usable_test.sum()})')
        gru_results_htf[target_name] = {'skipped': True, 'reason': f'y_usable_test.sum()={y_usable_test.sum()}'}
        continue
    print(f'\n[Training GRU] {target_name} ({n_classes} classes, {X_train_n.shape[1]} features)')
    gru_results_htf[target_name] = train_gru(target_name, y_tr, y_te, n_classes)

# ── Resumen comparativo (sin HTF vs con HTF) ──────────────────────────
print('\n' + '='*60)
print('COMPARATIVO: sin HTF (fase4) vs con HTF (ahora)')
print('='*60)

# Cargar resultados sin HTF
with open('data/learning/pipeline/displacement/phase4_training_results.json') as f:
    results_old = json.load(f)

for tn in ['geo', 'dir', 'ict', 'usable']:
    old_tab = results_old['tabular_baseline'][tn]['acc_test']
    new_tab = tabular_results_htf[tn]['acc_test']
    delta_tab = new_tab - old_tab
    
    old_gru = results_old['gru_temporal'][tn]['acc_test']
    new_gru = gru_results_htf[tn]['acc_test']
    delta_gru = new_gru - old_gru
    
    print(f'\n[{tn}]')
    print(f'  TABULAR:  sin HTF={old_tab:.4f} | con HTF={new_tab:.4f} | delta={delta_tab:+.4f}')
    print(f'  GRU:      sin HTF={old_gru:.4f} | con HTF={new_gru:.4f} | delta={delta_gru:+.4f}')
    # Detail per class
    for li in range(len(new_tab['labels'])):
        lab = new_tab['labels'][li]
        if tn in results_old['tabular_baseline'] and li < len(results_old['tabular_baseline'][tn]['f1_test']):
            old_f1 = results_old['tabular_baseline'][tn]['f1_test'][li]
            new_f1 = new_tab['f1_test'][li]
            print(f'    label={lab} TABULAR f1: {old_f1:.4f} -> {new_f1:.4f} ({new_f1-old_f1:+.4f})')

# ── Guardar resultados ─────────────────────────────────────────────────
results = {
    'phase': 'phase4_retrain_with_htf',
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'features_total': len(new_features),
    'new_htf_features': htf_features,
    'tabular_with_htf': tabular_results_htf,
    'gru_with_htf': gru_results_htf,
    'comparison_with_old': {
        tn: {
            'tabular_old': results_old['tabular_baseline'][tn]['acc_test'],
            'tabular_new': tabular_results_htf[tn]['acc_test'],
            'tabular_delta': float(tabular_results_htf[tn]['acc_test'] - results_old['tabular_baseline'][tn]['acc_test']),
            'gru_old': results_old['gru_temporal'][tn]['acc_test'],
            'gru_new': gru_results_htf[tn]['acc_test'],
            'gru_delta': float(gru_results_htf[tn]['acc_test'] - results_old['gru_temporal'][tn]['acc_test']),
        }
        for tn in ['geo', 'dir', 'ict', 'usable']
    },
    'conclusion': 'Reentrenamiento con features HTF multi-temperatura. Ver resultados de comparativo arriba.',
}
Path('data/learning/pipeline/displacement/phase4_htf_retrain_results.json').parent.mkdir(parents=True, exist_ok=True)
with open('data/learning/pipeline/displacement/phase4_htf_retrain_results.json', 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('\nGuardado: data/learning/pipeline/displacement/phase4_htf_retrain_results.json')
print('\n=== REENTRENAMIENTO CON HTF COMPLETADO ===')
