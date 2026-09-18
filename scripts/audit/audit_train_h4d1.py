"""
ENTRENAMIENTO H4/D1 — GRU 15 timesteps con calibración ICT correcta
=====================================================================
Criterio B (calibrado): body_ratio > 0.60, wick < 0.20, FVG presente,
                          sweep 10 velas antes, BOS 14 velas después.
"""
import os, json, time, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

print('='*70)
print('ENTRENAMIENTO H4/D1 — GRU 15 timesteps (calibración ICT)')
print('='*70)
print(f'TF={tf.__version__} | GPUs={len(tf.config.list_physical_devices("GPU"))}')

BASE = Path(__file__).resolve().parent.parent / 'data' / 'raw' / 'EURUSD'  # data no copiado a CLEAN; requiere fuente externa
OUT = Path('reports/audits/experiments/displacement')
OUT.mkdir(parents=True, exist_ok=True)

W = 15; HALF = W // 2
EPOCHS = 30; BATCH_SIZE = 16

# ─── Calibración ────────────────────────────────────────────────────────────
# Criterio B (calibrado para H4/D1 según literatura ICT):
#   body_ratio > 0.60  (body ocupa >60% del rango total)
#   wick_ratio < 0.20  (wicks < 20% del rango total)
#   FVG presente       (high[N-1] < low[N+1] para bullish, inverso para bearish)
#   sweep: 10 velas antes (más contexto para H4/D1)
#   BOS:  14 velas después (más tiempo para H4/D1)
# ────────────────────────────────────────────────────────────────────────────

def build_dataset_h4d1(df, W=15, EPOCHS=30):
    """Construye dataset para H4/D1 con calibración corregida."""
    n = len(df)
    df = df.copy().reset_index(drop=True)

    # Features
    _h = df.high.values.astype(np.float64)
    _l = df.low.values.astype(np.float64)
    _o = df.open.values.astype(np.float64)
    _c = df.close.values.astype(np.float64)
    _body = np.abs(_c - _o)
    _range = _h - _l
    _rng = np.where(_range == 0, 1e-10, _range)
    _body_ratio = _body / _rng
    _wick_ratio = 1.0 - _body_ratio
    _avg_range = pd.Series(_range).rolling(14).mean().values

    # Swing (numpy)
    half = 5
    sh = np.full(n, np.nan); sl = np.full(n, np.nan)
    for i in range(half, n - half):
        if _h[i] == _h[i-half:i+half+1].max() and _h[i] > _h[i-half:i].max():
            sh[i] = _h[i]
        if _l[i] == _l[i-half:i+half+1].min() and _l[i] < _l[i-half:i].min():
            sl[i] = _l[i]
    ph = sh.copy(); pl = sl.copy()
    for i in range(1, n):
        if np.isnan(ph[i]): ph[i] = ph[i-1]
        if np.isnan(pl[i]): pl[i] = pl[i-1]
    _sweep_up = (_l < pl) & (~np.isnan(pl))
    _sweep_down = (_h > ph) & (~np.isnan(ph))
    _bos_up = (_c > ph) & (~np.isnan(ph))
    _bos_down = (_c < pl) & (~np.isnan(pl))

    # FVG corregido
    _fvg_bull = np.zeros(n, dtype=bool)
    _fvg_bear = np.zeros(n, dtype=bool)
    for i in range(1, n-1):
        if _h[i-1] < _l[i+1]: _fvg_bull[i] = True
        if _l[i-1] > _h[i+1]: _fvg_bear[i] = True
    _has_fvg = _fvg_bull | _fvg_bear

    # Displacement B (calibrado)
    _disp = (_body_ratio > 0.60) & (_wick_ratio < 0.20) & (~np.isnan(_body_ratio))
    # Ventana 3
    _disp_win = np.zeros(n, dtype=bool)
    for i in range(n):
        if np.any(_disp[max(0,i-2):i+1]):
            _disp_win[i] = True

    # Construir secuencias SWEEP→DISPLACEMENT→BOS
    seqs = []
    for i in range(15, n - 15):
        if not _disp_win[i]:
            continue
        # FVG: en la vela displacement o adyacente dentro de ventana
        fvg_ok = False
        for j in range(max(0, i-2), min(n, i+3)):
            if _has_fvg[j]:
                fvg_ok = True; break
        if not fvg_ok:
            continue
        # Sweep: 10 velas antes
        sf, soff = False, -1
        for off in range(1, 11):
            ci = i - off
            if ci < 0: break
            if _sweep_up[ci] or _sweep_down[ci]:
                sf, soff = True, off; break
        if not sf:
            continue
        # BOS: 14 velas después
        bf, boff = False, -1
        for off in range(1, 15):
            ci = i + off
            if ci >= n: break
            if _bos_up[ci] or _bos_down[ci]:
                bf, boff = True, off; break
        if not bf:
            continue
        sd = 1 if _sweep_up[i-soff] else -1
        dd = 1 if (_c[i] > _o[i]) else -1
        bd = 1 if _bos_up[i+boff] else -1
        if sd == dd == bd:
            seqs.append(i)

    print(f'  Secuencias encontradas (calibración B+FVG): {len(seqs)}')

    if len(seqs) < 30:
        print(f'  ⚠️ Pocas secuencias para entrenamiento significativo')
        return None

    # Construir features (misma arquitectura que M5/M15)
    features = []
    targets_has_disp = []
    targets_r1 = []
    targets_magnitude = []
    targets_efficiency = []
    targets_duration = []
    targets_mfe = []
    targets_mae = []

    for si, di in enumerate(seqs):
        start = di - HALF
        end = di + HALF
        if start < 0 or end >= n:
            continue
        wdf = df.iloc[start:end].reset_index(drop=True)

        feat = np.zeros((W, 26), dtype=np.float32)
        for j in range(W):
            if j >= len(wdf): break
            row = wdf.iloc[j]
            body = abs(row.close - row.open)
            cr = row.high - row.low
            feat[j,0] = body/cr if cr > 0 else 0.0
            feat[j,1] = body * 10000.0
            feat[j,2] = cr * 10000.0
            feat[j,3] = (row.high - max(row.open, row.close)) * 10000.0
            feat[j,4] = (min(row.open, row.close) - row.low) * 10000.0
            feat[j,5] = 1.0 - (body/cr if cr > 0 else 0.0) if cr > 0 else 0.0
            feat[j,6] = (row.close - row.open) * 10000.0
            pc = wdf.close.iloc[j-1] if j > 0 else row.close
            feat[j,7] = (row.close - pc) * 10000.0
            ar = _avg_range[si] if si < len(_avg_range) else 0.0
            feat[j,8] = ar * 10000.0 if not np.isnan(ar) else 0.0
            feat[j,9] = 1.0 if (not np.isnan(sh[si]) and row.high == sh[si]) else 0.0
            feat[j,10] = 1.0 if (not np.isnan(sl[si]) and row.low == sl[si]) else 0.0
            feat[j,11] = body/(ar+1e-10) if not np.isnan(ar) else 0.0
            sw = _sweep_up[si] if si < len(_sweep_up) else False
            feat[j,12] = 1.0 if sw else 0.0
            fvg = _has_fvg[si] if si < len(_has_fvg) else False
            feat[j,13] = 1.0 if fvg else 0.0
            feat[j,14] = 1.0 if (_bos_up[si] or _bos_down[si]) else 0.0

        features.append(feat)

        # Targets
        bos_idx = di + boff
        if bos_idx < n:
            r1_achieved = bool((_c[bos_idx] - _h[di]) * dd > 0) if dd > 0 else bool((_l[di] - _c[bos_idx]) * (-dd) > 0)
        else:
            r1_achieved = False

        targets_has_disp.append(1.0)
        targets_r1.append(1.0 if r1_achieved else 0.0)
        # Magnitude: rango de la vela de displacement
        targets_magnitude.append(_range[di] * 10000.0)
        # Efficiency: ratio de displacement sobre rango previo (simplificado)
        prev_range = np.mean(_range[max(0, si-5):si]) * 10000.0 if si > 0 else 1.0
        eff = _range[di] / (prev_range + 1e-10) if prev_range > 0 else 1.0
        targets_efficiency.append(float(_body_ratio[di] if di < len(_body_ratio) else 1.0))
        # Duration: pasos hasta BOS
        targets_duration.append(float(boff))
        # MFE/MAE: estimaciones relativas
        mfe_est = _range[di] * 10000.0 * 1.5
        mae_est = _range[di] * 10000.0 * 0.5
        targets_mfe.append(float(mfe_est))
        targets_mae.append(float(mae_est))

    X = np.array(features, dtype=np.float32)
    y_has_disp = np.array(targets_has_disp, dtype=np.float32).reshape(-1, 1)
    y_r1 = np.array(targets_r1, dtype=np.float32).reshape(-1, 1)
    y_mag = np.array(targets_magnitude, dtype=np.float32).reshape(-1, 1)
    y_eff = np.array(targets_efficiency, dtype=np.float32).reshape(-1, 1)
    y_dur = np.array(targets_duration, dtype=np.float32).reshape(-1, 1)
    y_mfe = np.array(targets_mfe, dtype=np.float32).reshape(-1, 1)
    y_mae = np.array(targets_mae, dtype=np.float32).reshape(-1, 1)

    print(f'  Dataset: X={X.shape}, y_has_disp={y_has_disp.shape}, y_r1={y_r1.shape}')
    print(f'  y_mag: min={y_mag.min():.1f} max={y_mag.max():.1f} mean={y_mag.mean():.1f}')
    print(f'  y_r1: {int(y_r1.sum())}/{len(y_r1)} ({100*y_r1.mean():.1f}%)')
    print(f'  y_eff: min={y_eff.min():.3f} max={y_eff.max():.3f} mean={y_eff.mean():.3f}')

    return {
        'X': X,
        'y_has_disp': y_has_disp,
        'y_r1': y_r1,
        'y_magnitude': y_mag,
        'y_efficiency': y_eff,
        'y_duration': y_dur,
        'y_mfe': y_mfe,
        'y_mae': y_mae,
        'n_sequences': len(seqs),
        'seq_indices': seqs,
        'df': df,
    }


# ─── Modelo ────────────────────────────────────────────────────────────────
def build_model(W=15):
    inp = keras.Input(shape=(W, 26))
    x = layers.GRU(64, return_sequences=False)(inp)
    x = layers.Dense(32, activation='relu')(x)

    out_has_disp = layers.Dense(1, activation='sigmoid', name='has_displacement')(x)
    out_r1 = layers.Dense(1, activation='sigmoid', name='r1_achieved')(x)
    out_mag = layers.Dense(1, activation='sigmoid', name='magnitude')(x)
    out_eff = layers.Dense(1, activation='sigmoid', name='efficiency')(x)
    out_dur = layers.Dense(1, activation='linear', name='duration')(x)
    out_mfe = layers.Dense(1, activation='sigmoid', name='mfe')(x)
    out_mae = layers.Dense(1, activation='sigmoid', name='mae')(x)

    model = keras.Model(inputs=inp, outputs=[
        out_has_disp, out_r1, out_mag, out_eff, out_dur, out_mfe, out_mae
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss={
            'has_displacement': 'binary_crossentropy',
            'r1_achieved': 'binary_crossentropy',
            'magnitude': 'mse',
            'efficiency': 'mse',
            'duration': 'mse',
            'mfe': 'mse',
            'mae': 'mse',
        },
        loss_weights={
            'has_displacement': 2.0,
            'r1_achieved': 2.0,
            'magnitude': 0.5,
            'efficiency': 0.5,
            'duration': 0.3,
            'mfe': 0.3,
            'mae': 0.3,
        },
    )
    return model


def train_and_evaluate(ds, name, OUT):
    """Entrena y evalúa el modelo para un timeframe."""
    np.random.seed(42)
    tf.random.set_seed(42)

    n = ds['X'].shape[0]
    n_train = int(n * 0.8)

    X_train = ds['X'][:n_train]
    X_test = ds['X'][n_train:]

    def split_y(key):
        return ds[key][:n_train], ds[key][n_train:]

    y_train = {k: split_y(k)[0] for k in ['y_has_disp','y_r1','y_magnitude','y_efficiency','y_duration','y_mfe','y_mae']}
    y_test = {k: split_y(k)[1] for k in ['y_has_disp','y_r1','y_magnitude','y_efficiency','y_duration','y_mfe','y_mae']}

    model = build_model(W)
    print(f'\n  Entrenando GRU para {name}...')

    history = model.fit(
        X_train,
        {
            'has_displacement': y_train['y_has_disp'],
            'r1_achieved': y_train['y_r1'],
            'magnitude': y_train['y_magnitude'],
            'efficiency': y_train['y_efficiency'],
            'duration': y_train['y_duration'],
            'mfe': y_train['y_mfe'],
            'mae': y_train['y_mae'],
        },
        validation_data=(
            X_test,
            {
                'has_displacement': y_test['y_has_disp'],
                'r1_achieved': y_test['y_r1'],
                'magnitude': y_test['y_magnitude'],
                'efficiency': y_test['y_efficiency'],
                'duration': y_test['y_duration'],
                'mfe': y_test['y_mfe'],
                'mae': y_test['y_mae'],
            }
        ),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        verbose=0,
    )

    # Predicciones
    pred = model.predict(X_test, verbose=0)
    pred_has_disp = pred[0].flatten()
    pred_r1 = pred[1].flatten()

    # Métricas
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

    # Discretizar predicciones
    pred_has_disp_bin = (pred_has_disp > 0.5).astype(int)
    pred_r1_bin = (pred_r1 > 0.5).astype(int)
    true_has_disp = y_test['y_has_disp'].flatten().astype(int)
    true_r1 = y_test['y_r1'].flatten().astype(int)

    # Evaluar has_displacement (siempre 1.0 en train — overfitting potencial)
    has_acc = accuracy_score(true_has_disp, pred_has_disp_bin)
    has_prec = precision_score(true_has_disp, pred_has_disp_bin, zero_division=0)
    has_rec = recall_score(true_has_disp, pred_has_disp_bin, zero_division=0)
    has_f1 = f1_score(true_has_disp, pred_has_disp_bin, zero_division=0)

    # Evaluar R1
    r1_acc = accuracy_score(true_r1, pred_r1_bin)
    r1_prec = precision_score(true_r1, pred_r1_bin, zero_division=0)
    r1_rec = recall_score(true_r1, pred_r1_bin, zero_division=0)
    r1_f1 = f1_score(true_r1, pred_r1_bin, zero_division=0)

    # Correlaciones de regresión
    mag_corr = np.corrcoef(y_test['y_magnitude'].flatten(), pred[2].flatten())[0,1]
    eff_corr = np.corrcoef(y_test['y_efficiency'].flatten(), pred[3].flatten())[0,1]
    dur_corr = np.corrcoef(y_test['y_duration'].flatten(), pred[4].flatten())[0,1]
    mfe_corr = np.corrcoef(y_test['y_mfe'].flatten(), pred[5].flatten())[0,1]
    mae_corr = np.corrcoef(y_test['y_mae'].flatten(), pred[6].flatten())[0,1]

    cm = confusion_matrix(true_r1, pred_r1_bin)

    print(f'\n  ── RESULTADOS {name} ───────────────────────────────────────────')
    print(f'  n_train={n_train}, n_test={n-n_train}, n_seqs={ds["n_sequences"]}')
    print(f'  has_displacement: acc={has_acc:.4f} prec={has_prec:.4f} rec={has_rec:.4f} F1={has_f1:.4f}')
    print(f'  r1_achieved:      acc={r1_acc:.4f} prec={r1_prec:.4f} rec={r1_rec:.4f} F1={r1_f1:.4f}')
    print(f'  Confusión R1:     TN={cm[0,0]} FP={cm[0,1]} FN={cm[1,0]} TP={cm[1,1]}')
    print(f'  Magnitud corr:    {mag_corr:.4f}')
    print(f'  Efficiency corr:  {eff_corr:.4f}')
    print(f'  Duration corr:    {dur_corr:.4f}')
    print(f'  MFE corr:         {mfe_corr:.4f}')
    print(f'  MAE corr:         {mae_corr:.4f}')

    result = {
        'timeframe': name,
        'n_sequences': ds['n_sequences'],
        'n_train': n_train,
        'n_test': n - n_train,
        'has_displacement_accuracy': float(has_acc),
        'has_displacement_precision': float(has_prec),
        'has_displacement_recall': float(has_rec),
        'has_displacement_f1': float(has_f1),
        'r1_accuracy': float(r1_acc),
        'r1_precision': float(r1_prec),
        'r1_recall': float(r1_rec),
        'r1_f1': float(r1_f1),
        'confusion_r1': cm.tolist(),
        'magnitude_corr': float(mag_corr) if not np.isnan(mag_corr) else None,
        'efficiency_corr': float(eff_corr) if not np.isnan(eff_corr) else None,
        'duration_corr': float(dur_corr) if not np.isnan(dur_corr) else None,
        'mfe_corr': float(mfe_corr) if not np.isnan(mfe_corr) else None,
        'mae_corr': float(mae_corr) if not np.isnan(mae_corr) else None,
        'calibration': 'B (body_ratio>0.60, wick<0.20, FVG, sweep10, BOS14)',
        'timestamp': pd.Timestamp.now().isoformat(),
    }

    with open(OUT / f'results_{name.lower()}.json', 'w') as f:
        json.dump(result, f, indent=2)

    model.save(OUT / f'model_gru_{name.lower()}.keras')
    print(f'\n  ✓ Modelo guardado: {OUT}/model_gru_{name.lower()}.keras')
    print(f'  ✓ Resultados guardados: {OUT}/results_{name.lower()}.json')

    return result


# ─── MAIN ────────────────────────────────────────────────────────────────────
all_results = {}

for name, fn in [('H4', 'EURUSD_H4.parquet'), ('D1', 'EURUSD_D1.parquet')]:
    print(f'\n{"="*70}')
    print(f'LOADING {name}: {fn}')
    print(f'{"="*70}')

    df = pd.read_parquet(BASE / fn)
    df['time'] = pd.to_datetime(df['time'], utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    print(f'  Filas: {len(df):,}')
    print(f'  Periodo: {df.time.min():%Y-%m-%d} → {df.time.max():%Y-%m-%d}')

    ds = build_dataset_h4d1(df, W, EPOCHS)
    if ds is None:
        print(f'  ⚠️ No hay secuencias suficientes para {name}')
        continue

    result = train_and_evaluate(ds, name, OUT)
    all_results[name] = result

# ─── COMPARACIÓN FINAL ─────────────────────────────────────────────────────
print('\n' + '='*70)
print('COMPARACIÓN: M5, M15 vs H4, D1 (calibración ICT correcta)')
print('='*70)
print(f'  {"TF":<6} {"Seqs":>6} {"HasDisp":>9} {"R1 F1":>8} {"Mag corr":>10} {"Eff corr":>10} {"MFE corr":>10}')
print(f'  {"-"*6} {"-"*6} {"-"*9} {"-"*8} {"-"*10} {"-"*10} {"-"*10}')

# Resultados previos (de auditoría anterior)
prev = {
    'M5':  {'n_sequences': 168, 'has_displacement_f1': 1.0, 'r1_f1': 1.0, 'magnitude_corr': -0.46, 'efficiency_corr': 0.33, 'mfe_corr': 0.38},
    'M15': {'n_sequences': 459, 'has_displacement_f1': 1.0, 'r1_f1': 0.9815, 'magnitude_corr': -0.68, 'efficiency_corr': 0.15, 'mfe_corr': 0.79},
}

for tf_name in ['M5', 'M15', 'H4', 'D1']:
    if tf_name in prev:
        d = prev[tf_name]
        print(f'  {tf_name:<6} {d["n_sequences"]:>6} {"—":>9} {d["r1_f1"]:>8.4f} {d["magnitude_corr"]:>10.4f} {d["efficiency_corr"]:>10.4f} {d["mfe_corr"]:>10.4f}')
    elif tf_name in all_results:
        d = all_results[tf_name]
        print(f'  {tf_name:<6} {d["n_sequences"]:>6} {d["has_displacement_f1"]:>9.4f} {d["r1_f1"]:>8.4f} {d["magnitude_corr"] or 0:>10.4f} {d["efficiency_corr"] or 0:>10.4f} {d["mfe_corr"] or 0:>10.4f}')

print('\n✓ Entrenamiento completado')
print(f'  Resultados guardados en: {OUT}/')

# Guardar resultados consolidados
consolidado = {
    'previo': prev,
    'calibracion_h4d1': all_results,
    'nota': 'H4/D1 usando criterio B (calibración ICT): body_ratio>0.60, wick<0.20, FVG presente',
    'fecha': pd.Timestamp.now().isoformat(),
}
with open(OUT / 'consolidado_h4d1.json', 'w') as f:
    json.dump(consolidado, f, indent=2)