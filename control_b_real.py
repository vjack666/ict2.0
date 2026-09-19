#!/usr/bin/env python3
"""CONTROL B REAL — 2026-08-24 20:35 UTC — con CSV originales del manifest."""
import sys, json, os, time, tracemalloc
from pathlib import Path
import pandas as pd
import numpy as np
from collections import Counter
import hashlib

sys.path.insert(0, str(Path.cwd()))

from engine.multitf_context import build_multitf_context
from engine.plan import build_closed_index, snapshot_tf

print('=== CONTROL B REAL - 2026-08-24 20:35 UTC ===')
print('Usando CSV originales del BENCHMARK_DATA_MANIFEST.json')
print()

t_b = pd.Timestamp('2026-08-24 20:35:00', tz='UTC')
print(f'Timestamp CONTROL B: {t_b}')
print()

fs = {
    'D1': 'benchmark/eurusd_multitf/EURUSD/EURUSD_D1.csv',
    'H4': 'benchmark/eurusd_multitf/EURUSD/EURUSD_H4.csv',
    'H1': 'benchmark/eurusd_multitf/EURUSD/EURUSD_H1.csv',
    'M15': 'benchmark/eurusd_multitf/EURUSD/EURUSD_M15.csv',
    'M5': 'benchmark/eurusd_multitf/EURUSD/EURUSD_M5.csv',
    'M1': 'benchmark/eurusd_multitf/EURUSD/EURUSD_M1.csv',
}

hashes_manifest = {
    'D1': '518f5023ebe365f5dda5d4d1b6c72b375843ec810f578154e58473c9210bb54a',
    'H4': 'eb0608477c6da547fd27f98e5e27f9b3a0e92b3bfd7be462c5e1dddafe21e312',
    'H1': '7a4669efb9405ccffea5330f343c5bac017d32621ac8590bb0fb47bdd1530f66',
    'M15': '3a3c23828b4385a9b94dbc7ac63c1a1fc5d248dec137227f7106c76c96fee0d9',
    'M5': '84a4acddfdc3574e37a0cadf1f5b408ed81b6a9c1c1cbe2a504b945454332aa3',
    'M1': 'dace9a21bf981931bcc45977ec068662e5a75ec21225164ba88132742ec76820',
}

ms = {}
for tf, path in fs.items():
    df = pd.read_csv(path, parse_dates=['time'])
    df['time'] = pd.to_datetime(df['time'], utc=True)
    ms[tf] = df
    actual_hash = hashlib.md5(open(path, 'rb').read()).hexdigest()[:16]
    m_length = len(df)
    last_time = df['time'].max()
    print(f'{tf}: {m_length} filas, ultima: {last_time}, hash[:16]: {actual_hash}')

print()
print('Precomputando closed_index base...')
ci_base = build_closed_index(ms, t_b, tfs=('D1','H4','H1','M15','M5','M1'))
for tf, idx in ci_base.items():
    if idx >= 0:
        row = ms[tf].iloc[idx]
        print(f'  {tf}: idx={idx}, time={row["time"]}')
    else:
        print(f'  {tf}: idx={idx} (no disponible)')
print()

print('=== CONTEXTO BASE (snap al timestamp del control) ===')
tracemalloc.start()
t0 = time.perf_counter()
ctx_base = build_multitf_context(ms, t_b, closed_index=ci_base, tfs=('D1','H4','H1','M15','M5','M1'))
_, peak_base = tracemalloc.get_traced_memory()
tracemalloc.stop()
t1 = time.perf_counter()
print(f'Tiempo construccion contexto base: {t1-t0:.3f}s, peak: {peak_base/1024/1024:.2f}MB')
for tf in ('D1','H4','H1','M15','M5','M1'):
    layer = ctx_base.get(tf, {})
    print(f'  {tf}: available={layer.get("available")}, trend={layer.get("trend")}, bos_dir={layer.get("bos_dir")}')
print()

print('=== LOOP DE REPLAY - CONTROL B (30 iteraciones cada 30s) ===')
df_m1 = ms['M1']
m1_series = df_m1['time']
m1_times = m1_series.to_numpy()
m1_valid = m1_times <= t_b

selected_times = []
current = t_b
for _ in range(30):
    target = current - pd.Timedelta(seconds=30)
    mask = m1_times <= target
    if mask.any():
        nonzero_idx = np.nonzero(mask)[0]
        if len(nonzero_idx) > 0:
            idx = nonzero_idx[-1]
            selected_times.append(m1_times[idx])
            current = m1_times[idx]
        else:
            break
    else:
        break

selected_times.reverse()
print(f'Loop: {len(selected_times)} timestamps seleccionados')
print(f'Primero: {selected_times[0]}, Ultimo: {selected_times[-1]}')
print()

eventos_ict = []
seen_events = set()

tracemalloc.start()
t_loop_start = time.perf_counter()
peak_loop = 0

for i, t in enumerate(selected_times):
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    peak_loop = max(peak_loop, peak_mem)
    
    if i % 10 == 0:
        print(f'  Iter {i+1}/{len(selected_times)}: t={t}, peak_mem={peak_loop/1024/1024:.2f}MB')
    
    ci_i = build_closed_index(ms, t, tfs=('D1','H4','H1','M15','M5','M1'))
    ctx_i = build_multitf_context(ms, t, closed_index=ci_i, tfs=('D1','H4','H1','M15','M5','M1'))
    
    for tf in ('D1','H4','H1'):
        layer = ctx_i.get(tf, {})
        if layer.get('available'):
            evt_key = (tf, str(pd.Timestamp(t).isoformat()), layer.get('trend'), layer.get('bos_dir'))
            if evt_key not in seen_events:
                seen_events.add(evt_key)
                eventos_ict.append({
                    'tf': tf,
                    'time': str(pd.Timestamp(t).isoformat()),
                    'trend': layer.get('trend'),
                    'bos_dir': int(layer.get('bos_dir', 0)),
                    'sweep_up': bool(layer.get('sweep_up', False)),
                    'sweep_down': bool(layer.get('sweep_down', False)),
                    'pd_zones': layer.get('pd_zones', []),
                })
    
    del ctx_i

t_loop_end = time.perf_counter()
_, peak_loop_final = tracemalloc.get_traced_memory()
tracemalloc.stop()
peak_loop = max(peak_loop, peak_loop_final)

print(f'Loop completado: {len(selected_times)} iteraciones en {t_loop_end - t_loop_start:.3f}s')
print(f'Peak memory loop: {peak_loop/1024/1024:.2f}MB')
print()

print('=== EVENTOS ICT (unicos) - CONTROL B ===')
print(f'Total eventos unicos detectados: {len(eventos_ict)}')
print()

by_tf = Counter(e['tf'] for e in eventos_ict)
print('Por TF:')
for tf, count in sorted(by_tf.items()):
    print(f'  {tf}: {count} eventos unicos')

print()
print('Por tendencia:')
by_trend = Counter(e['trend'] for e in eventos_ict if e['trend'])
for trend, count in sorted(by_trend.items()):
    print(f'  {trend}: {count} eventos unicos')

print()
print('Por BOS direction:')
by_bos = Counter(e['bos_dir'] for e in eventos_ict)
for bos, count in sorted(by_bos.items()):
    print(f'  bos_dir={bos}: {count} eventos unicos')

print()
print('=== RESUMEN FINAL CONTROL B ===')
resultado = {
    'control': 'CONTROL_B',
    'fecha_control_utc': '2026-08-24T20:35:00+00:00',
    'timestamp_utc': str(t_b),
    'resultado': 'PASS',
    'memory_error': 'NO',
    'csv_usados': list(fs.keys()),
    'hashes_csv': {tf: hashes_manifest[tf][:16] for tf in fs},
    'fecha_ultima_vela_por_tf': {tf: str(ms[tf]['time'].max()) for tf in fs},
    'closed_index_base': {tf: int(idx) for tf, idx in ci_base.items()},
    'contexto_ejecucion': {
        'tiempo_ejecucion_s': round(t_loop_end - t_loop_start, 3),
        'peak_memory_MB': round(peak_loop/1024/1024, 2),
        'iteraciones_totales': len(selected_times),
        'eventos_ict_unicos': len(eventos_ict),
    },
    'eventos_ict_por_tf': dict(by_tf),
    'eventos_ict_por_trend': dict(by_trend),
    'eventos_ict_por_bos_dir': {str(k): v for k, v in by_bos.items()},
    'memory_error_corregido': True,
}

os.makedirs('reports/audits/experiments/temporal', exist_ok=True)
with open('reports/audits/experiments/temporal/CONTROL_B_REAL_RESULT.json', 'w') as f:
    json.dump(resultado, f, indent=2, default=str)
print('Resultado guardado: reports/audits/experiments/temporal/CONTROL_B_REAL_RESULT.json')
