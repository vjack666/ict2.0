"""ict_backtest/bos_table_builder.py

Generador de la ``bos_table`` empirica para la ventana de confirmacion BOS
dinamica de R10 (Propuesta A). SIN indicadores: solo high-low del precio.

Responsabilidad:
- Extraer eventos BOS de un DataFrame ya anotado con market structure
  (columnas ``bos_dir`` / ``bos_level`` que ``detect_market_structure`` inyecta).
- Medir ``N_real`` = velas hasta que el precio toca el nivel del BOS, con
  corte por BOS de direccion opuesta (anti-sesgo de supervivencia: un BOS que
  nunca se mitiga porque fue invalidado por uno contrario NO cuenta).
- Calcular la mediana de ``N_real`` por bucket de fuerza (1..5) derivado con
  la MISMA formula que usa el motor (``confirmation_window`` en sequence.py).

El CLI (scripts/build_bos_table.py) orquesta la carga de datos reales y llama
a ``build_bos_table``; este modulo es la logica pura y testeable.
"""

from typing import Any

import numpy as np
import pandas as pd

from ict_backtest.market_object import MarketObject, ObjectType, Role, ObjectState


def _to_objects(df: pd.DataFrame, tf: str) -> list[MarketObject]:
    """Convierte el DataFrame anotado en MarketObject[] (igual que sequence)."""
    objs: list[MarketObject] = []
    for i, row in df.iterrows():
        meta: dict[str, Any] = {}
        for col in ("bos_dir", "choch_dir", "high", "low", "open", "close",
                    "bos_level", "time"):
            if col in df.columns:
                meta[col] = row[col]
        objs.append(MarketObject(
            type=ObjectType.CANDLE, origin_tf=tf, role=Role.REFINEMENT,
            direction=0, symbol="", state=ObjectState.ACTIVE,
            bar_index=int(i), bar_time=row.get("time"), meta=meta,
        ))
    return objs


def extract_bos_events(df: pd.DataFrame) -> list[tuple[int, float, int]]:
    """Devuelve [(idx, bos_level, direction), ...] para cada vela con BOS.

    Solo high-low / bos_dir / bos_level del market structure. Sin indicadores.
    """
    events: list[tuple[int, float, int]] = []
    for i, row in df.iterrows():
        bos_dir = int(row.get("bos_dir", 0) or 0)
        choch_dir = int(row.get("choch_dir", 0) or 0)
        level = row.get("bos_level", np.nan)
        if (bos_dir != 0 or choch_dir != 0) and pd.notna(level):
            direction = bos_dir if bos_dir != 0 else choch_dir
            events.append((int(i), float(level), int(direction)))
    return events


def measure_mitigation(df: pd.DataFrame,
                       events: list[tuple[int, float, int]]) -> list[int]:
    """Mide la VIDA del BOS: velas hasta que un BOS opuesto lo invalida.

    En el motor, ``bos_gap`` es la ventana de PACIENCIA maxima: cuantas velas
    espera la secuencia a ver el BOS de confirmacion (fase DISPLACE_DONE) o a
    que el precio toque la zona de entrada (fase BOS_DONE) antes de resetear.
    Calibrar ese numero con datos reales = medir cuanto aguanta tipicamente un
    BOS de fuerza r antes de que el mercado rompa estructura en contra.

    Definicion: para cada BOS en idx, N_real = (primer BOS de direccion opuesta
    estrictamente despues de idx) - idx. Esa es la "vida" del BOS.

    Corte anti-sesgo de supervivencia: los BOS que NUNCA son invalidados antes
    del fin de los datos se descartan (limit = n) porque no aportan a la ventana
    de paciencia (el motor los mantendria vivos hasta bos_gap de todos modos).
    """
    n = len(df)
    by_dir: dict[int, list[int]] = {}
    for idx, _level, direction in events:
        by_dir.setdefault(direction, []).append(idx)

    ns: list[int] = []
    for idx, _level, direction in events:
        opp_idxs = by_dir.get(-direction, [])
        limit = next((j for j in opp_idxs if j > idx), n)
        if limit >= n:
            continue  # BOS nunca invalidado -> descartar (anti-sesgo supervivencia)
        ns.append(limit - idx)
    return ns


def _bucket_of(objs: list[MarketObject], bos_idx: int) -> int | None:
    """Bucket 1..5 de la fuerza del BOS en bos_idx, via formula del motor.

    Reusa el calculo de ``confirmation_window`` (rango_bos / rango_ctx de 50
    velas). Devuelve None si hay rango 0 / ctx vacio (mismo fallback del motor).
    """
    if bos_idx <= 0:
        return None
    lo = max(0, bos_idx - 50)
    ctx = objs[lo:bos_idx]
    if len(ctx) == 0:
        return None
    rango_bos = float(objs[bos_idx].meta.get("high", 0.0)) - float(objs[bos_idx].meta.get("low", 0.0))
    if rango_bos <= 0:
        return None
    suma = sum(float(o.meta.get("high", 0.0)) - float(o.meta.get("low", 0.0)) for o in ctx)
    rango_ctx = suma / len(ctx)
    if rango_ctx <= 0:
        return None
    r = rango_bos / rango_ctx
    return max(1, min(5, int(round(r))))


def build_bos_table_from_counts(measures_by_bucket: dict[int, list[int]]) -> dict:
    """Mediana de N_real por bucket. Solo buckets con datos."""
    table: dict[int, int] = {}
    for bucket, vals in measures_by_bucket.items():
        if vals:
            table[bucket] = int(round(float(np.median(vals))))
    return table


def build_bos_table(df: pd.DataFrame, tf: str = "M15",
                    max_bucket: int = 5) -> dict:
    """Pipeline end-to-end sobre un DataFrame anotado con market structure.

    Devuelve {bucket: N_real_mediano} para buckets 1..max_bucket con muestra.
    """
    objs = _to_objects(df, tf)
    events = extract_bos_events(df)
    ns = measure_mitigation(df, events)
    if not ns:
        return {}
    measures: dict[int, list[int]] = {b: [] for b in range(1, max_bucket + 1)}
    for (idx, _level, _dir), n_real in zip(events, ns):
        bucket = _bucket_of(objs, idx)
        if bucket is not None and 1 <= bucket <= max_bucket:
            measures[bucket].append(n_real)
    return build_bos_table_from_counts(measures)
