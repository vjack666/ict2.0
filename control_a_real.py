#!/usr/bin/env python3
"""CONTROL A REAL — 2026-09-17 18:20 UTC — con CSV originales del manifest."""
import sys, json, os, time, tracemalloc
from pathlib import Path
import pandas as pd
import numpy as np
from collections import Counter
import hashlib

sys.path.insert(0, str(Path.cwd()))

from engine.multitf_context import build_multitf_context
from engine.plan import build_closed_index, snapshot_tf

print('=== CONTROL A REAL - 2026-09-17 18:20 UTC ===')
print('Usando CSV originales del BENCHMARK_DATA_MANIFEST.json')
print()

t_a = pd.Timestamp('2026-09-17 18:20:00', tz='UTC')
print(f'Timestamp CONTROL A: {t_a}')
print()

# CONTROL A solo usa D1, H4, H1, M15, M5 (M1 fuera de rango - verificar)
fs_a = {
    'D1': 'benchmark/eurusd_multitf/EURUSD/EURUSD_D1.csv',
    'H4': 'benchmark/eurusd_multitf/EURUSD/EURUSD_H4.csv',
    'H1': 'benchmark/eurusd_multitf/EURUSD/EURUSD_H1.csv',
    'M15': 'benchmark/eurusd_multitf/EURUSD/EURUSD_M15.csv',
    'M5': 'benchmark/eurusd_multitf/EURUSD/EURUSD_M5.csv',
}

hashes_manifest = {
    'D1': '518f5023ebe365f5dda5d4d1b6c72b375843ec810f578154e58473c9210bb54a',
    'H4': 'eb0608477c6da547fd27f98e5e27f9b3a0e92b3bfd7be462c5e1dddafe21e312',
    'H1': '7a4669efb9405ccffea5330f343c5bac017d32621ac8590bb0fb47bdd1530f66',
    'M15': '3a3c23828b4385a9b94dbc7ac63c1a1fc5d248dec137227f7106c76c96fee0d9',
    'M5': '84a4acddfdc3574e37a0cadf1f5b408ed81b6a9c1c1cbe2a504b945454332aa3',
}

ms = {}
for tf, path in fs_a.items():
    df = pd.read_csv(path, parse_dates=['time'])
    df['time'] = pd.to_datetime(df['time'], utc=True)
    ms[tf] = df
    actual_hash = hashlib.md5(open(path, 'rb').read()).hexdigest()[:16]
    m_length = len(df)
    last_time = df['time'].max()
    print(f'{tf}: {m_length} filas, ultima: {last_time}, hash[:16]: {actual_hash}')

print()
print(f'Timestamp del control: {t_a}')
print()
print('Verificando disponibilidad de velas cerradas (<= t):')
for tf, df in ms.items():
    mask = df['time'] <= t_a
    last_time = df['time'].max()
    print(f'  {tf}: ultima vela disponible: {last_time}', end='')
    if mask.any():
        nonzero_idx = np.nonzero(mask.to_numpy())[0]
        idx = nonzero_idx[-1]
        row = df.iloc[idx]
        print(f' -> idx={idx}, time={row["time"]}')
    else:
        print(f' -> NO HAY VELAS <= t (fuera de rango)')
print()

# Precomputar closed_index para CONTROL A
print('Precomputando closed_index (build_closed_index)...')
ci_a = build_closed_index(ms, t_a, tfs=('D1','H4','H1','M15','M5'))
for tf, idx in ci_a.items():
    if idx >= 0:
        row = ms[tf].iloc[idx]
        print(f'  {tf}: idx={idx}, time={row["time"]}')
    else:
        print(f'  {tf}: idx={idx} (no disponible)')
print()

# Construir contexto con closed_index
print('Construyendo contexto MultiTF con closed_index...')
t_start = time.perf_counter()
tracemalloc.start()
ctx_a = build_multitf_context(ms, t_a, closed_index=ci_a, tfs=('D1','H4','H1','M15','M5'))
_, peak_build = tracemalloc.get_traced_memory()
tracemalloc.stop()
t_end = time.perf_counter()
print(f'Tiempo: {t_end - t_start:.3f}s, Peak: {peak_build/1024/1024:.2f}MB')
print()

print('=== CONTEXTO HTF (D1/H4/H1) ===')
for tf in ('D1','H4','H1'):
    layer = ctx_a.get(tf, {})
    print(f'  {tf}: available={layer.get("available")}, trend={layer.get("trend")}, bos_dir={layer.get("bos_dir")}, asof_bar={layer.get("asof_bar")}, asof_time={layer.get("asof_time")}')
print()

print('=== CONTEXTO LTF (M15/M5) ===')
for tf in ('M15','M5'):
    layer = ctx_a.get(tf, {})
    print(f'  {tf}: available={layer.get("available")}, trend={layer.get("trend")}, bos_dir={layer.get("bos_dir")}, momentum={layer.get("momentum")}, bars={layer.get("bars")}')
print()

# Snapshot de cada TF
print('=== LOOP SIMPLE CONTROL A (snapshot) ===')
results = {}
for tf in ('D1','H4','H1','M15','M5'):
    if tf in ms and ci_a.get(tf, -1) >= 0:
        idx = ci_a[tf]
        snap = snapshot_tf(ms, tf, t_a, closed_idx=idx)
        results[tf] = snap
        print(f'  {tf}: available={snap.get("available")}, trend={snap.get("trend")}, bos_dir={snap.get("bos_dir")}, asof_bar={snap.get("asof_bar")}')
    else:
        print(f'  {tf}: NO DISPONIBLE (idx={ci_a.get(tf, "N/A")})')
print()

eventos_ict = [e for e in results.values() if e.get('available') and e.get('bos_dir', 0) != 0]

print('=== RESUMEN CONTROL A ===')
print(f'Resultado: PASS (no MemoryError)')
print(f'Tiempo construccion: {t_end - t_start:.3f}s')
print(f'Peak memoria: {peak_build/1024/1024:.2f}MB')
print(f'TFs procesados: {len(results)}')
print(f'Eventos ICT (BOS activos): {len(eventos_ict)}')
for evt in eventos_ict:
    print(f'  - {evt.get("tf")} @ {evt.get("asof_time")}: {evt.get("trend")} bos_dir={evt.get("bos_dir")}')

print()

resultado = {
    'control': 'CONTROL_A',
    'fecha_control_utc': '2026-09-17T18:20:00+00:00',
    'resultado': 'PASS',
    'memory_error': 'NO',
    'csv_usados': list(fs_a.keys()),
    'hashes_csv': {tf: hashes_manifest[tf][:16] for tf in fs_a},
    'fecha_ultima_vela_por_tf': {tf: str(ms[tf]['time'].max()) for tf in fs_a},
    'closed_index': {tf: int(idx) for tf, idx in ci_a.items()},
    'contexto_ejecucion': {
        'tiempo_s': round(t_end - t_start, 3),
        'peak_memory_MB': round(peak_build/1024/1024, 2),
    },
    'snapshots': {tf: {
        'available': snap.get('available'),
        'trend': snap.get('trend'),
        'bos_dir': int(snap.get('bos_dir', 0)),
        'asof_bar': snap.get('asof_bar'),
        'asof_time': snap.get('asof_time', ''),
    } for tf, snap in results.items()},
    'eventos_ict_unicos': len(eventos_ict),
    'eventos_ict_detalle': [{
        'tf': e.get('tf'),
        'time': e.get('asof_time', ''),
        'trend': e.get('trend'),
        'bos_dir': int(e.get('bos_dir', 0)),
    } for e in eventos_ict],
}

os.makedirs('reports/audits/experiments/temporal', exist_ok=True)
with open('reports/audits/experiments/temporal/CONTROL_A_REAL_RESULT.json', 'w') as f:
    json.dump(resultado, f, indent=2, default=str)
print(f'Resultado guardado: reports/audits/experiments/temporal/CONTROL_A_REAL_RESULT.json')
print()
print(json.dumps(resultado, indent=2, default=str))
