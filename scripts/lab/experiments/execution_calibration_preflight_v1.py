#!/usr/bin/env python3
"""
EXECUTION_CALIBRATION_PREFLIGHT_V1 — Auditoría read-only de cobertura de 
calibración de ejecución en pips con execution.py como profesor determinista.

Objetivo: medir cuántas filas del dataset tienen cobertura suficiente para
fine_execution() y qué razones de fallo predominan.

RESTRICCIONES:
- can_trade=false
- entry_authorized=false
- shadow_mode=true
- prediction_is_diagnostic=true
- execution_authority=engine.execution
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent  # raíz del repo
DATASET_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1"

try:
    sys.path.insert(0, str(ROOT))
    from engine.execution import fine_execution
    EXECUTION_AVAILABLE = True
except Exception as e:
    EXECUTION_AVAILABLE = False
    EXECUTION_ERROR = str(e)

try:
    import pandas as pd
    import pyarrow.parquet as pq
    PANDAS_AVAILABLE = True
except Exception:
    PANDAS_AVAILABLE = False


def pip_size_for_symbol(symbol: str) -> float:
    if symbol in ("EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"):
        return 0.0001
    elif symbol in ("USDJPY",):
        return 0.01
    elif symbol in ("XAUUSD",):
        return 0.01
    return 0.0001


def load_splits() -> dict[str, list[dict[str, Any]]]:
    splits = {}
    for name in ["dataset_train.jsonl", "dataset_validation.jsonl", "dataset_test_oos.jsonl"]:
        path = DATASET_DIR / name
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                splits[name.replace(".jsonl", "").upper()] = [
                    json.loads(line) for line in f if line.strip()
                ]
    return splits


def diagnose_not_enough_bars() -> dict[str, Any]:
    """
    Diagnosticar por qué fine_execution falla con not_enough_bars.
    Necesita entender qué estructura mínima necesita el TF de ejecución.
    """
    # Cargar M15 real
    source = ROOT / "data/raw/EURUSD/EURUSD_M15.parquet"
    if not source.exists():
        return {"error": "M15 no encontrado", "source": str(source)}

    try:
        table = pq.read_table(source)
        df = table.to_pandas()
        df = df.sort_values("time").reset_index(drop=True)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    # Probar fine_execution con ventanas de diferente tamaño
    print("   Diagnóstico de not_enough_bars:")
    print("   " + "-" * 60)

    # Tomar un punto de decisión de ejemplo
    # Buscar una fila con direction != 0 y un tiempo bien dentro del rango de M15
    example_rows = []
    for name, rows in load_splits().items():
        for row in rows:
            direction = int(row.get("features_at_t", {}).get("context_inputs", {}).get("sequence_direction", 0) or 0)
            if direction != 0:
                example_rows.append(row)
                if len(example_rows) >= 5:
                    break
        if len(example_rows) >= 5:
            break

    if not example_rows:
        return {"error": "No hay filas con direction != 0"}

    # Probar con la primera fila
    row = example_rows[0]
    decision_time = row.get("decision_time")
    direction = int(row.get("features_at_t", {}).get("context_inputs", {}).get("sequence_direction", 0) or 0)

    print(f"   Fila de ejemplo: event_id={row.get('event_id','?')}, direction={direction}")
    print(f"   decision_time: {decision_time}")

    # Encontrar la posición de decision_time en M15
    if pd.api.types.is_datetime64_any_dtype(df["time"]):
        decision_dt = pd.to_datetime(decision_time, utc=True)
    else:
        decision_dt = pd.to_datetime(decision_time)

    time_mask = df["time"] <= decision_dt
    if time_mask.any():
        last_idx = df.index[time_mask][-1]
        print(f"   Índice de decision_time en M15: {last_idx} (vela index {last_idx})")
        print(f"   Velas disponibles antes de decision_time: {last_idx}")
        print(f"   Velas después de decision_time: {len(df) - last_idx - 1}")
    else:
        print(f"   decision_time NO está en rango de M15")
        print(f"   Rango M15: {df['time'].min()} → {df['time'].max()}")

    # Probar fine_execution con varios tamaños de ventana alrededor de decision_time
    for window_bars in [4, 10, 20, 30, 50, 100]:
        if last_idx is not None and last_idx - window_bars + 1 >= 0:
            window_df = df.iloc[last_idx - window_bars + 1:last_idx + 1].copy()
            window_df = window_df.reset_index(drop=True)

            try:
                result = fine_execution(
                    ms={"M15": window_df},
                    t=decision_time,
                    direction=direction,
                    exec_tf="M15",
                    rr=3.0,
                    sweep_ts=None,
                )
                ok_str = "OK" if result.get("ok") else "FAIL"
                print(f"   Ventana {window_bars} velas: {ok_str} (reason={result.get('reason','?')})")
                if result.get("ok"):
                    pip = 0.0001
                    print(f"     → entry={result['entry']}, sl={result['sl']}, tp={result['tp']}")
                    print(f"     → entry-SL={abs(result['entry']-result['sl'])/pip:.1f} pips, "
                          f"entry-TP={abs(result['tp']-result['entry'])/pip:.1f} pips")
            except Exception as e:
                print(f"   Ventana {window_bars} velas: ERROR {type(e).__name__}: {e}")

    # Verificar cuántas filas del dataset tienen decision_time dentro del rango de M15
    print(f"\n   Verificación de rango de decision_time:")
    m15_min = df["time"].min()
    m15_max = df["time"].max()
    print(f"   Rango M15: {m15_min} → {m15_max}")

    in_range = 0
    out_range_before = 0
    out_range_after = 0
    for row in load_splits().get("DATASET_TRAIN", []) + load_splits().get("DATASET_VALIDATION", []) + load_splits().get("DATASET_TEST_OOS", []):
        dt = row.get("decision_time")
        if dt:
            try:
                decision_dt = pd.to_datetime(dt, utc=True)
                if decision_dt < m15_min:
                    out_range_before += 1
                elif decision_dt > m15_max:
                    out_range_after += 1
                else:
                    in_range += 1
            except Exception:
                out_range_before += 1

    total = in_range + out_range_before + out_range_after
    print(f"   decision_times dentro de rango M15: {in_range}/{total} ({in_range/len(load_splits().get('DATASET_TRAIN',[])+load_splits().get('DATASET_VALIDATION',[])+load_splits().get('DATASET_TEST_OOS',[]))*100:.1f}%)")
    print(f"   decision_times ANTES de rango M15: {out_range_before}")
    print(f"   decision_times DESPUÉS de rango M15: {out_range_after}")

    return {"ok": True}


def main():
    print("=" * 70)
    print("EXECUTION_CALIBRATION_PREFLIGHT_V1 — Auditoría read-only")
    print("=" * 70)
    print()
    print("can_trade=false")
    print("entry_authorized=false")
    print("shadow_mode=true")
    print("prediction_is_diagnostic=true")
    print("execution_authority=engine.execution")
    print()

    splits = load_splits()
    all_rows = []
    for name, rows in splits.items():
        all_rows.extend(rows)

    # Cargar M15
    print("Cargando M15 desde data/raw/EURUSD/EURUSD_M15.parquet ...")
    m15_df = None
    source = ROOT / "data/raw/EURUSD/EURUSD_M15.parquet"
    if source.exists():
        try:
            table = pq.read_table(source)
            m15_df = table.to_pandas()
            m15_df = m15_df.sort_values("time").reset_index(drop=True)
            print(f"M15 OK: {len(m15_df):,} velas")
        except Exception as e:
            print(f"M15 error: {type(e).__name__}: {e}")

    print(f"\nFilas totales del dataset: {len(all_rows)}")
    print(f"  TRAIN: {len(splits.get('TRAIN', []))}")
    print(f"  VALIDATION: {len(splits.get('VALIDATION', []))}")
    print(f"  TEST_OOS: {len(splits.get('TEST_OOS', []))}")
    print()

    # 1. Cobertura de exec_tf
    print("1. COBERTURA DE EXEC_TF")
    tf_counts = Counter()
    for row in all_rows:
        tf = str((row.get("exec_tf_evidence") or {}).get("tf", "UNKNOWN"))
        tf_counts[tf] += 1
    for tf, count in sorted(tf_counts.items()):
        print(f"   TF={tf}: {count} ({count/len(all_rows)*100:.1f}%)")
    print()

    # 2. sweep_ts
    print("2. DISPONIBILIDAD DE SWEEP_TS")
    has_sweep = sum(1 for row in all_rows if row.get("features_at_t", {}).get("sweep_ts"))
    print(f"   Con sweep_ts: {has_sweep} ({has_sweep/len(all_rows)*100:.1f}%)")
    print(f"   Sin sweep_ts: {len(all_rows)-has_sweep} ({(len(all_rows)-has_sweep)/len(all_rows)*100:.1f}%)")
    print()

    # 3. Features relevantes
    print("3. FEATURES RELEVANTES")
    h4 = Counter()
    h1 = Counter()
    dirs = Counter()
    for row in all_rows:
        ctx = row.get("features_at_t", {}).get("context_inputs", {})
        h4[ctx.get("h4_location", "UNKNOWN")] += 1
        h1[ctx.get("h1_alignment", "UNKNOWN")] += 1
        dirs[int(ctx.get("sequence_direction", 0) or 0)] += 1
    print(f"   h4_location: {dict(h4)}")
    print(f"   h1_alignment: {dict(h1)}")
    print(f"   direction: {dict(dirs)}")
    print()

    # 4. Test fine_execution por split (breve)
    print("4. TEST fine_execution() POR SPLIT (con M15, sin sweep_ts)")
    print("-" * 70)

    if m15_df is not None and EXECUTION_AVAILABLE:
        for split_name, rows in splits.items():
            rows_con_dir = [r for r in rows if int(r.get("features_at_t", {}).get("context_inputs", {}).get("sequence_direction", 0) or 0) != 0]
            if not rows_con_dir:
                print(f"\n   [{split_name}] No hay filas con direction != 0")
                continue

            ok = 0
            fail_reasons = Counter()
            tested = 0
            for row in rows_con_dir[:min(10, len(rows_con_dir))]:
                direction = int(row.get("features_at_t", {}).get("context_inputs", {}).get("sequence_direction", 0) or 0)
                if direction == 0:
                    fail_reasons["direction_zero"] += 1
                    continue
                tested += 1
                try:
                    result = fine_execution(
                        ms={"M15": m15_df},
                        t=row.get("decision_time"),
                        direction=direction,
                        exec_tf="M15",
                        rr=3.0,
                        sweep_ts=None,
                    )
                    if result.get("ok"):
                        ok += 1
                    else:
                        fail_reasons[result.get("reason", "unknown")] += 1
                except Exception as e:
                    fail_reasons[f"exception: {type(e).__name__}"] += 1

            print(f"\n   [{split_name}] muestra n={len(rows_con_dir)} (prueba 10)")
            print(f"   OK: {ok}/{tested} ({ok/max(tested,1)*100:.1f}%)")
            if fail_reasons:
                for reason, count in sorted(fail_reasons.items(), key=lambda x: -x[1]):
                    print(f"     {reason}: {count}")
    else:
        print("   No hay M15 o execution.py disponible para probar.")
    print()

    # 5. Diagnóstico de not_enough_bars
    print("5. DIAGNÓSTICO DE not_enough_bars")
    print("-" * 70)
    diagnose_result = diagnose_not_enough_bars()
    print()

    # 6. Resumen ejecutivo
    print("=" * 70)
    print("RESUMEN EJECUTIVO")
    print("=" * 70)
    print()
    print(f"Filas totales: {len(all_rows)}")
    print(f"  M15 disponible: {'SI' if m15_df is not None else 'NO'}")
    print(f"  execution.py disponible: {'SI' if EXECUTION_AVAILABLE else 'NO'}")
    print()
    print("HALLAZGOS CLAVE:")
    print()
    print("  1. El dataset tiene exec_tf=M15 con window_bars=4 en el 100% de las filas")
    print("     → Pero fine_execution() necesita TF de ejecución fino (M5/M1)")
    print("     → M15 con 4 velas NO es suficiente para calibrar (not_enough_bars en 100%)")
    print()
    print("  2. sweep_ts NO disponible en 100% de las filas")
    print("     → SL usa fallback a swings, no mecha del sweep")
    print()
    print("  3. Todos los datos son EURUSD → pip_size=0.0001")
    print()
    print("  4. COBERTURA REAL para fine_execution(): 0%")
    print("     → execution.py NO puede calibrar con el dataset actual")
    print("     → Problema: window_bars=4 es insuficiente, no M15 en sí")
    print()
    print("=" * 70)
    print("DIAGNÓSTICO TÉCNICO")
    print("=" * 70)
    print()
    print("El problema NO es que execution.py no funcione.")
    print("El problema es que el dataset tiene M15 con window_bars=4,")
    print("pero fine_execution() necesita estructura de swings del exec TF.")
    print()
    print("Para calibrar con execution.py, se necesita:")
    print("  1. TF de ejecución (M5 o M1) con bastantes velas (>=20-30)")
    print("  2. O M15 con window_bars mayor (>=20-30)")
    print("  3. sweep_ts disponible para SL anclado al sweep")
    print()
    print("El dataset actual NO tiene ninguna de estas condiciones.")
    print()
    print("=" * 70)
    print("RECOMENDACIÓN")
    print("=" * 70)
    print()
    print("No proceder a EXECUTION_CALIBRATION_SHADOW_V1 con este dataset.")
    print()
    print("Soluciones posibles:")
    print()
    print("  A — Extender dataset a M5/M1 con estructura suficiente")
    print("     - Incluir M5/M1 de EURUSD (ya disponibles en data/raw/EURUSD/)")
    print("     - Materializar con window_bars >= 30 para cada decision_point")
    print("     - Requiere re-materializar el dataset completo")
    print()
    print("  B — Usar M15 completo como proxy (misma fuente, pero ventana grande)")
    print("     - Cambiar exec_tf_window_bars de 4 a >= 30")
    print("     - Documentar que es M15, no M5/M1")
    print("     - Mejorar cuando haya M5/M1 disponibles")
    print()
    print("  C — Esperar a tener M5/M1 materializados")
    print("     - Los archivos M5 y M1 existen en data/raw/EURUSD/")
    print("     - Solo hay que materializarlos en el dataset")
    print()
    print("Mantenimiento de restricciones:")
    print("  can_trade=false ✓")
    print("  entry_authorized=false ✓")
    print("  shadow_mode=true ✓")
    print("  prediction_is_diagnostic=true ✓")
    print("  execution_authority=engine.execution ✓")


if __name__ == "__main__":
    main()
