#!/usr/bin/env python3
"""Barrido ultra-rápido multi-par v2: contar condiciones POI básicas en vectorizado.

NO llama a pd_array_zone (el cuello de botella). Solo cuenta cuántas velas M15
cumplen las 3 condiciones POI del materializador corregido:
  1. Zona correcta del dealing range (long→DISCOUNT, short→PREMIUM)
  2. HTF alineado (h1_alignment == ALIGNED)
  3. Displacement detectado (cuerpo grande + break de estructura H1)
  + FVG asumido presente (mejor caso)

Con el ratio obtenido, extrapola cuántos USABLE_UNGRADED habría en el dataset
completo multi-par.

Corre en ~30-60 segundos.
"""

from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np


def load_and_prepare(m15_path: Path, h1_path: Path, d1_path: Path) -> tuple:
    """Cargar y preparar DataFrames M15, H1, D1."""
    m15 = pd.read_parquet(m15_path)
    h1 = pd.read_parquet(h1_path)
    d1 = pd.read_parquet(d1_path)

    for df in (m15, h1, d1):
        df["dt"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        df["dt"] = df["dt"].dt.tz_localize(None)  # tz-naive para comparación
        df.sort_values("dt", inplace=True)
        df.reset_index(drop=True, inplace=True)

    # Excluir última vela abierta de M15
    m15_closed = m15.iloc[:-1].copy()
    m15_closed["date"] = m15_closed["dt"].dt.date

    d1["date"] = d1["dt"].dt.date

    return m15_closed, h1, d1


def sample_velas(m15_closed: pd.DataFrame, n_sample: int = 5000) -> pd.DataFrame:
    """Muestreo estratificado: tomar velas espaciadas uniformemente."""
    n = len(m15_closed)
    if n <= n_sample:
        return m15_closed.copy()

    step = n // n_sample
    indices = list(range(0, n, step))[:n_sample]
    return m15_closed.iloc[indices].copy()


def compute_poi_conditions(m15_s: pd.DataFrame, h1: pd.DataFrame, d1: pd.DataFrame) -> dict:
    """Calcular condiciones POI para todas las velas en vectorizado.

    Retorna dict con arrays numpy de:
    - ok_zona: bool (zona correcta para la dirección)
    - ok_htf: bool (h1_alignment == ALIGNED)
    - ok_displacement: bool (displacement detectado)
    - razones: Counter de por qué falló cada condición
    """
    n = len(m15_s)
    o = m15_s["open"].values.astype(float)
    c = m15_s["close"].values.astype(float)
    h = m15_s["high"].values.astype(float)
    l = m15_s["low"].values.astype(float)

    # Dirección: +1 bullish, -1 bearish, 0 neutro
    direction = np.where(c > o, 1, np.where(c < o, -1, 0))
    neutros = (direction == 0).sum()

    # --- CONDICIÓN 1: Zona correcta ---
    # Para cada vela, calcular H4_LOCATION desde D1 del día
    ok_zona = np.zeros(n, dtype=bool)
    razones_zona = Counter()
    dates = m15_s["date"].values
    d1_dates = d1["date"].values

    # Índice de D1 por date para lookup rápido
    d1_by_date = {}
    for _, row in d1.iterrows():
        d1_by_date[row["date"]] = (row["low"], row["high"])

    for i in range(n):
        day = dates[i]
        if day not in d1_by_date:
            razones_zona["d1_no_data"] += 1
            continue
        d_low, d_high = d1_by_date[day]
        d_rng = d_high - d_low
        if d_rng <= 0:
            razones_zona["d1_rango_cero"] += 1
            continue
        pos = (c[i] - d_low) / d_rng
        if pos < 0.30:
            h4 = "DISCOUNT"
        elif pos > 0.70:
            h4 = "PREMIUM"
        else:
            h4 = "EQUILIBRIUM"

        if direction[i] > 0:
            ok_zona[i] = (h4 == "DISCOUNT")
            if not ok_zona[i]:
                razones_zona["long_en_premium_o_eq"] += 1
        elif direction[i] < 0:
            ok_zona[i] = (h4 == "PREMIUM")
            if not ok_zona[i]:
                razones_zona["short_en_discount_o_eq"] += 1
        else:
            razones_zona["neutro"] += 1

    # --- CONDICIÓN 2: HTF Alignment ---
    ok_htf = np.zeros(n, dtype=bool)
    razones_htf = Counter()

    # Para cada vela M15, encontrar el H1 que la contiene
    h1_dt = h1["dt"].values
    for i in range(n):
        dt = m15_s["dt"].iloc[i]
        # Último H1 con dt <= decision_time
        mask = h1_dt <= dt
        if not mask.any():
            razones_htf["h1_no_data"] += 1
            continue
        idx_h1 = np.where(mask)[0][-1]
        h1_row = h1.iloc[idx_h1]
        h1_open = float(h1_row["open"])
        h1_close = float(h1_row["close"])
        h1_bias = 1 if h1_close > h1_open else (-1 if h1_close < h1_open else 0)
        if h1_bias == 0:
            razones_htf["h1_neutro"] += 1
            continue
        if direction[i] == h1_bias:
            ok_htf[i] = True
        else:
            razones_htf["h1_contra"] += 1

    # --- CONDICIÓN 3: Displacement ---
    ok_displacement = np.zeros(n, dtype=bool)
    razones_disp = Counter()

    bar_rng = h - l
    body = np.abs(c - o)

    for i in range(n):
        if bar_rng[i] <= 0:
            razones_disp["rango_cero"] += 1
            continue
        if body[i] / bar_rng[i] < 0.70:
            razones_disp["cuerpo_pequeno"] += 1
            continue

        dt = m15_s["dt"].iloc[i]
        mask = h1_dt <= dt
        if not mask.any():
            razones_disp["h1_no_data"] += 1
            continue
        h1_before = h1[mask]
        if len(h1_before) < 5:
            razones_disp["h1_insuficiente"] += 1
            continue
        prev_h1 = h1_before.iloc[-5:-1]
        if direction[i] > 0:
            if c[i] > prev_h1["high"].max():
                ok_displacement[i] = True
            else:
                razones_disp["no_break_h1"] += 1
        elif direction[i] < 0:
            if c[i] < prev_h1["low"].min():
                ok_displacement[i] = True
            else:
                razones_disp["no_break_h1"] += 1
        else:
            razones_disp["neutro"] += 1

    return {
        "direction": direction,
        "ok_zona": ok_zona,
        "ok_htf": ok_htf,
        "ok_displacement": ok_displacement,
        "razones_zona": razones_zona,
        "razones_htf": razones_htf,
        "razones_disp": razones_disp,
        "n_neutros": neutros,
    }


def main():
    pairs_dir = ROOT / "data/raw"
    print("=" * 85)
    print("BARRIDO ULTRA-RÁPIDO v2 — 7 pares adicionales (vectorizado, 5K muestras/par)")
    print("=" * 85)
    print()
    print(f"{'PAR':<10} {'TOTAL_M15':>10} {'MUESTRA':>8} {'ZONA_OK':>7} {'HTF_OK':>6} {'DISP_OK':>7} {'LAS_3':>6} {'RATIO':>7}")
    print("-" * 85)

    total_muestra = 0
    total_las_3 = 0

    for p in sorted(pairs_dir.iterdir()):
        if not p.is_dir() or p.name == "EURUSD":
            continue

        pname = p.name
        m15_p = p / f"{pname}_M15.parquet"
        h1_p = p / f"{pname}_H1.parquet"
        d1_p = p / f"{pname}_D1.parquet"

        if not m15_p.exists():
            continue

        print(f"\n--- {pname} ---", flush=True)
        t0_load = pd.Timestamp.now()

        m15_closed, h1, d1 = load_and_prepare(m15_p, h1_p, d1_p)
        m15_s = sample_velas(m15_closed, n_sample=5000)
        total_m15 = len(m15_closed)

        print(f"  Cargadas {total_m15:,} velas, muestras {len(m15_s):,}... ", flush=True)

        features = compute_poi_conditions(m15_s, h1, d1)

        n = len(m15_s)
        zona_ok = features["ok_zona"].sum()
        htf_ok = features["ok_htf"].sum()
        disp_ok = features["ok_displacement"].sum()
        las_3 = (features["ok_zona"] & features["ok_htf"] & features["ok_displacement"]).sum()

        ratio = las_3 / n if n > 0 else 0

        print(
            f"  {pname:<10} "
            f"{total_m15:>10,} "
            f"{n:>8,} "
            f"{zona_ok:>7,} "
            f"{htf_ok:>6,} "
            f"{disp_ok:>7,} "
            f"{las_3:>6,} "
            f"{ratio:>7.2%}"
        )
        print(f"    Razones zona: {dict(features['razones_zona'])}", flush=True)
        print(f"    Razones htf: {dict(features['razones_htf'])}", flush=True)
        print(f"    Razones disp: {dict(features['razones_disp'])}", flush=True)

        total_muestra += n
        total_las_3 += las_3

    print()
    print("-" * 85)
    print(
        f"{'TOTAL':<10} {'':>10} "
        f"{total_muestra:>8,} "
        f"{'':>7} "
        f"{'':>6} "
        f"{'':>7} "
        f"{total_las_3:>6,} "
        f"{total_las_3/total_muestra if total_muestra > 0 else 0:>7.2%}"
    )

    print()
    print("RESULTADO DEL BARRIDO:")
    print(f"  Muestras analizadas: {total_muestra:,} velas de 7 pares adicionales")
    print(f"  Velas con las 3 condiciones POI: {total_las_3:,} ({total_las_3/total_muestra if total_muestra > 0 else 0:.2%})")
    print()

    # Extrapolación a total de velas M15 cerradas en los 7 pares
    total_velas_7pares = 0
    for p in sorted(pairs_dir.iterdir()):
        if not p.is_dir() or p.name == "EURUSD":
            continue
        m15_p = p / f"{p.name}_M15.parquet"
        if m15_p.exists():
            df = pd.read_parquet(m15_p)
            total_velas_7pares += len(df) - 1  # excluir última
    print(f"  Total velas M15 cerradas en 7 pares: ~{total_velas_7pares:,}")
    print(f"  Extrapolación de USABLE_UNGRADED (con ratio {total_las_3/total_muestra if total_muestra > 0 else 0:.2%}):")
    print(f"    ~{int(total_velas_7pares * (total_las_3/total_muestra if total_muestra > 0 else 0)):,} USABLE_UNGRADED potenciales")
    print()
    print("COMPARACIÓN:")
    print(f"  Dataset actual EURUSD: 292 filas, 6 USABLE_UNGRADED (2.05%)")
    print(f"  Multi-par estimado: ~{total_velas_7pares:,} filas, ~{int(total_velas_7pares * (total_las_3/total_muestra if total_muestra > 0 else 0)):,} USABLE_UNGRADED")
    print()
    print("NOTA: este barrido asume FVG siempre presente. Con detección real de FVG,")
    print("el número podría ser menor. Es un ESTIMADO del techo superior de positivos.")
    print()
    print("RECOMENDACIÓN:")
    extrap = int(total_velas_7pares * (total_las_3/total_muestra if total_muestra > 0 else 0))
    if extrap >= 100:
        print(f"  ✓ ~{extrap} positivos estimados → suficiente para reentrenar con más confianza.")
        print(f"    Materializar multi-par tiene sentido.")
    elif extrap >= 30:
        print(f"  ~ {extrap} positivos estimados → mejor que ahora (6) pero aún limitado.")
        print(f"    Podría mejorar resultados pero no garantiza certificación.")
    else:
        print(f"  ✗ Solo ~{extrap} positivos estimados → la escasez persiste.")
        print(f"    Revisar definición de USABLE_UNGRADED o ampliar detección de displacement.")


if __name__ == "__main__":
    main()
