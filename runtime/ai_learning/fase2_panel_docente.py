#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FASE 2: Panel docente de ejemplos causales de desplazamiento.

LOCAL_ONLY. Carga datos M15 de EURUSD, aplica el profesor y genera
el panel docente con episodios positivos, negativos y ambiguos.

Estado: FASE2 — ejemplos causales.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from runtime.ai_learning.displacement_teacher import (
    DisplacementProfile,
    DisplacementTeacher,
    DisplacementTeacherConfig,
    GeometricStrength,
    Direction,
    IctContextStatus,
)


@dataclass
class DocenteEpisode:
    """Episodio para el panel docente."""
    candle_idx: int
    time: int
    geometric_strength: str
    direction: str
    ict_context_status: str
    body_to_range_ratio: float
    body_pips: float
    range_pips: float
    wick_ratio: float
    category: str  # POSITIVE, NEGATIVE, AMBIGUOUS
    subcategory: str  # Simple, Local, ICT, Dificil
    description: str
    confirmation_time: int | None = None
    duration_bars: int = 0


def load_m15_data(month_file: Path) -> pd.DataFrame:
    """Cargar datos M15 de un archivo CSV mensual."""
    df = pd.read_csv(
        month_file,
        parse_dates=["time"],
        usecols=["time", "open", "high", "low", "close"],
    )
    df["time"] = df["time"].astype(int) // 10**9  # timestamp Unix
    return df


def classify_episode(profile: DisplacementProfile, context_available: bool) -> tuple[str, str]:
    """Clasificar episodio para el panel docente."""
    geom = profile.geometric_strength
    direc = profile.direction
    ctx = profile.ict_context_status

    if geom in (GeometricStrength.STRONG, GeometricStrength.WEAK):
        if direc in (Direction.UP, Direction.DOWN):
            if ctx == IctContextStatus.SUPPORTED:
                return "POSITIVE", "ICT_COMPLETO"
            elif ctx == IctContextStatus.PENDING:
                return "POSITIVE", "ICT_PENDIENTE"
            elif ctx == IctContextStatus.UNKNOWN:
                return "POSITIVE", "SIN_CONTEXTO"
            else:
                return "POSITIVE", "GEOMETRIA_SOLO"
        elif direc == Direction.NONE:
            return "NEGATIVE", "SIN_DIRECCION"

    if geom == GeometricStrength.NONE:
        return "NEGATIVE", "GEOMETRIA_INSUFICIENTE"

    if geom == GeometricStrength.UNKNOWN:
        return "AMBIGUOUS", "HISTORIA_INSUFICIENTE"

    if direc == Direction.NONE and geom == GeometricStrength.WEAK:
        return "AMBIGUOUS", "WEAK_SIN_DIRECCION"

    return "AMBIGUOUS", "CASO_LIMITE"


def generate_synthetic_examples() -> list[DocenteEpisode]:
    """Generar ejemplos sintéticos para el curriculum del plan."""
    examples = []
    cfg = DisplacementTeacherConfig()
    teacher = DisplacementTeacher(cfg)

    # 1. CONTRASTE SIMPLE: Doji
    frame = pd.DataFrame({
        "time": list(range(10)),
        "open": [1.0000] * 10,
        "high": [1.0000 + 0.001] * 10,
        "low": [1.0000 - 0.001] * 10,
        "close": [1.0000 + 0.00001] * 10,
    })
    p = teacher.evaluate(frame, 5)
    examples.append(DocenteEpisode(
        candle_idx=5, time=frame.iloc[5]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="NEGATIVE", subcategory="CONTRASTE_SIMPLE",
        description="Doji: cuerpo negligible, no es desplazamiento",
    ))

    # 2. CONTRASTE SIMPLE: Rango cero
    frame = pd.DataFrame({
        "time": list(range(10)),
        "open": [1.0000] * 10,
        "high": [1.0000] * 10,
        "low": [1.0000] * 10,
        "close": [1.0000] * 10,
    })
    p = teacher.evaluate(frame, 5)
    examples.append(DocenteEpisode(
        candle_idx=5, time=frame.iloc[5]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="NEGATIVE", subcategory="CONTRASTE_SIMPLE",
        description="Rango cero: velas idénticas, sin movimiento",
    ))

    # 3. CONTRASTE SIMPLE: Cuerpo dominante alcista STRONG
    frame = pd.DataFrame({
        "time": list(range(10)),
        "open": [1.0000] * 10,
        "high": [1.0000 + 0.010] * 10,
        "low": [1.0000] * 10,
        "close": [1.0000 + 0.008] * 10,
    })
    p = teacher.evaluate(frame, 5)
    examples.append(DocenteEpisode(
        candle_idx=5, time=frame.iloc[5]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="POSITIVE", subcategory="CONTRASTE_SIMPLE",
        description="Cuerpo dominante alcista 80%: STRONG direction UP",
    ))

    # 4. CONTRASTE SIMPLE: Cuerpo dominante bajista STRONG
    frame = pd.DataFrame({
        "time": list(range(10)),
        "open": [1.0000] * 10,
        "high": [1.0000 + 0.001] * 10,
        "low": [1.0000 - 0.010] * 10,
        "close": [1.0000 - 0.008] * 10,
    })
    p = teacher.evaluate(frame, 5)
    examples.append(DocenteEpisode(
        candle_idx=5, time=frame.iloc[5]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="POSITIVE", subcategory="CONTRASTE_SIMPLE",
        description="Cuerpo dominante bajista 80%: STRONG direction DOWN",
    ))

    # 5. CONTEXTO LOCAL: Vela grande dentro de rango consolidado
    base_prices = [1.0000 + idx * 0.0001 for idx in range(15)]
    frame = pd.DataFrame({
        "time": list(range(15)),
        "open": base_prices,
        "high": [p + 0.0005 for p in base_prices],
        "low": [p - 0.0005 for p in base_prices],
        "close": base_prices,
    })
    frame.loc[8, "open"] = 1.0008
    frame.loc[8, "high"] = 1.0015
    frame.loc[8, "low"] = 1.0005
    frame.loc[8, "close"] = 1.0013
    p = teacher.evaluate(frame, 8)
    examples.append(DocenteEpisode(
        candle_idx=8, time=frame.iloc[8]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="NEGATIVE", subcategory="CONTEXTO_LOCAL",
        description="Vela grande dentro de rango consolidado: no rompe estructura",
    ))

    # 6. CONTEXTO ICT: Desplazamiento con sweep + FVG → SUPPORTED
    frame = pd.DataFrame({
        "time": list(range(15)),
        "open": [1.0000] * 15,
        "high": [1.0000 + 0.001] * 15,
        "low": [1.0000 - 0.001] * 15,
        "close": [1.0000] * 15,
    })
    frame.loc[5, "open"] = 1.0000
    frame.loc[5, "high"] = 1.0000 + 0.008
    frame.loc[5, "low"] = 1.0000
    frame.loc[5, "close"] = 1.0000 + 0.006
    p = teacher.evaluate(frame, 5, context={
        "sweep_previo": True,
        "fvg_cercano": True,
        "estructura_confirmada": False,
        "htf_sesgo": "BULLISH",
    })
    examples.append(DocenteEpisode(
        candle_idx=5, time=frame.iloc[5]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="POSITIVE", subcategory="CONTEXTO_ICT",
        description="Desplazamiento con sweep + FVG cercano: ICT SUPPORTED",
    ))

    # 7. CONTEXTO ICT: Mismo desplazamiento sin contexto → PENDING
    p2 = teacher.evaluate(frame, 5, context={
        "sweep_previo": False,
        "fvg_cercano": False,
        "htf_desconocido": True,
    })
    examples.append(DocenteEpisode(
        candle_idx=5, time=frame.iloc[5]["time"],
        geometric_strength=p2.geometric_strength.name,
        direction=p2.direction.name,
        ict_context_status=p2.ict_context_status.name,
        body_to_range_ratio=p2.body_to_range_ratio or 0,
        body_pips=p2.body_pips, range_pips=p2.range_pips,
        wick_ratio=p2.wick_ratio,
        category="POSITIVE", subcategory="CONTEXTO_ICT",
        description="Desplazamiento sin contexto ICT: PENDING (no confirmado, no negado)",
    ))

    # 8. CASO DIFICIL: Movimiento fuerte con retroceso >50%
    frame = pd.DataFrame({
        "time": list(range(20)),
        "open": [1.0000] * 20,
        "high": [1.0000 + 0.001] * 20,
        "low": [1.0000 - 0.001] * 20,
        "close": [1.0000] * 20,
    })
    frame.loc[5, "open"] = 1.0000
    frame.loc[5, "high"] = 1.0000 + 0.010
    frame.loc[5, "low"] = 1.0000
    frame.loc[5, "close"] = 1.0000 + 0.008
    # Vela 6 retrocede
    frame.loc[6, "open"] = 1.0000 + 0.008
    frame.loc[6, "high"] = 1.0000 + 0.008
    frame.loc[6, "low"] = 1.0000 + 0.002
    frame.loc[6, "close"] = 1.0000 + 0.003
    p = teacher.evaluate(frame, 5)
    examples.append(DocenteEpisode(
        candle_idx=5, time=frame.iloc[5]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="AMBIGUOUS", subcategory="CASO_DIFICIL",
        description="Movimiento fuerte con retroceso >50% después: candidato no confirmado",
    ))

    # 9. CASO DIFICIL: Fin de datos sin confirmación
    frame = pd.DataFrame({
        "time": list(range(10)),
        "open": [1.0000] * 10,
        "high": [1.0000 + 0.010] * 10,
        "low": [1.0000] * 10,
        "close": [1.0000 + 0.008] * 10,
    })
    p = teacher.evaluate(frame, 8)
    examples.append(DocenteEpisode(
        candle_idx=8, time=frame.iloc[8]["time"],
        geometric_strength=p.geometric_strength.name,
        direction=p.direction.name,
        ict_context_status=p.ict_context_status.name,
        body_to_range_ratio=p.body_to_range_ratio or 0,
        body_pips=p.body_pips, range_pips=p.range_pips,
        wick_ratio=p.wick_ratio,
        category="AMBIGUOUS", subcategory="CASO_DIFICIL",
        description="Fin de datos: desplazamiento sin confirmación por falta de historia futura",
    ))

    return examples


def analyze_real_data(data_dir: Path, months: int = 3) -> list[DocenteEpisode]:
    """Analizar datos reales M15 de EURUSD y extraer episodios representativos."""
    episodes = []
    csv_files = sorted(data_dir.glob("**/*.csv"))
    if not csv_files:
        print("No se encontraron archivos CSV")
        return episodes

    for csv_file in csv_files[:months]:
        print(f"Cargando: {csv_file.name}")
        try:
            df = load_m15_data(csv_file)
            if len(df) < 100:
                continue
        except Exception as e:
            print(f"  Error cargando {csv_file.name}: {e}")
            continue

        teacher = DisplacementTeacher()
        candle_results = []

        for i in range(5, min(len(df) - 2, 500)):
            profile = teacher.evaluate(df, i)
            cat, subcat = classify_episode(profile, context_available=True)

            candle_results.append({
                "idx": i,
                "time": int(df.iloc[i]["time"]),
                "geom": profile.geometric_strength.name,
                "dir": profile.direction.name,
                "ctx": profile.ict_context_status.name,
                "body_ratio": profile.body_to_range_ratio or 0,
                "body_pips": profile.body_pips,
                "category": cat,
                "subcategory": subcat,
            })

        positives = [r for r in candle_results if r["category"] == "POSITIVE"]
        negatives = [r for r in candle_results if r["category"] == "NEGATIVE"]
        ambiguouss = [r for r in candle_results if r["category"] == "AMBIGUOUS"]

        # Top POSITIVE
        posit_sorted = sorted(positives, key=lambda x: x["body_ratio"], reverse=True)
        for r in posit_sorted[:3]:
            episodes.append(DocenteEpisode(
                candle_idx=r["idx"], time=r["time"],
                geometric_strength=r["geom"],
                direction=r["dir"],
                ict_context_status=r["ctx"],
                body_to_range_ratio=r["body_ratio"],
                body_pips=0, range_pips=0, wick_ratio=0,
                category=r["category"],
                subcategory=r["subcategory"],
                description=f"EURUSD M15 real: desplazamiento {r['dir']} body/ratio {r['body_ratio']:.1%}",
            ))

        # NEGATIVE
        neg_sorted = sorted(negatives, key=lambda x: x["body_ratio"])
        for r in neg_sorted[:2]:
            episodes.append(DocenteEpisode(
                candle_idx=r["idx"], time=r["time"],
                geometric_strength=r["geom"],
                direction=r["dir"],
                ict_context_status=r["ctx"],
                body_to_range_ratio=r["body_ratio"],
                body_pips=0, range_pips=0, wick_ratio=0,
                category=r["category"],
                subcategory=r["subcategory"],
                description=f"EURUSD M15 real: {r['subcategory']} body/ratio {r['body_ratio']:.1%}",
            ))

        # AMBIGUOUS
        for r in ambiguouss[:2]:
            episodes.append(DocenteEpisode(
                candle_idx=r["idx"], time=r["time"],
                geometric_strength=r["geom"],
                direction=r["dir"],
                ict_context_status=r["ctx"],
                body_to_range_ratio=r["body_ratio"],
                body_pips=0, range_pips=0, wick_ratio=0,
                category=r["category"],
                subcategory=r["subcategory"],
                description=f"EURUSD M15 real: {r['subcategory']} body/ratio {r['body_ratio']:.1%}",
            ))

    return episodes


def write_panel_docente(sinteticos: list[DocenteEpisode], reales: list[DocenteEpisode], output_dir: Path):
    """Escribir el panel docente en formato JSON y resumen legible."""
    output_dir.mkdir(parents=True, exist_ok=True)

    panel = {
        "version": "1.0",
        "fecha": "2026-09-17",
        "total_ejemplos": len(sinteticos) + len(reales),
        "sinteticos": [
            {
                "candle_idx": e.candle_idx,
                "time": e.time,
                "geometric_strength": e.geometric_strength,
                "direction": e.direction,
                "ict_context_status": e.ict_context_status,
                "body_to_range_ratio": e.body_to_range_ratio,
                "category": e.category,
                "subcategory": e.subcategory,
                "description": e.description,
            }
            for e in sinteticos
        ],
        "reales": [
            {
                "candle_idx": e.candle_idx,
                "time": e.time,
                "geometric_strength": e.geometric_strength,
                "direction": e.direction,
                "ict_context_status": e.ict_context_status,
                "body_to_range_ratio": e.body_to_range_ratio,
                "category": e.category,
                "subcategory": e.subcategory,
                "description": e.description,
            }
            for e in reales
        ],
    }

    with open(output_dir / "panel_docente.json", "w", encoding="utf-8") as f:
        json.dump(panel, f, indent=2, ensure_ascii=False)

    lines = [
        "# Panel Docente de Desplazamiento v1",
        "",
        f"**Fecha:** 2026-09-17",
        f"**Total ejemplos:** {len(sinteticos) + len(reales)}",
        "",
        "## Ejemplos Sintéticos (curriculum del plan)",
        "",
    ]

    for e in sinteticos:
        lines.append(f"### {e.category}: {e.description}")
        lines.append(f"- Geometric_strength: {e.geometric_strength}")
        lines.append(f"- Direction: {e.direction}")
        lines.append(f"- ICT_context: {e.ict_context_status}")
        lines.append(f"- Body/ratio: {e.body_to_range_ratio:.1%}")
        lines.append("")

    lines.append("## Ejemplos Reales (EURUSD M15)")
    lines.append("")

    for e in reales[:10]:
        lines.append(f"### {e.category}: {e.description}")
        lines.append(f"- Geometric_strength: {e.geometric_strength}")
        lines.append(f"- Direction: {e.direction}")
        lines.append(f"- ICT_context: {e.ict_context_status}")
        lines.append(f"- Body/ratio: {e.body_to_range_ratio:.1%}")
        lines.append("")

    lines.append("## Resumen por categoría")
    lines.append("")
    lines.append("| Categoría | Count |")
    lines.append("|-----------|-------|")

    sint_count = defaultdict(int)
    real_count = defaultdict(int)
    for e in sinteticos:
        sint_count[e.category] += 1
    for e in reales:
        real_count[e.category] += 1

    for cat in ["POSITIVE", "NEGATIVE", "AMBIGUOUS"]:
        lines.append(f"| {cat} | {sint_count[cat] + real_count[cat]} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Nota:** Este panel es el conjunto de ejemplos para entrenar reconocimiento de desplazamiento.")
    lines.append("Las neuronas deben aprender a distinguir geometría de contexto ICT.")
    lines.append("El resultado posterior no redefine lo observable en decision_time.")

    with open(output_dir / "panel_docente_resumen.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return panel


def main():
    print("=" * 60)
    print("FASE 2: Panel docente de ejemplos causales")
    print("=" * 60)

    print("\n[1/3] Generando ejemplos sintéticos del curriculum...")
    sinteticos = generate_synthetic_examples()
    print(f"  Generados: {len(sinteticos)} ejemplos sintéticos")

    print("\n[2/3] Analizando datos reales M15 EURUSD...")
    data_dir = Path("/c/Users/v_jac/Desktop/ICT SYSTEM/datasets/eurusd_dukascopy_intraday_2021_2025")
    reales = analyze_real_data(data_dir, months=3)
    print(f"  Extraídos: {len(reales)} ejemplos reales representativos")

    print("\n[3/3] Escribiendo panel docente...")
    output_dir = Path("/c/Users/v_jac/Desktop/ICT SYSTEM/reports/ict_temporal_v1/helix/displacement_v1")
    panel = write_panel_docente(sinteticos, reales, output_dir)

    print(f"\n=== RESULTADO ===")
    print(f"Panel docente: {output_dir / 'panel_docente.json'}")
    print(f"Resumen: {output_dir / 'panel_docente_resumen.md'}")
    print(f"Total ejemplos: {panel['total_ejemplos']}")

    cats = defaultdict(int)
    for e in sinteticos:
        cats[e.category] += 1
    for e in reales:
        cats[e.category] += 1

    print("\nDistribución por categoría:")
    for cat, count in cats.items():
        print(f"  {cat}: {count}")

    return panel


if __name__ == "__main__":
    main()
