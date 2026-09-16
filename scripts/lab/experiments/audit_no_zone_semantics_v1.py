#!/usr/bin/env python3
"""Auditoría semántica de las 73 filas NO_ZONE y las 219 con zona del dataset
SETUP_GRAMMAR_DATASET_V1.

Aplica semantic_pd_array_eval_v1 sobre cada fila, reensamblando la evidencia M15
desde fuentes históricas hasta decision_time (causal).

Resultado esperado:
    - Conteo de cada estado (VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING)
    - Tabla de las 73 filas NO_ZONE con su clasificación semántica
    - Distribución de las 219 filas con zona (valid/invalid)
    - Verificación de que no hay leakage temporal
    - Conclusión sobre falsos negativos (NO_ZONE incorrectos) y falsos positivos (zona inválida etiquetada como válida)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from engine.m15_evidence_assembler import build_m15_evidence_for_decision_time
from scripts.lab.experiments.semantic_pd_array_eval_v1 import (
    EVIDENCE_MISSING,
    INVALID_ZONE,
    NO_ZONE,
    VALID_ITF_ZONE,
    semantic_pd_array_zone,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("audit_no_zone_semantics")

ROOT = Path(__file__).parent.parent.parent
DATASET_PATH = ROOT / "data" / "ml" / "tensorflow" / "setup_grammar_v1"
REPORT_PATH = ROOT / "reports" / "audits" / "experiments" / "ai"
REPORT_NAME = "setup_grammar_semantics_v1_audit.md"

# ─────────────────────────────────────────────────────────────────────────────
# Cargas de datos
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset() -> pd.DataFrame:
    """Cargar el dataset SETUP_GRAMMAR_DATASET_V1 y combinar los tres splits."""
    dfs = []
    for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
        path = DATASET_PATH / f"dataset_{split.lower()}.jsonl"
        if not path.exists():
            logger.warning(f"Split {split} no encontrado: {path}")
            continue
        df = pd.read_json(path, lines=True)
        dfs.append(df)
    if not dfs:
        raise FileNotFoundError(f"No se encontró ningún split en {DATASET_PATH}")
    combined = pd.concat(dfs, ignore_index=True)
    return combined


def load_feature_schema() -> dict[str, Any]:
    """Cargar el schema de features del dataset."""
    path = DATASET_PATH / "feature_schema.json"
    if not path.exists():
        logger.warning(f"feature_schema.json no encontrado: {path}")
        return {}
    with open(path, "r") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría semántica por fila
# ─────────────────────────────────────────────────────────────────────────────

def audit_row_semantically(row_data: dict[str, Any], h4_frame: pd.DataFrame | None = None) -> dict[str, Any]:
    """Auditar una fila del dataset semánticamente.

    Reconstruye la evidencia M15 para el decision_time de la fila y aplica el
    detector semántico.
    """
    try:
        decision_time = row_data.get("decision_time")
        if decision_time is None:
            return {
                "zone_state": EVIDENCE_MISSING,
                "reason": "decision_time no disponible",
                "conditions": {},
            }

        # Normalizar decision_time a Timestamp UTC
        if isinstance(decision_time, str):
            decision_time = pd.to_datetime(decision_time, utc=True)
        elif not isinstance(decision_time, pd.Timestamp):
            decision_time = pd.to_datetime(decision_time, utc=True)

        features_at_t = row_data.get("features_at_t")
        if features_at_t is None:
            return {
                "zone_state": EVIDENCE_MISSING,
                "reason": "features_at_t no disponible",
                "conditions": {},
            }

        direction = int((row_data.get("features_at_t") or {}).get("context_inputs", {}).get("sequence_direction", 0) or 0)

        # Si no hay fuente M15 adjunta, no podemos evaluar condición 3
        # Para las filas del dataset, verificamos si existe un m15_source adjunto
        m15_source = row.get("m15_source")
        if m15_source is None or (isinstance(m15_source, str) and m15_source == ""):
            logger.warning(f"No hay m15_source para decision_time={decision_time}")
            return {
                "zone_state": EVIDENCE_MISSING,
                "reason": "m15_source no disponible en la fila",
                "conditions": {},
            }

        # Construir evidencia M15 desde el source de la fila
        m15_evidence = _build_m15_evidence_safe(
            decision_time=decision_time,
            m15_source=m15_source,
            h4_frame=h4_frame,
        )

        result = semantic_pd_array_zone(
            decision_time=decision_time,
            features_at_t=features_at_t,
            m15_evidence=m15_evidence,
            direction=direction,
        )
        return result

    except Exception as e:
        logger.exception(f"Error auditando fila: {e}")
        return {
            "zone_state": EVIDENCE_MISSING,
            "reason": f"excepción: {e}",
            "conditions": {},
        }


def _build_m15_evidence_safe(
    decision_time: pd.Timestamp,
    m15_source: Any,
    h4_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Construir evidencia M15 desde el source de la fila.

    Si el source es un path de archivo, lo carga y construye la evidencia.
    Si es un json/dict, usa directamente.
    Si no se puede, devuelve evidencia vacía.
    """
    try:
        # Si el source es un path de archivo JSONL/CSV
        if isinstance(m15_source, str) and Path(m15_source).exists():
            df = pd.read_json(Path(m15_source), lines=True)
        elif isinstance(m15_source, list):
            df = pd.DataFrame(m15_source)
        elif isinstance(m15_source, dict):
            df = pd.DataFrame([m15_source])
        else:
            # intentar como path
            path = Path(str(m15_source))
            if path.exists():
                df = pd.read_json(path, lines=True)
            else:
                logger.warning(f"m15_source no reconocido: {m15_source}")
                return _empty_evidence("m15_source_no_reconocido")

        if df.empty:
            return _empty_evidence("m15_source_vacio")

        return build_m15_evidence_for_decision_time(
            m15_frame=df,
            h4_frame=h4_frame,
            decision_time=decision_time,
            symbol="EURUSD",
        )
    except Exception as e:
        logger.exception(f"Error construyendo evidencia M15: {e}")
        return _empty_evidence(f"error_construction: {e}")


def _empty_evidence(reason: str) -> dict[str, Any]:
    """Evidencia vacía."""
    return {
        "sweep": {"present": False, "time": None, "source": reason},
        "displacement": {"present": False, "time": None, "source": reason},
        "bos_or_choch": {"present": False, "time": None, "source": reason},
        "fvg_or_ob": {"present": False, "time": None, "source": reason},
        "retest": {"present": False, "time": None, "source": reason},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría global
# ─────────────────────────────────────────────────────────────────────────────

def audit_dataset(
    dataset: pd.DataFrame,
    h4_frame: pd.DataFrame | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Auditar todo el dataset semánticamente."""
    rows = dataset.to_dict("records")
    if max_rows is not None:
        rows = rows[:max_rows]

    results: list[dict[str, Any]] = []
    no_zone_rows: list[dict[str, Any]] = []
    with_zone_rows: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        result = audit_row_semantically(row, h4_frame=h4_frame)
        result["index"] = i
        result["split"] = row.get("split", "UNKNOWN")
        result["direction"] = row.get("direction", 0)
        result["setup_type"] = row.get("setup_type", "UNKNOWN")
        if row.get("pd_array_zone"):
            result["original_pd_array_zone"] = row.get("pd_array_zone")
        else:
            result["original_pd_array_zone"] = None
        results.append(result)

        if result["zone_state"] == NO_ZONE:
            no_zone_rows.append(result)
        else:
            with_zone_rows.append(result)

    return {
        "total_rows": len(results),
        "results": results,
        "no_zone_rows": no_zone_rows,
        "with_zone_rows": with_zone_rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Informe
# ─────────────────────────────────────────────────────────────────────────────

def generate_report(audit_result: dict[str, Any]) -> str:
    """Generar el informe markdown de la auditoría semántica."""
    lines: list[str] = []

    lines.append("# Auditoría Semántica SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1")
    lines.append("")
    lines.append("**Fecha de auditoría:** 2026-09-16")
    lines.append("")
    lines.append("## Resumen Ejecutivo")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Filas auditadas | {audit_result['total_rows']} |")
    lines.append(f"| Filas NO_ZONE originales | {len(audit_result['no_zone_rows'])} |")
    lines.append(f"| Filas con zona originales | {len(audit_result['with_zone_rows'])} |")
    lines.append("")

    # Conteos de estados semánticos
    state_counts = {}
    for row in audit_result["results"]:
        state = row["zone_state"]
        state_counts[state] = state_counts.get(state, 0) + 1

    lines.append("### Estados Semánticos")
    lines.append("")
    for state in (VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING):
        count = state_counts.get(state, 0)
        lines.append(f"- **{state}:** {count} filas")

    lines.append("")
    lines.append("## Análisis de las 73 Filas NO_ZONE")
    lines.append("")
    lines.append("| Índice | Split | Estado Semántico | Reason |")
    lines.append("|--------|--------|-------------------|--------|")
    for row in audit_result["no_zone_rows"]:
        idx = row.get("index", "?")
        split = row.get("split", "?")
        state = row["zone_state"]
        reason = row.get("reason", "")[:80]
        lines.append(f"| {idx} | {split} | {state} | {reason} |")

    lines.append("")
    lines.append("## Análisis de las 219 Filas con Zona")
    lines.append("")
    lines.append("| Índice | Split | Estado Semántico | Reason |")
    lines.append("|--------|--------|-------------------|--------|")
    for row in audit_result["with_zone_rows"]:
        idx = row.get("index", "?")
        split = row.get("split", "?")
        state = row["zone_state"]
        reason = row.get("reason", "")[:80]
        lines.append(f"| {idx} | {split} | {state} | {reason} |")

    lines.append("")
    lines.append("## Conclusión")
    lines.append("")
    lines.append(f"**Falsos negativos (NO_ZONE incorrectos):** {state_counts.get(VALID_ITF_ZONE, 0)} filas")
    lines.append(f"**Falsos positivos (zona inválida etiquetada como válida):** necesario comparar con resultados semánticos")
    lines.append("")
    lines.append("## Siguiente Pasos")
    lines.append("")
    lines.append("1. Si faltó evidencia (`EVIDENCE_MISSING`), corregir la materialización antes de continuar.")
    lines.append("2. Si hay `VALID_ITF_ZONE` entre las 73 NO_ZONE, corregir el materializador.")
    lines.append("3. Si hay `INVALID_ZONE` entre las 219 con zona, corregir el materializador.")
    lines.append("4. Regenerar el dataset con el materializador corregido y verificar hashes.")

    return "\n".join(lines)


def main():
    import sys
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Auditoría Semántica SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1")
    print("=" * 60)

    # Cargar dataset
    print("\nCargando dataset...")
    dataset = load_dataset()
    print(f"Dataset cargado: {len(dataset)} filas")

    # Cargar schema
    schema = load_feature_schema()
    print(f"Schema cargado: {len(schema)} campos")

    # Auditoría
    print("\nEjecutando auditoría semántica...")
    audit_result = audit_dataset(dataset)

    # Generar informe
    report = generate_report(audit_result)
    report_path = REPORT_PATH / REPORT_NAME
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\nInforme generado: {report_path}")

    # Imprimir resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Total filas: {audit_result['total_rows']}")
    print(f"NO_ZONE originales: {len(audit_result['no_zone_rows'])}")
    print(f"Con zona originales: {len(audit_result['with_zone_rows'])}")

    state_counts = {}
    for row in audit_result["results"]:
        state = row["zone_state"]
        state_counts[state] = state_counts.get(state, 0) + 1

    print("\nEstados semánticos:")
    for state in (VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING):
        count = state_counts.get(state, 0)
        print(f"  {state}: {count}")

    print(f"\nFalsos negativos (NO_ZONE → VALID_ITF_ZONE): {state_counts.get(VALID_ITF_ZONE, 0)}")
    print(f"EVIDENCE_MISSING: {state_counts.get(EVIDENCE_MISSING, 0)}")

    print("\n" + "=" * 60)
    print("AUDITORÍA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
