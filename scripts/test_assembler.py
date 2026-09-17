"""Tests sintéticos del ensamblador M15 — incluyen H4 para que pasen realmente."""
import sys
from pathlib import Path

# Configuración de path
ROOT = Path(__file__).resolve().parent.parent
DETECTORS_ROOT = ROOT / 'detectors'

if str(DETECTORS_ROOT) not in sys.path:
    sys.path.insert(0, str(DETECTORS_ROOT))
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from engine.m15_evidence_assembler import build_m15_evidence_for_decision_time, M15EvidenceAssembler

# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Escenario básico con velas aleatorias pero con H4 válido
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('TEST 1: Escenario básico con velas aleatorias + H4 válido')
print('='*60)
print()

np.random.seed(42)
n_bars = 200
times_m15 = pd.date_range('2024-03-15 00:00', periods=n_bars, freq='15min', tz='UTC')
times_h4 = pd.date_range('2024-03-14 00:00', periods=20, freq='4h', tz='UTC')

# M15 sintéticos
prices_m15 = 1.0850 + np.cumsum(np.random.uniform(-0.0003, 0.0003, n_bars))
opens_m15 = prices_m15 + np.random.uniform(-0.0002, 0.0002, n_bars)
closes_m15 = opens_m15 + np.random.uniform(-0.0005, 0.0005, n_bars)
highs_m15 = np.maximum(opens_m15, closes_m15) + np.random.uniform(0, 0.0002, n_bars)
lows_m15 = np.minimum(opens_m15, closes_m15) - np.random.uniform(0, 0.0002, n_bars)

m15_df = pd.DataFrame({
    'time': times_m15,
    'open': opens_m15,
    'high': highs_m15,
    'low': lows_m15,
    'close': closes_m15,
})

# H4 sintéticos
prices_h4 = 1.0800 + np.cumsum(np.random.uniform(-0.0005, 0.0005, 20))
opens_h4 = prices_h4 + np.random.uniform(-0.0003, 0.0003, 20)
closes_h4 = opens_h4 + np.random.uniform(-0.0008, 0.0008, 20)
highs_h4 = np.maximum(opens_h4, closes_h4) + np.random.uniform(0, 0.0003, 20)
lows_h4 = np.minimum(opens_h4, closes_h4) - np.random.uniform(0, 0.0003, 20)

h4_df = pd.DataFrame({
    'timestamp': times_h4,
    'open': opens_h4,
    'high': highs_h4,
    'low': lows_h4,
    'close': closes_h4,
})

print(f'M15: {len(m15_df)} velas')
print(f'  Tiempo: {m15_df["time"].min()} -> {m15_df["time"].max()}')
print(f'H4: {len(h4_df)} velas')
print(f'  Tiempo: {h4_df["timestamp"].min()} -> {h4_df["timestamp"].max()}')
print()

decision_time = m15_df['time'].iloc[-1]
print(f'Decision time: {decision_time}')
print()

evidence = build_m15_evidence_for_decision_time(
    m15_frame=m15_df,
    h4_frame=h4_df,
    decision_time=decision_time,
    symbol='EURUSD',
)

for key in ['sweep', 'displacement', 'bos_or_choch', 'fvg_or_ob', 'retest']:
    print(f'  {key}: {evidence[key]}')

print()
print('✔ Test 1 completado sin errores')
print()

# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Estructura de respuesta correcta
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('TEST 2: Estructura de respuesta correcta')
print('='*60)
print()

expected_keys = ['sweep', 'displacement', 'bos_or_choch', 'fvg_or_ob', 'retest']
for key in expected_keys:
    assert key in evidence, f'Falta clave: {key}'
    assert 'present' in evidence[key], f'Falta present en {key}'
    assert 'time' in evidence[key], f'Falta time en {key}'
    assert 'source' in evidence[key], f'Falta source en {key}'
    if evidence[key]['present']:
        assert evidence[key]['time'] is not None, f'Time None cuando present=True en {key}'

print('✔ Todos los campos esperados presentes con estructura correcta')
print()

# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Determinismo — dos llamadas con mismo input dan mismo resultado
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('TEST 3: Determinismo')
print('='*60)
print()

evidence2 = build_m15_evidence_for_decision_time(
    m15_frame=m15_df,
    h4_frame=h4_df,
    decision_time=decision_time,
    symbol='EURUSD',
)

for key in expected_keys:
    assert evidence[key] == evidence2[key], f'Divergencia en {key}: {evidence[key]} != {evidence2[key]}'

print('✔ Determinismo verificado (dos ejecuciones con mismo input = mismo resultado)')
print()

# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Clase M15EvidenceAssembler
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('TEST 4: Clase M15EvidenceAssembler')
print('='*60)
print()

assembler = M15EvidenceAssembler(symbol='EURUSD')
ev_cls = assembler.build(m15_df, h4_df, decision_time=decision_time)

assert isinstance(ev_cls, dict), 'Debe retornar dict'
for key in expected_keys:
    assert key in ev_cls, f'Falta clave en resultado de clase: {key}'
    assert 'present' in ev_cls[key], f'Falta present en {key}'

print('✔ Clase M15EvidenceAssembler funciona correctamente')
print()

# ─────────────────────────────────────────────────────────────────────────────
# Test 5: No modifica los inputs
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('Test 5: No modifica los inputs')
print('='*60)
print()

m15_original = m15_df.copy()
h4_original = h4_df.copy()

_ = build_m15_evidence_for_decision_time(m15_df, h4_df, decision_time, 'EURUSD')

assert m15_df.equals(m15_original), 'No debe modificar el dataframe de entrada M15'
assert h4_df.equals(h4_original), 'No debe modificar el dataframe de entrada H4'

print('✔ No modifica los dataframes de entrada (M15 ni H4)')
print()

# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Timestamp timezone-aware vs naive
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('Test 6: Compatibilidad con timestamps timezone-aware')
print('='*60)
print()

# DataFrame timezone-aware
m15_tz = m15_df.copy()
m15_tz['time'] = pd.to_datetime(m15_tz['time'], utc=True)
h4_tz = h4_df.copy()
h4_tz['timestamp'] = pd.to_datetime(h4_tz['timestamp'], utc=True)
dt_tz = m15_tz['time'].iloc[-1]

ev_tz = build_m15_evidence_for_decision_time(m15_tz, h4_tz, dt_tz, 'EURUSD')

assert ev_tz['sweep']['time'] is not None, 'sweep.time debe ser no None'
# Evitar crash con naive en data timezone-aware
print(f'  sweep.time (tz-aware): {ev_tz["sweep"]["time"]}')
print(f'  displacement.time (tz-aware): {ev_tz["displacement"]["time"]}')
print()
print('✔ Compatibilidad con timestamps timezone-aware verificada')
print()

# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Decision_time fuera del rango (no debería causar error)
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('Test 7: Decision_time fuera del rango de datos')
print('='*60)
print()

dt_future = pd.Timestamp('2025-12-31 23:59:59', tz='UTC')
m15_future = pd.DataFrame({
    'time': pd.date_range('2024-01-01', periods=10, freq='15min', tz='UTC'),
    'open': [1.0]*10,
    'high': [1.001]*10,
    'low': [0.999]*10,
    'close': [1.0]*10,
})

h4_future = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=5, freq='4h', tz='UTC'),
    'open': [1.0]*5,
    'high': [1.001]*5,
    'low': [0.999]*5,
    'close': [1.0]*5,
})

ev_future = build_m15_evidence_for_decision_time(m15_future, h4_future, dt_future, 'EURUSD')
print(f'  sweep.time: {ev_future["sweep"]["time"]}')
print(f'  displacement.time: {ev_future["displacement"]["time"]}')
print('✔ Funciona con decision_time fuera del rango (no crashea)')
print()

# ─────────────────────────────────────────────────────────────────────────────
# Sumario
# ─────────────────────────────────────────────────────────────────────────────
print('='*60)
print('RESUMEN TESTS SINTÉTICOS')
print('='*60)
print()
print('  ✔ Test 1: Escenario básico (M15 + H4)')
print('  ✔ Test 2: Estructura de respuesta correcta')
print('  ✔ Test 3: Determinismo')
print('  ✔ Test 4: Clase M15EvidenceAssembler')
print('  ✔ Test 5: No modifica los inputs')
print('  ✔ Test 6: Compatibilidad con timestamps timezone-aware')
print('  ✔ Test 7: Funciona con decision_time fuera del rango')
print()
print('='*60)
print('OBJETIVO 3: VALIDACIÓN SINTÉTICA — COMPLETADO')
print('='*60)
