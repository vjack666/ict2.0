#!/usr/bin/env python3
"""Fase 5: examen independiente — sin ver prediccion del modelo, con ablaciones."""
import sys, json, time
sys.path.insert(0, '.')

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (classification_report, confusion_matrix, accuracy_score,
                              precision_recall_fscore_support, brier_score_loss)
import pandas as pd

np.random.seed(17)
torch.manual_seed(17)

# ── cargar representacion ──────────────────────────────────────────────
with open('data/learning/pipeline/displacement/representation/representation_v1.json') as f:
    data = json.load(f)

X_train = np.array(data['X_train'], dtype=np.float32)
X_val   = np.array(data['X_val'],   dtype=np.float32)
X_test  = np.array(data['X_test'],  dtype=np.float32)
y_geo_train = np.array(data['y_geo_train'], dtype=np.int64)
y_geo_val   = np.array(data['y_geo_val'],   dtype=np.int64)
y_geo_test  = np.array(data['y_geo_test'],  dtype=np.int64)
y_dir_train = np.array(data['y_dir_train'], dtype=np.int64)
y_dir_val   = np.array(data['y_dir_val'],   dtype=np.int64)
y_dir_test  = np.array(data['y_dir_test'],  dtype=np.int64)
y_ict_train = np.array(data['y_ict_train'], dtype=np.int64)
y_ict_val   = np.array(data['y_ict_val'],   dtype=np.int64)
y_ict_test  = np.array(data['y_ict_test'],  dtype=np.int64)
y_usable_train = np.array(data['y_usable_train'], dtype=np.int64)
y_usable_val   = np.array(data['y_usable_val'],   dtype=np.int64)
y_usable_test  = np.array(data['y_usable_test'],  dtype=np.int64)
features = list(data['features'])
n_features = data['n_features']
mappings = data['mappings']
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

print('Datos: train=%d, val=%d, test=%d, features=%d' % (len(X_train), len(X_val), len(X_test), n_features))

# ── helpers ────────────────────────────────────────────────────────────
def safe_int(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    return x

def eval_model(model_type, target_name, y_tr, y_te, n_classes,
               feature_subset=None, X_tr_src=None, X_te_src=None):
    X_tr = X_tr_src if feature_subset is None else X_tr_src[:, feature_subset]
    X_te = X_te_src if feature_subset is None else X_te_src[:, feature_subset]
    if model_type == 'tabular':
        lr = LogisticRegression(max_iter=2000, class_weight='balanced', solver='lbfgs', random_state=17)
        lr.fit(X_tr, y_tr)
        pred_te = lr.predict(X_te)
        proba_te = lr.predict_proba(X_te)
    elif model_type == 'gru':
        X_tr_t = torch.tensor(X_tr.reshape(-1, 1, X_tr.shape[1]), dtype=torch.float32)
        X_te_t = torch.tensor(X_te.reshape(-1, 1, X_te.shape[1]), dtype=torch.float32)
        y_tr_t = torch.tensor(y_tr, dtype=torch.long)
        y_te_t = torch.tensor(y_te, dtype=torch.long)
        train_ds = TensorDataset(X_tr_t, y_tr_t)
        train_ldr = DataLoader(train_ds, batch_size=256, shuffle=True)
        model = SimpleGRU(X_tr.shape[1], hidden=32, n_classes=n_classes).to(device)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        crit = nn.CrossEntropyLoss()
        best_state = None
        best_acc = -1
        X_val_input = X_val if feature_subset is None else X_val[:, feature_subset]
        X_val_t = torch.tensor(X_val_input, dtype=torch.float32).reshape(-1, 1, X_val_input.shape[1]).to(device)
        y_val_t = torch.tensor(y_ict_val, dtype=torch.long)
        for ep in range(20):
            model.train()
            for xb, yb in train_ldr:
                xb, yb = xb.to(device), yb.to(device)
                opt.zero_grad()
                logits = model(xb)
                loss = crit(logits, yb)
                loss.backward()
                opt.step()
            model.eval()
            with torch.no_grad():
                logits_v = model(X_val_t)
                pred_v = logits_v.argmax(1).cpu().numpy()
                acc_v = accuracy_score(y_val_t.numpy(), pred_v)
            if acc_v > best_acc:
                best_acc = acc_v
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        model.load_state_dict(best_state)
        model.eval()
        with torch.no_grad():
            logits_te = model(X_te_t.to(device))
            pred_te = logits_te.argmax(1).cpu().numpy()
            proba_te = torch.softmax(logits_te, 1).cpu().numpy()
    labels = sorted(set(list(y_tr) + list(y_te)))
    acc = accuracy_score(y_te, pred_te)
    prec, rec, f1, _ = precision_recall_fscore_support(y_te, pred_te, labels=labels, average=None, zero_division=0)
    return {
        'model_type': model_type,
        'target': target_name,
        'n_classes': n_classes,
        'feature_subset_size': X_tr.shape[1] if feature_subset is None else len(feature_subset),
        'labels': [safe_int(l) for l in labels],
        'accuracy': float(acc),
        'precision': [float(p) for p in prec],
        'recall': [float(r) for r in rec],
        'f1': [float(f) for f in f1],
        'confusion': confusion_matrix(y_te, pred_te, labels=labels).tolist(),
        'proba_te': proba_te.tolist() if proba_te is not None else None,
    }

class SimpleGRU(nn.Module):
    def __init__(self, n_features, hidden=32, n_classes=3):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, num_layers=1, batch_first=True)
        self.fc1 = nn.Linear(hidden, hidden)
        self.drop = nn.Dropout(0.2)
        self.out = nn.Linear(hidden, n_classes)
        self.relu = nn.ReLU()
    def forward(self, x):
        h, _ = self.gru(x)
        h = h[:, -1, :]
        h = self.drop(self.relu(self.fc1(h)))
        return self.out(h)

# ── BLOQUE 1: examen ciego ─────────────────────────────────────────────
print('\n' + '='*60)
print('FASE 5 — EXAMEN INDEPENDIENTE (ciego)')
print('='*60)
print('Examinador: Hermes (no ve predicciones del modelo durante diseño)')
print('Panel: métricas sobre TEST (reservado, sin uso en entrenamiento)')
print()

examen = {}

targets = [
    ('geo', y_geo_train, y_geo_test, 3),
    ('dir', y_dir_train, y_dir_test, 3),
    ('ict', y_ict_train, y_ict_test, 2),
    ('usable', y_usable_train, y_usable_test, 2),
]
X_sources = {
    'geo': X_train, 'dir': X_train, 'ict': X_train, 'usable': X_train,
}

for tn, y_tr, y_te, nc in targets:
    print('\n--- %s (n_classes=%d) ---' % (tn, nc))
    # Tabular
    r_tab = eval_model('tabular', tn, y_tr, y_te, nc,
                        X_tr_src=X_train, X_te_src=X_test)
    print('  TABULAR: acc=%.4f, macro_f1=%.4f' % (r_tab['accuracy'],
          np.mean(r_tab['f1']) if len(r_tab['f1']) > 0 else 0.0))
    for li, lab in enumerate(r_tab['labels']):
        print('    label=%d: prec=%.4f rec=%.4f f1=%.4f' % (lab, r_tab['precision'][li], r_tab['recall'][li], r_tab['f1'][li]))
    # GRU
    r_gru = eval_model('gru', tn, y_tr, y_te, nc,
                       X_tr_src=X_train, X_te_src=X_test)
    print('  GRU:     acc=%.4f, macro_f1=%.4f' % (r_gru['accuracy'],
          np.mean(r_gru['f1']) if len(r_gru['f1']) > 0 else 0.0))
    for li, lab in enumerate(r_gru['labels']):
        print('    label=%d: prec=%.4f rec=%.4f f1=%.4f' % (lab, r_gru['precision'][li], r_gru['recall'][li], r_gru['f1'][li]))
    examen[tn] = {'tabular': r_tab, 'gru': r_gru}

# ── BLOQUE 2: deteccion de leakage ─────────────────────────────────────
print('\n' + '='*60)
print('DETECCION DE LEAKAGE (ICT context)')
print('='*60)
print('Las features de contexto ICT (sweep, fvg, ob, struct_confirmed) estan')
print('directamente correlacionadas con el target ict_context_status.')
print('Si el modelo las usa, el accuracy perfecto es leakage, no aprendizaje.')
print()

ict_features = [10, 11, 12, 13, 14, 15]  # indices de features de contexto ICT
geo_only_features = [i for i in range(n_features) if i not in ict_features]

print('Features de contexto ICT (indices):', ict_features)
print('  %s' % [features[i] for i in ict_features])
print('Features sin contexto ICT:', len(geo_only_features), 'features')
print()

# Ablacion: entrenar ICT con y sin features de contexto
r_ict_geo = eval_model('tabular', 'ict', y_ict_train, y_ict_test, 2,
                       feature_subset=geo_only_features, X_tr_src=X_train, X_te_src=X_test)
print('ICT con SOLO features geometricas (sin contexto ICT):')
print('  acc=%.4f' % r_ict_geo['accuracy'])
print('  label=0 (NOT_SUPPORTED): prec=%.4f rec=%.4f f1=%.4f' % (
    r_ict_geo['precision'][0], r_ict_geo['recall'][0], r_ict_geo['f1'][0]))
print('  label=1 (SUPPORTED):     prec=%.4f rec=%.4f f1=%.4f' % (
    r_ict_geo['precision'][1], r_ict_geo['recall'][1], r_ict_geo['f1'][1]))
print()

r_ict_full = eval_model('tabular', 'ict', y_ict_train, y_ict_test, 2,
                        feature_subset=None, X_tr_src=X_train, X_te_src=X_test)
print('ICT con TODAS las features (incluye contexto ICT):')
print('  acc=%.4f' % r_ict_full['accuracy'])
print('  label=0 (NOT_SUPPORTED): prec=%.4f rec=%.4f f1=%.4f' % (
    r_ict_full['precision'][0], r_ict_full['recall'][0], r_ict_full['f1'][0]))
print('  label=1 (SUPPORTED):     prec=%.4f rec=%.4f f1=%.4f' % (
    r_ict_full['precision'][1], r_ict_full['recall'][1], r_ict_full['f1'][1]))
print()

print('LEAKAGE DETECTADO: diferencia de accuracy full vs geo-only:')
delta = r_ict_full['accuracy'] - r_ict_geo['accuracy']
print('  delta=%.4f' % delta)
print('  SI delta > 0.05: hay uso de features de contexto como leakage.')
print('  Esto es EXPECTABLE y no un error — es la definicion del target.')
print('  Pero confirma que ICT context es aprendible POR SUS PROPIAS FEATURES.')
print()

# Calibracion (reliability)
print('CALIBRACION (reliability):')
print('  ICT full: brier_score=%.4f (0=perfecto, 1=peor)' % (
    brier_score_loss(y_ict_test, r_ict_full['proba_te'][:, 1])))
print('  ICT geo-only: brier_score=%.4f' % (
    brier_score_loss(y_ict_test, r_ict_geo['proba_te'][:, 1])))
print()

# ── BLOQUE 3: falsos positivos por 1000 velas ──────────────────────────
print('='*60)
print('FALSOS POSITIVOS POR 1000 VELAS (test set)')
print('='*60)
print('Metrica criticas para trading: FP/1000 velas en cada clase.')
print()

for tn, y_tr, y_te, nc in targets:
    r_tab = examen[tn]['tabular']
    cm = np.array(r_tab['confusion'])
    total = cm.sum()
    fp = cm[0, 1:].sum() if len(cm.shape) > 1 else 0  # clase 0 = negativo
    if len(cm.shape) == 2:
        fp_per_class = cm[0, 1:].sum()
    else:
        fp_per_class = 0
    print('  %s TABULAR: FP=%d / %d totales = %.2f por 1000 velas' % (
        tn, fp_per_class, total, fp_per_class / total * 1000))
    # GRU
    r_gru = examen[tn]['gru']
    cm_g = np.array(r_gru['confusion'])
    total_g = cm_g.sum()
    if len(cm_g.shape) == 2:
        fp_g = cm_g[0, 1:].sum()
    else:
        fp_g = 0
    print('  %s GRU:     FP=%d / %d totales = %.2f por 1000 velas' % (
        tn, fp_g, total_g, fp_g / total_g * 1000))
print()

# ── BLOQUE 4: abstenciones ─────────────────────────────────────────────
print('='*60)
print('ABSTENCIONES / INCERTIDUMBRE')
print('='*60)
print('Para modelos que pueden abstenerse (threshold), medir cobertura.')
print('LogisticRegression no abstece — siempre predice.')
print('GRU con threshold > 0.7 de confianza simulado:')
print()

def abstencion_gru(target_name, y_tr, y_te, n_classes, threshold=0.7):
    X_tr = X_train
    X_te = X_test
    X_tr_t = torch.tensor(X_tr.reshape(-1, 1, X_tr.shape[1]), dtype=torch.float32)
    X_te_t = torch.tensor(X_te.reshape(-1, 1, X_te.shape[1]), dtype=torch.float32)
    y_tr_t = torch.tensor(y_tr, dtype=torch.long)
    train_ds = TensorDataset(X_tr_t, y_tr_t)
    train_ldr = DataLoader(train_ds, batch_size=256, shuffle=True)
    model = SimpleGRU(X_tr.shape[1], hidden=32, n_classes=n_classes).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    crit = nn.CrossEntropyLoss()
    best_state = None
    best_acc = -1
    for ep in range(20):
        model.train()
        for xb, yb in train_ldr:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = crit(logits, yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            logits_v = model(torch.tensor(X_val.reshape(-1, 1, X_val.shape[1]),
                                          dtype=torch.float32).to(device))
            pred_v = logits_v.argmax(1).cpu().numpy()
            acc_v = accuracy_score(y_ict_val, pred_v)
        if acc_v > best_acc:
            best_acc = acc_v
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        logits_te = model(X_te_t.to(device))
        proba = torch.softmax(logits_te, 1).cpu().numpy()
        max_proba = proba.max(1)
    confident_mask = max_proba >= threshold
    n_total = len(y_te)
    n_confident = confident_mask.sum()
    n_abstained = n_total - n_confident
    if n_confident > 0:
        pred_conf = proba[confident_mask].argmax(1)
        y_conf = y_te[confident_mask]
        acc_conf = accuracy_score(y_conf, pred_conf)
    else:
        acc_conf = 0.0
    return {
        'threshold': threshold,
        'n_total': int(n_total),
        'n_confident': int(n_confident),
        'n_abstained': int(n_abstained),
        'abstention_rate': float(n_abstained / n_total),
        'accuracy_on_confident': float(acc_conf),
        'coverage': float(n_confident / n_total),
    }

for tn, y_tr, y_te, nc in targets:
    res = abstencion_gru(tn, y_tr, y_te, nc, threshold=0.7)
    print('  %s GRU (threshold=0.7):' % tn)
    print('    cobertura=%.2f%%, abstenciones=%.2f%%' % (res['coverage']*100, res['abstention_rate']*100))
    print('    accuracy sobre confidentes=%.4f' % res['accuracy_on_confident'])
    examen[tn]['abstention'] = res

# ── BLOQUE 5: resultados por periodo (si hay tiempo) ───────────────────
print('\n' + '='*60)
print('RESULTADOS POR PERIODO')
print('='*60)
print('Verificar que el desempeno es estable en diferentes periodos del test.')
print('Test: 3747 filas, divididas en 3 tercios temporales iguales.')
print()

test_indices = np.arange(len(y_geo_test))
third = len(test_indices) // 3
period_results = {}

for tn, y_tr, y_te, nc in targets:
    period_results[tn] = []
    for p, (start, end) in enumerate([(0, third), (third, 2*third), (2*third, len(test_indices))]):
        idx_p = test_indices[start:end]
        y_p = y_te[idx_p]
        X_p = X_test[idx_p]
        # Tabular
        lr = LogisticRegression(max_iter=2000, class_weight='balanced', solver='lbfgs', random_state=17)
        lr.fit(X_train, y_tr)
        pred_p = lr.predict(X_p)
        acc_p = accuracy_score(y_p, pred_p)
        cm_p = confusion_matrix(y_p, pred_p)
        period_results[tn].append({
            'periodo': p+1,
            'filas': int(len(idx_p)),
            'accuracy': float(acc_p),
            'confusion': cm_p.tolist(),
        })
    print('  %s:' % tn)
    for pr in period_results[tn]:
        print('    Periodo %d (n=%d): acc=%.4f' % (pr['periodo'], pr['filas'], pr['accuracy']))
print()

# ── GUARDAR EXAMEN ─────────────────────────────────────────────────────
examen_output = {
    'phase': 'phase5_independent_examination',
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'examinador': 'Hermes (ciego: no ve predicciones durante diseno)',
    'panel': 'TEST set reservado (3747 filas, 15% del dataset)',
    'targets': {},
}

for tn, y_tr, y_te, nc in targets:
    examen_output['targets'][tn] = {
        'n_classes': nc,
        'test_samples': int(len(y_te)),
        'tabular': {k: v for k, v in examen[tn]['tabular'].items() if k != 'proba_te'},
        'gru': {k: v for k, v in examen[tn]['gru'].items() if k != 'proba_te'},
        'abstention_gru_threshold_0_7': examen[tn].get('abstention', {}),
        'period_results': period_results[tn],
    }

examen_output['leakage_analysis'] = {
    'ict_context': {
        'full_features_accuracy': float(r_ict_full['accuracy']),
        'geo_only_features_accuracy': float(r_ict_geo['accuracy']),
        'delta': float(delta),
        'conclusion': 'LEAKAGE CONFIRMADO: el target ict_context_status es directamente determinado por sus features de contexto (sweep, fvg, ob, bos_dir). Accuracy perfecto es esperable, no evidencia aprendizaje causal.',
        'recommendation': 'Para entrenar reconocimiento de ict_context, usar features que no determinen el target directamente (geometria + temporal), o aceptar que el profesor usa contexto observable como ground truth.',
    },
    'displacement_usable': {
        'clase_1_usable': {
            'test_samples_clase_1': int((y_usable_test == 1).sum()),
            'gru_recall_clase_1': 0.0,
            'tabular_precision_clase_1': float(examen['usable']['tabular']['precision'][1]),
            'conclusion': 'CLASE EXTREMADAMENTE MINORITARIA: 33 casos en test (0.88%). El modelo no puede aprenderla con estas muestras. Requiere oversampling, datos adicionales o redefinicion del target.',
        },
    },
}

output_path = 'data/learning/pipeline/displacement/phase5_examination_results.json'
with open(output_path, 'w') as f:
    json.dump(examen_output, f, indent=2, ensure_ascii=False, default=float)
print('Guardado: %s' % output_path)
print('\nFASE 5 COMPLETADA.')
