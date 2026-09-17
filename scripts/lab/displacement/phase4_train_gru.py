#!/usr/bin/env python3
"""Fase 4: entrenamiento GRU + tabular sobre representacion causal (compacto)."""
import sys, json, time
sys.path.insert(0, '.')

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, precision_recall_fscore_support

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
features = data['features']
n_features = data['n_features']

print('Cargado: X_train=%d, X_val=%d, X_test=%d, features=%d' % (len(X_train), len(X_val), len(X_test), n_features))

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('Device:', device)

# ── helper metrics ──────────────────────────────────────────────────────
def metrics(y_true, y_pred, labels=None):
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, labels=labels, average=None, zero_division=0)
    return acc, prec, rec, f1

# ── TABULAR BASELINE (logistic regression) ─────────────────────────────
print('\n' + '='*60)
print('TABULAR BASELINE (LogisticRegression, balanced)')
print('='*60)

tabular_results = {}

for target_name, y_tr, y_v, y_te in [
    ('geo', y_geo_train, y_geo_val, y_geo_test),
    ('dir', y_dir_train, y_dir_val, y_dir_test),
    ('ict', y_ict_train, y_ict_val, y_ict_test),
    ('usable', y_usable_train, y_usable_val, y_usable_test),
]:
    labels = sorted(set(list(y_tr) + list(y_v) + list(y_te)))
    lr = LogisticRegression(max_iter=2000, class_weight='balanced', solver='lbfgs', random_state=17)
    lr.fit(X_train, y_tr)
    y_pred_v = lr.predict(X_val)
    y_pred_t = lr.predict(X_test)
    acc_v, prec_v, rec_v, f1_v = metrics(y_v, y_pred_v, labels=labels)
    acc_t, prec_t, rec_t, f1_t = metrics(y_te, y_pred_t, labels=labels)
    tabular_results[target_name] = {
        'labels': labels,
        'acc_val': float(acc_v), 'acc_test': float(acc_t),
        'prec_val': prec_v.tolist(), 'prec_test': prec_t.tolist(),
        'rec_val': rec_v.tolist(), 'rec_test': rec_t.tolist(),
        'f1_val': f1_v.tolist(), 'f1_test': f1_t.tolist(),
    }
    print('\n[Tabular] %s:' % target_name)
    print('  Val  acc=%.4f, labels=%s' % (acc_v, labels))
    print('  Test acc=%.4f' % acc_t)
    for li, lab in enumerate(labels):
        print('    label=%d: prec=%.4f rec=%.4f f1=%.4f'
              % (lab, prec_t[li], rec_t[li], f1_t[li]))

# ── GRU TEMPORAL ────────────────────────────────────────────────────────
# Añadimos dimensi�n secuencial dummy (1 paso) + features como 텐서 형태.
# El modelo GRU recibe [batch, seq_len=1, features] y aprende interacción no-lineal.

class SimpleGRU(nn.Module):
    def __init__(self, n_features, hidden=32, n_classes=3, dropout=0.2):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, num_layers=1, batch_first=True, dropout=0)
        self.fc1 = nn.Linear(hidden, hidden)
        self.drop = nn.Dropout(dropout)
        self.out = nn.Linear(hidden, n_classes)
        self.relu = nn.ReLU()
    def forward(self, x):
        # x: [batch, seq_len=1, features]
        h, _ = self.gru(x)
        h = h[:, -1, :]  # último step
        h = self.drop(self.relu(self.fc1(h)))
        return self.out(h)

def train_gru(target_name, y_tr_int, y_te_int, n_classes, n_epochs=40, lr=1e-3, hidden=32, batch_size=256):
    y_tr = y_tr_int.astype(np.int64)
    y_te = y_te_int.astype(np.int64)
    X_tr_t = torch.tensor(X_train.reshape(-1, 1, n_features), dtype=torch.float32)
    X_val_t = torch.tensor(X_val.reshape(-1, 1, n_features), dtype=torch.float32)
    X_te_t = torch.tensor(X_test.reshape(-1, 1, n_features), dtype=torch.float32)
    y_tr_t = torch.tensor(y_tr, dtype=torch.long)
    y_val_t = torch.tensor(y_ict_val if target_name=='ict' else (y_geo_val if target_name=='geo' else (y_dir_val if target_name=='dir' else y_usable_val)), dtype=torch.long)
    y_te_t = torch.tensor(y_te, dtype=torch.long)

    train_ds = TensorDataset(X_tr_t, y_tr_t)
    train_ldr = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    model = SimpleGRU(n_features, hidden=hidden, n_classes=n_classes).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    crit = nn.CrossEntropyLoss()
    losses = []
    best_state = None
    best_acc = -1
    for ep in range(n_epochs):
        model.train()
        ep_loss = 0.0
        for xb, yb in train_ldr:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            logits = model(xb)
            loss = crit(logits, yb)
            loss.backward()
            opt.step()
            ep_loss += loss.item() * xb.size(0)
        losses.append(ep_loss / len(train_ds))
        # validación rápida
        model.eval()
        with torch.no_grad():
            logits_v = model(X_val_t.to(device))
            pred_v = logits_v.argmax(1).cpu().numpy()
            acc_v = accuracy_score(y_val_t.numpy(), pred_v)
        if acc_v > best_acc:
            best_acc = acc_v
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        if (ep+1) % 10 == 0 or ep == 0:
            print('  epoch %2d/%d loss=%.4f val_acc=%.4f best=%.4f'
                  % (ep+1, n_epochs, losses[-1], acc_v, best_acc))
    # cargar mejor
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        logits_te = model(X_te_t.to(device))
        pred_te = logits_te.argmax(1).cpu().numpy()
    labels = sorted(set(list(y_tr) + list(y_te)))
    acc_t, prec_t, rec_t, f1_t = metrics(y_te, pred_te, labels=labels)
    return {
        'acc_test': float(acc_t),
        'labels': labels,
        'prec_test': prec_t.tolist(),
        'rec_test': rec_t.tolist(),
        'f1_test': f1_t.tolist(),
        'best_val_acc': float(best_acc),
        'n_epochs_trained': n_epochs,
    }

print('\n' + '='*60)
print('GRU TEMPORAL (seq_len=1, hidden=32, 40 epochs, lr=1e-3)')
print('='*60)
gru_results = {}
for target_name, y_tr, y_te, n_classes in [
    ('geo', y_geo_train, y_geo_test, 3),
    ('dir', y_dir_train, y_dir_test, 3),
    ('ict', y_ict_train, y_ict_test, 2),
    ('usable', y_usable_train, y_usable_test, 2),
]:
    print('\n[Training GRU] target=%s (n_classes=%d)' % (target_name, n_classes))
    t0 = time.time()
    res = train_gru(target_name, y_tr, y_te, n_classes)
    dt = time.time() - t0
    gru_results[target_name] = res
    print('[GRU] %s: test_acc=%.4f, epochs=%d, time=%.1fs' % (target_name, res['acc_test'], res['n_epochs_trained'], dt))
    for li, lab in enumerate(res['labels']):
        print('  label=%d: prec=%.4f rec=%.4f f1=%.4f'
              % (lab, res['prec_test'][li], res['rec_test'][li], res['f1_test'][li]))

# ── RESUMEN COMPARATIVO ─────────────────────────────────────────────────
print('\n' + '='*60)
print('RESUMEN: TABULAR vs GRU')
print('='*60)
summary = {}
for tn in ['geo','dir','ict','usable']:
    tr = tabular_results[tn]
    gr = gru_results[tn]
    print('\n[%s]' % tn)
    print('  TABULAR test_acc=%.4f' % tr['acc_test'])
    print('  GRU    test_acc=%.4f (delta=%.4f)' % (gr['acc_test'], gr['acc_test']-tr['acc_test']))
    print('  Mejor muestra:')
    for li, lab in enumerate(tr['labels']):
        tab_f1 = tr['f1_test'][li]
        gru_f1 = gr['f1_test'][li] if li < len(gr['f1_test']) else -1
        mejor = 'TABULAR' if tab_f1 >= gru_f1 else 'GRU'
        print('    label=%d: TABULAR f1=%.4f | GRU f1=%.4f -> %s'
              % (lab, tab_f1, gru_f1, mejor))
    summary[tn] = {
        'tabular_acc_test': tr['acc_test'],
        'gru_acc_test': gr['acc_test'],
        'tabular_f1_test': tr['f1_test'],
        'gru_f1_test': gr['f1_test'],
        'mejor_modelo': 'tabular' if tr['acc_test'] >= gr['acc_test'] else 'gru',
    }

# ── Guardar resultados ──────────────────────────────────────────────────
results = {
    'phase': 'phase4_training',
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'device': str(device),
    'tabular_baseline': tabular_results,
    'gru_temporal': gru_results,
    'summary': summary,
    'config': {
        'n_features': n_features,
        'features': features,
        'train_samples': len(X_train),
        'val_samples': len(X_val),
        'test_samples': len(X_test),
        'gru_hidden': 32,
        'gru_epochs': 40,
        'gru_lr': 1e-3,
        'tabular_max_iter': 2000,
        'tabular_class_weight': 'balanced',
    },
}
out_path = 'data/learning/pipeline/displacement/phase4_training_results.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print('\nGuardado: %s' % out_path)
print('Fase 4 COMPLETADA.')
