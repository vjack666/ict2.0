import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from pathlib import Path
from runtime.ai_learning.displacement_teacher import (
    DisplacementTeacher, DisplacementTeacherConfig,
    GeometricStrength, Direction, IctContextStatus
)

raw = Path('data/raw/EURUSD')
df5 = pd.read_parquet(raw / 'EURUSD_M5.parquet')
sample_idx = np.linspace(0, len(df5)-1, 50000, dtype=int)
df = df5.iloc[sample_idx].reset_index(drop=True)

# Alinear columnas y tipos para el profesor
for c in ['open','high','low','close']:
    df[c] = df[c].astype(float)
if hasattr(df['time'].iloc[0], 'timestamp'):
    df['time'] = df['time'].apply(lambda t: int(t.timestamp()) if pd.notna(t) else 0)

teacher = DisplacementTeacher(DisplacementTeacherConfig())

results = {'geometry': {}, 'direction': {}, 'episode': {}, 'ict_context': {}}
cross = {}

print("=" * 60)
print("PROFESOR 3-CAPAS SOBRE 50K VELAS EURUSD M5")
print("=" * 60)

for i in range(10, len(df)):
    p = teacher.evaluate(df, i)
    g = p.geometric_strength.name
    d = p.direction.name
    c = p.ict_context_status.name
    e = p.reasons.get('episode_status', 'N/A')
    results['geometry'][g] = results['geometry'].get(g, 0) + 1
    results['direction'][d] = results['direction'].get(d, 0) + 1
    results['ict_context'][c] = results['ict_context'].get(c, 0) + 1
    results['episode'][e] = results['episode'].get(e, 0) + 1
    key = f"{g} x {d}"
    cross[key] = cross.get(key, 0) + 1

total = 50000 - 10
tmin = pd.Timestamp(df.time.min(), unit='s').date()
tmax = pd.Timestamp(df.time.max(), unit='s').date()
print(f"Rango: {tmin} -> {tmax}")
print()

print("--- DISTRIBUCIÓN GEOMÉTRICA ---")
for k, v in sorted(results['geometry'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print("\n--- DISTRIBUCIÓN DIRECCIÓN ---")
for k, v in sorted(results['direction'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print("\n--- DISTRIBUCIÓN CONTEXTO ICT ---")
for k, v in sorted(results['ict_context'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print("\n--- ESTADO DE EPISODIO ---")
for k, v in sorted(results['episode'].items(), key=lambda x: -x[1]):
    print(f"  {k}: {v} ({v/total*100:.2f}%)")

print("\n--- CRUCE GEOMETRÍA x DIRECCIÓN (desplazamiento según profesor) ---")
for k, v in sorted(cross.items(), key=lambda x: -x[1]):
    if v > 0:
        print(f"  {k}: {v} ({v/total*100:.2f}%)")

strong_up = cross.get('STRONG x UP', 0)
strong_dn = cross.get('STRONG x DOWN', 0)
weak_up = cross.get('WEAK x UP', 0)
weak_dn = cross.get('WEAK x DOWN', 0)
total_strong = strong_up + strong_dn
total_weak = weak_up + weak_dn

print("\n--- RESUMEN: QUÉ ES DESPLAZAMIENTO SEGÚN EL PROFESOR ---")
print(f"  STRONG (cuerpo>=60% rango + rompe estruct): {total_strong} ({total_strong/total*100:.2f}%)")
print(f"    UP={strong_up}  DOWN={strong_dn}")
print(f"  WEAK (cuerpo 50-60% rango): {total_weak} ({total_weak/total*100:.2f}%)")
print(f"    UP={weak_up}  DOWN={weak_dn}")
print(f"  TOTAL geometría positiva (WEAK+STRONG): {total_strong+total_weak} ({(total_strong+total_weak)/total*100:.2f}%)")
none_unkn = total - (total_strong + total_weak)
print(f"  NONE + UNKNOWN: {none_unkn} ({none_unkn/total*100:.2f}%)")
print(f"\n  NOTA: ict_context=UNKNOWN en todas las filas (sin sweep/FVG/OB real detectado en este script)")
print(f"  ctx UNKNOWN: {results['ict_context'].get('UNKNOWN',0)} ({results['ict_context'].get('UNKNOWN',0)/total*100:.2f}%)")
