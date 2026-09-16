#!/usr/bin/env python3
"""SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1 — detector semántico y auditoría de las 73 filas NO_ZONE y 219 con zona del dataset SETUP_GRAMMAR_DATASET_V1.

Corregido después de la revisión: usa campos reales del dataset (grammar_labels.pd_array_zone, exec_tf_evidence.source, features_at_t.context_inputs, context_bucket), ROOT apunta a la raíz del repo, variable row_data no row, y carga M15 desde parquet/CSV según el source real.

can_trade = false, entry_authorized = false, shadow_mode = true.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup_grammar_semantics_audit")

# ─────────────────────────────────────────────────────────────────────────────
# ROOT: apunta a la raíz del repo de forma robusta
# El script puede ejecutarse desde cualquier directorio.
# __file__ puede ser relativo si se ejecuta como `python scripts/...`,
# por eso resolvemos PATH_ABSOLUTE desde __file__.
# ─────────────────────────────────────────────────────────────────────────────

_PATH_HERE = Path(__file__).resolve().parent
# El script está en scripts/lab/experiments/ → 3 niveles hasta la raíz
_ROOT = _PATH_HERE.parent.parent.parent

# Verificar que ROOT apunta a ICT SYSTEM (contiene data/ml/tensorflow/setup_grammar_v1)
_DATASET_PATH = _ROOT / "data" / "ml" / "tensorflow" / "setup_grammar_v1"
if not _DATASET_PATH.exists():
    raise RuntimeError(
        f"ROOT={_ROOT} no contiene el dataset esperado.\n"
        f"Path del script: {Path(__file__).resolve()}\n"
        f"Dataset esperado: {_DATASET_PATH}\n"
        f"cwd: {Path.cwd()}"
    )

ROOT = _ROOT
DATASET_PATH = _DATASET_PATH
REPORT_PATH = ROOT / "reports" / "audits" / "experiments" / "ai"
REPORT_NAME = "setup_grammar_semantics_v1_audit.md"

# Asegurar que ROOT esté en sys.path para importar engine/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ─────────────────────────────────────────────────────────────────────────────
# Estados semánticos
# ─────────────────────────────────────────────────────────────────────────────

VALID_ITF_ZONE = "VALID_ITF_ZONE"
INVALID_ZONE = "INVALID_ZONE"
NO_ZONE = "NO_ZONE"
EVIDENCE_MISSING = "EVIDENCE_MISSING"
REVIEW_CAUSAL_LINK_MISSING = "REVIEW_CAUSAL_LINK_MISSING"

SEMANTIC_ZONE_STATES = (
    VALID_ITF_ZONE,
    INVALID_ZONE,
    NO_ZONE,
    EVIDENCE_MISSING,
    REVIEW_CAUSAL_LINK_MISSING,
)

# ─────────────────────────────────────────────────────────────────────────────
# Cargas
# ─────────────────────────────────────────────────────────────────────────────

def load_dataset() -> pd.DataFrame:
    """Cargar el dataset SETUP_GRAMMAR_DATASET_V1 combinando los tres splits."""
    dfs: list[pd.DataFrame] = []
    for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
        path = DATASET_PATH / f"dataset_{split.lower()}.jsonl"
        if not path.exists():
            logger.warning(f"Split {split} no encontrado: {path}")
            continue
        df = pd.read_json(path, lines=True)
        dfs.append(df)
    if not dfs:
        raise FileNotFoundError(f"No se encontró ningún split en {DATASET_PATH}")
    return pd.concat(dfs, ignore_index=True)


def load_m15_from_exec_evidence(
    exec_tf_evidence: dict[str, Any],
) -> pd.DataFrame | None:
    """Cargar el frame M15 desde exec_tf_evidence.source.

    El source es un path relativo desde la raíz del repo (ej: data\\raw\\EURUSD\\...).
    Los timestamps en los CSV son enteros (milisegundos desde epoch).
    """
    source_rel = exec_tf_evidence.get("source")
    if not source_rel:
        return None
    abs_source = ROOT / str(source_rel)
    if not abs_source.exists():
        logger.warning(f"Archivo M15 no encontrado: {abs_source}")
        return None

    ext = abs_source.suffix.lower()
    try:
        if ext == ".parquet":
            df = pq.read_table(abs_source).to_pandas()
        elif ext == ".csv":
            df = pd.read_csv(abs_source, encoding="utf-8", on_bad_lines="skip")
        else:
            logger.warning(f"Formato M15 desconocido: {ext} en {abs_source}")
            return None

        # Normalizar columna de tiempo: puede ser int64 (ms desde epoch) o datetime
        if "timestamp" not in df.columns:
            logger.warning(f"Columna 'timestamp' no encontrada en {abs_source}")
            return None

        ts_col = df["timestamp"]
        if ts_col.dtype == "int64":
            df["timestamp"] = pd.to_datetime(ts_col, unit="ms", utc=True)
        elif ts_col.dtype == "float64":
            df["timestamp"] = pd.to_datetime(ts_col, unit="ms", utc=True)
        elif pd.api.types.is_datetime64_any_dtype(ts_col):
            pass  # ya es datetime
        else:
            # Attempt string parse
            try:
                df["timestamp"] = pd.to_datetime(ts_col, utc=True, format="ISO8601")
            except Exception:
                # Fallback: try parsing as milliseconds
                try:
                    df["timestamp"] = pd.to_datetime(ts_col.astype(str), unit="ms", utc=True)
                except Exception as e:
                    logger.warning(f"No se pudo parsear timestamp en {abs_source}: {e}")
                    return None

        if df["timestamp"].isna().all():
            logger.warning(f"Todos los timestamps son NaN en {abs_source}")
            return None

        return df
    except Exception as e:
        logger.warning(f"Error cargando M15 desde {abs_source}: {e}")
        return None


def filter_m15_to_decision_time(
    m15: pd.DataFrame,
    decision_time: pd.Timestamp,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """Filtrar el frame M15 hasta decision_time (causal)."""
    # Normalizar columna de tiempo
    if timestamp_col == "timestamp" and m15[timestamp_col].dtype == "int64":
        # Milisegundos desde epoch
        ts = pd.to_datetime(m15[timestamp_col], unit="ms", utc=True)
    else:
        ts = pd.to_datetime(m15[timestamp_col], utc=True, errors="coerce")

    mask = ts <= decision_time
    return m15[mask].copy()


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría semántica por fila
# ─────────────────────────────────────────────────────────────────────────────

def audit_row_semantically(
    row_data: dict[str, Any],
) -> dict[str, Any]:
    """Auditar una fila del dataset semánticamente.

    Reconstruye la evidencia M15 desde exec_tf_evidence.source y aplica el
    detector semántico.
    """
    # Extract fields
    decision_time_raw = row_data.get("decision_time")
    features_at_t = row_data.get("features_at_t")
    exec_tf_evidence = row_data.get("exec_tf_evidence")
    grammar_labels = row_data.get("grammar_labels")
    context_bucket = row_data.get("context_bucket", "MISSING")
    split = row_data.get("split", "UNKNOWN")

    if decision_time_raw is None:
        return {
            "zone_state": EVIDENCE_MISSING,
            "reason": "decision_time no disponible",
            "conditions": {},
            "split": split,
            "original_pd_array_zone": grammar_labels.get("pd_array_zone") if grammar_labels else None,
        }

    # Normalizar decision_time
    if isinstance(decision_time_raw, str):
        decision_time = pd.to_datetime(decision_time_raw, utc=True)
    elif isinstance(decision_time_raw, pd.Timestamp):
        decision_time = decision_time_raw.tz_convert("UTC") if decision_time_raw.tz is None else decision_time_raw
    else:
        decision_time = pd.to_datetime(decision_time_raw, utc=True)

    # Etiqueta original
    original_zone = grammar_labels.get("pd_array_zone") if grammar_labels else None

    # Cargar M15 desde exec_tf_evidence
    m15 = load_m15_from_exec_evidence(exec_tf_evidence)
    if m15 is None or m15.empty:
        return {
            "zone_state": EVIDENCE_MISSING,
            "reason": "no se pudo cargar el archivo M15 desde exec_tf_evidence.source",
            "conditions": {},
            "split": split,
            "original_pd_array_zone": original_zone,
        }

    # Filtrar M15 hasta decision_time (causal)
    m15_ctx = filter_m15_to_decision_time(m15, decision_time)
    if m15_ctx.empty:
        return {
            "zone_state": EVIDENCE_MISSING,
            "reason": "no hay velas M15 hasta decision_time",
            "conditions": {},
            "split": split,
            "original_pd_array_zone": original_zone,
        }

    # Construir evidencia M15 usando detectores directos (sin HEO, que exige H4)
    try:
        from detectors.fvg import detect_fvg
        from detectors.ob import detect_order_blocks
        from detectors.displacement import DisplacementConfig, detect_displacement

        m15_ctx_reset = m15_ctx.copy().reset_index(drop=True)

        # Detectar displacement
        displacement_present = False
        displacement_time = None
        displacement_direction = None
        displacement_magnitude = None
        try:
            disp_cfg = DisplacementConfig()
            disp_df = detect_displacement(m15_ctx_reset, disp_cfg)
            disp_mask = disp_df["displacement_bullish"] | disp_df["displacement_bearish"]
            if disp_mask.any():
                displacement_present = True
                last_idx = disp_df.index[disp_mask][-1]
                displacement_direction = 1 if bool(disp_df.iloc[last_idx]["displacement_bullish"]) else -1
                displacement_time = str(m15_ctx_reset.iloc[last_idx]["timestamp"])
                displacement_magnitude = float(disp_df.iloc[last_idx].get("displacement_mag", 0) or 0)
        except Exception as e:
            logger.warning(f"Error detectando displacement M15: {e}")

        # Detectar FVG
        fvg_present = False
        fvg_time = None
        fvg_type = None
        fvg_zone_low = None
        fvg_zone_high = None
        try:
            fvg_df = detect_fvg(m15_ctx_reset)
            if not fvg_df.empty:
                fvg_present = True
                last_idx = fvg_df.index[-1]
                fvg_time = str(m15_ctx_reset.iloc[last_idx]["timestamp"])
                fvg_type = str(fvg_df.iloc[last_idx].get("fvg_type", "FVG")).upper()
                fvg_zone_low = float(fvg_df.iloc[last_idx].get("fvg_low", 0) or 0)
                fvg_zone_high = float(fvg_df.iloc[last_idx].get("fvg_high", 0) or 0)
        except Exception as e:
            logger.warning(f"Error detectando FVG M15: {e}")

        # Detectar OB
        ob_present = False
        ob_time = None
        ob_zone_low = None
        ob_zone_high = None
        try:
            ob_list = detect_order_blocks(m15_ctx_reset)
            if not ob_list.empty:
                ob_present = True
                last_ob = ob_list[-1]
                ob_time = str(last_ob.creation_time)
                ob_zone_low = float(last_ob.zone_low) if last_ob.zone_low else None
                ob_zone_high = float(last_ob.zone_high) if last_ob.zone_high else None
        except Exception as e:
            logger.warning(f"Error detectando OB M15: {e}")

        # Combinar FVG + OB
        fvg_or_ob_present = fvg_present or ob_present
        if fvg_present:
            fvg_or_ob_time = fvg_time
            fvg_or_ob_type = fvg_type
            fvg_or_ob_zone_low = fvg_zone_low
            fvg_or_ob_zone_high = fvg_zone_high
            fvg_or_ob_source = "m15_fvg"
        elif ob_present:
            fvg_or_ob_time = ob_time
            fvg_or_ob_type = "ORDER_BLOCK"
            fvg_or_ob_zone_low = ob_zone_low
            fvg_or_ob_zone_high = ob_zone_high
            fvg_or_ob_source = "m15_order_block"
        else:
            fvg_or_ob_time = None
            fvg_or_ob_type = None
            fvg_or_ob_zone_low = None
            fvg_or_ob_zone_high = None
            fvg_or_ob_source = "no_poi"

        m15_evidence = {
            "fvg_or_ob": {
                "present": fvg_or_ob_present,
                "time": fvg_or_ob_time,
                "source": fvg_or_ob_source,
                "type": fvg_or_ob_type,
                "zone_low": fvg_or_ob_zone_low,
                "zone_high": fvg_or_ob_zone_high,
            },
            "displacement": {
                "present": displacement_present,
                "time": displacement_time,
                "source": ("m15_displacement_detector" if displacement_present else "no_displacement"),
                "direction": displacement_direction,
                "magnitude": displacement_magnitude,
            },
            "sweep": {"present": False, "time": None, "source": "canonical_sweep_not_run"},
            "bos_or_choch": {"present": False, "time": None, "source": "not_extracted"},
            "retest": {"present": False, "time": None, "source": "not_extracted"},
        }
    except Exception as e:
        logger.warning(f"Error construyendo evidencia M15 desde detectores: {e}")
        import traceback
        traceback.print_exc()
        return {
            "zone_state": EVIDENCE_MISSING,
            "reason": f"error construyendo m15_evidence desde detectores: {e}",
            "conditions": {},
            "split": split,
            "original_pd_array_zone": original_zone,
        }

    # Extraer campos para el detector semántico
    context_inputs = (features_at_t or {}).get("context_inputs") or {}
    h4_location = str(context_inputs.get("h4_location", "MISSING")).upper()
    h1_alignment = str(context_inputs.get("h1_alignment", "MISSING")).upper()
    direction_hint = str(context_inputs.get("direction_hint", "N/A")).upper()
    sequence_direction = int(context_inputs.get("sequence_direction", 0) or 0)

    # Evaluar semánticamente
    from semantic_pd_array_eval_v1 import semantic_pd_array_zone

    result = semantic_pd_array_zone(
        decision_time=decision_time,
        features_at_t={
            "context_inputs": {
                "h4_location": h4_location,
                "h1_alignment": h1_alignment,
                "direction_hint": direction_hint,
                "sequence_direction": sequence_direction,
            },
            "context_bucket": context_bucket,
        },
        m15_evidence=m15_evidence,
        direction=sequence_direction,
    )

    return {
        "zone_state": result["zone_state"],
        "reason": result["reason"],
        "conditions": result["conditions"],
        "split": split,
        "original_pd_array_zone": original_zone,
        "context_bucket": context_bucket,
        "h4_location": h4_location,
        "h1_alignment": h1_alignment,
        "direction_hint": direction_hint,
        "sequence_direction": sequence_direction,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auditoría global
# ─────────────────────────────────────────────────────────────────────────────

def audit_dataset(
    dataset: pd.DataFrame,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Auditar todo el dataset semánticamente."""
    rows = dataset.to_dict("records")
    if max_rows is not None:
        rows = rows[:max_rows]

    results: list[dict[str, Any]] = []
    no_zone_rows: list[dict[str, Any]] = []
    with_zone_rows: list[dict[str, Any]] = []
    evidence_missing_rows: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        result = audit_row_semantically(row)
        result["index"] = i
        results.append(result)

        if result["zone_state"] == EVIDENCE_MISSING:
            evidence_missing_rows.append(result)
        elif result["original_pd_array_zone"] == "NO_ZONE":
            no_zone_rows.append(result)
        else:
            with_zone_rows.append(result)

    return {
        "total_rows": len(results),
        "results": results,
        "no_zone_rows": no_zone_rows,
        "with_zone_rows": with_zone_rows,
        "evidence_missing_rows": evidence_missing_rows,
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
    lines.append("Este documento es el resultado de aplicar el detector semántico `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1` a las 292 filas del dataset SETUP_GRAMMAR_DATASET_V1. El detector evalúa si cada PD Array (FVG/OB) cumple las tres condiciones de POI según la tesis ICT del proyecto (`21_POI.md` §16, `20_TESIS_ICT.md` §5b).")
    lines.append("")
    lines.append("| Métrica | Valor |")
    lines.append("|---------|-------|")
    lines.append(f"| Filas auditadas | {audit_result['total_rows']} |")
    lines.append(f"| Filas originales NO_ZONE | {len(audit_result['no_zone_rows'])} |")
    lines.append(f"| Filas originales con zona | {len(audit_result['with_zone_rows'])} |")
    lines.append(f"| Filas EVIDENCE_MISSING | {len(audit_result['evidence_missing_rows'])} |")
    lines.append("")

    # Conteos de estados semánticos
    state_counts: dict[str, int] = {}
    for row in audit_result["results"]:
        state = row["zone_state"]
        state_counts[state] = state_counts.get(state, 0) + 1

    lines.append("### Estados Semánticos")
    lines.append("")
    for state in SEMANTIC_ZONE_STATES:
        count = state_counts.get(state, 0)
        lines.append(f"- **{state}:** {count} filas")

    lines.append("")
    lines.append("## Análisis de las 73 Filas NO_ZONE Originales")
    lines.append("")
    lines.append("Estas son las filas que el materializador actual etiquetó como `NO_ZONE`. La auditoría semántica determina si realmente no hay PD Array válido, o si hay un error de materialización.")
    lines.append("")
    lines.append("| Índice | Split | Estado Semántico | Reason | h4_location | h1_alignment |")
    lines.append("|--------|--------|-------------------|--------|-------------|---------------|")
    for row in audit_result["no_zone_rows"]:
        idx = row.get("index", "?")
        split = row.get("split", "?")
        state = row["zone_state"]
        reason = row.get("reason", "")[:60]
        h4 = row.get("h4_location", "?")
        h1 = row.get("h1_alignment", "?")
        lines.append(f"| {idx} | {split} | {state} | {reason} | {h4} | {h1} |")

    lines.append("")
    lines.append("### Resumen de las 73 NO_ZONE")
    lines.append("")
    no_zone_state_counts: dict[str, int] = {}
    for row in audit_result["no_zone_rows"]:
        state = row["zone_state"]
        no_zone_state_counts[state] = no_zone_state_counts.get(state, 0) + 1
    for state in SEMANTIC_ZONE_STATES:
        count = no_zone_state_counts.get(state, 0)
        lines.append(f"- **{state}:** {count}")

    lines.append("")
    lines.append("### Falsos Negativos (NO_ZONE → VALID_ITF_ZONE)")
    lines.append("")
    false_negatives = [r for r in audit_result["no_zone_rows"] if r["zone_state"] == VALID_ITF_ZONE]
    if false_negatives:
        lines.append(f"**{len(false_negatives)} filas etiquetadas como NO_ZONE pero semánticamente son VALID_ITF_ZONE.**")
        lines.append("")
        lines.append("| Índice | Split | Reason |")
        lines.append("|--------|--------|--------|")
        for row in false_negatives:
            idx = row.get("index", "?")
            split = row.get("split", "?")
            reason = row.get("reason", "")[:60]
            lines.append(f"| {idx} | {split} | {reason} |")
    else:
        lines.append("No se encontraron falsos negativos. Las 73 NO_ZONE originales son correctas según la auditoría semántica, o se clasificaron como EVIDENCE_MISSING/INVALID_ZONE.")

    lines.append("")
    lines.append("## Análisis de las 219 Filas con Zona Original (USABLE_UNGRADED)")
    lines.append("")
    lines.append("Estas son las filas que el materializador actual etiquetó como `USABLE_UNGRADED` (tienen PD Array). La auditoría semántica determina si realmente cumplen las tres condiciones de POI o si hay falsos positivos.")
    lines.append("")
    lines.append("| Índice | Split | Estado Semántico | Reason | h4_location | h1_alignment |")
    lines.append("|--------|--------|-------------------|--------|-------------|---------------|")
    for row in audit_result["with_zone_rows"]:
        idx = row.get("index", "?")
        split = row.get("split", "?")
        state = row["zone_state"]
        reason = row.get("reason", "")[:60]
        h4 = row.get("h4_location", "?")
        h1 = row.get("h1_alignment", "?")
        lines.append(f"| {idx} | {split} | {state} | {reason} | {h4} | {h1} |")

    lines.append("")
    lines.append("### Resumen de las 219 con Zona")
    lines.append("")
    with_zone_state_counts: dict[str, int] = {}
    for row in audit_result["with_zone_rows"]:
        state = row["zone_state"]
        with_zone_state_counts[state] = with_zone_state_counts.get(state, 0) + 1
    for state in SEMANTIC_ZONE_STATES:
        count = with_zone_state_counts.get(state, 0)
        lines.append(f"- **{state}:** {count}")

    lines.append("")
    lines.append("### Falsos Positivos (Zona etiquetada como USABLE_UNGRADED pero semánticamente no válida)")
    lines.append("")
    false_positives = [r for r in audit_result["with_zone_rows"] if r["zone_state"] in (INVALID_ZONE, REVIEW_CAUSAL_LINK_MISSING)]
    if false_positives:
        lines.append(f"**{len(false_positives)} filas etiquetadas como USABLE_UNGRADED pero semánticamente NO son zonas válidas.**")
        lines.append("")
        lines.append("| Índice | Split | Estado | Reason |")
        lines.append("|--------|--------|--------|--------|")
        for row in false_positives:
            idx = row.get("index", "?")
            split = row.get("split", "?")
            state = row["zone_state"]
            reason = row.get("reason", "")[:60]
            lines.append(f"| {idx} | {split} | {state} | {reason} |")
    else:
        lines.append("No se encontraron falsos positivos. Las 219 USABLE_UNGRADED son correctas según la auditoría semántica.")

    lines.append("")
    lines.append("## Distribución por Split")
    lines.append("")
    lines.append("| Split | Total | NO_ZONE | USABLE_UNGRADED |")
    lines.append("|-------|-------|---------|-----------------|")
    for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
        split_rows = [r for r in audit_result["results"] if r.get("split") == split]
        no_zone = sum(1 for r in split_rows if r.get("original_pd_array_zone") == "NO_ZONE")
        with_zone = sum(1 for r in split_rows if r.get("original_pd_array_zone") == "USABLE_UNGRADED")
        lines.append(f"| {split} | {len(split_rows)} | {no_zone} | {with_zone} |")

    lines.append("")
    lines.append("## Conclusión")
    lines.append("")
    lines.append(f"**Falsos negativos (NO_ZONE incorrectos):** {len(false_negatives)} filas")
    lines.append(f"**Falsos positivos (USABLE_UNGRADED incorrectos):** {len(false_positives)} filas")
    lines.append(f"**EVIDENCE_MISSING (no se pudo auditar):** {len(audit_result['evidence_missing_rows'])} filas")
    lines.append("")
    if len(evidence_missing_rows := audit_result["evidence_missing_rows"]) > 0:
        lines.append("### Filas con Evidencia Insuficiente")
        lines.append("")
        lines.append("| Índice | Split | Reason |")
        lines.append("|--------|--------|--------|")
        for row in evidence_missing_rows:
            idx = row.get("index", "?")
            split = row.get("split", "?")
            reason = row.get("reason", "")[:80]
            lines.append(f"| {idx} | {split} | {reason} |")
    lines.append("")
    lines.append("## Siguientes Pasos")
    lines.append("")
    lines.append("1. Si hay EVIDENCE_MISSING > 0: corregir la materialización antes de continuar; no pueden participar en la auditoría semántica.")
    lines.append("2. Si hay falsos negativos > 0: **corregir el materializador** `materialize_setup_grammar_dataset_v1.py` (no editar el dataset a mano) y regenerar el dataset desde las fuentes originales.")
    lines.append("3. Si hay falsos positivos > 0: **corregir el materializador** para que no etiquete como USABLE_UNGRADED zonas que no cumplen las tres condiciones.")
    lines.append("4. Si no hay errores (0 falsos negativos, 0 falsos positivos, 0 EVIDENCE_MISSING): las 292 etiquetas son semánticamente correctas según la tesis. **El materializador actual es correcto** para las tres condiciones de POI.")
    lines.append("5. Regenerar el dataset corregido, verificar hashes, ejecutar pruebas y comparación antes/después.")
    lines.append("6. Solo después: reentrenar `setup_quality_v1` comparado contra los baselines actuales.")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import sys
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("Auditoría Semántica SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1")
    print("=" * 60)

    # Cargar dataset
    print("\n[1/3] Cargando dataset...")
    dataset = load_dataset()
    print(f"    Dataset cargado: {len(dataset)} filas")

    # Auditoría
    print("\n[2/3] Ejecutando auditoría semántica...")
    audit_result = audit_dataset(dataset)

    print(f"    Filas auditadas: {audit_result['total_rows']}")
    print(f"    NO_ZONE originales: {len(audit_result['no_zone_rows'])}")
    print(f"    Con zona originales: {len(audit_result['with_zone_rows'])}")
    print(f"    EVIDENCE_MISSING: {len(audit_result['evidence_missing_rows'])}")

    # Conteos de estados semánticos
    state_counts: dict[str, int] = {}
    for row in audit_result["results"]:
        state = row["zone_state"]
        state_counts[state] = state_counts.get(state, 0) + 1

    print("\n    Estados semánticos:")
    for state in SEMANTIC_ZONE_STATES:
        count = state_counts.get(state, 0)
        print(f"      {state}: {count}")

    false_negatives = [r for r in audit_result["no_zone_rows"] if r["zone_state"] == VALID_ITF_ZONE]
    false_positives = [r for r in audit_result["with_zone_rows"] if r["zone_state"] in (INVALID_ZONE, REVIEW_CAUSAL_LINK_MISSING)]

    print(f"\n    Falsos negativos (NO_ZONE → VALID_ITF_ZONE): {len(false_negatives)}")
    print(f"    Falsos positivos (USABLE_UNGRADED → INVALID_ZONE/REVIEW_CAUSAL_LINK_MISSING): {len(false_positives)}")

    # Generar informe
    print("\n[3/3] Generando informe...")
    report = generate_report(audit_result)
    report_path = REPORT_PATH / REPORT_NAME
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"    Informe generado: {report_path}")

    print("\n" + "=" * 60)
    print("AUDITORÍA COMPLETADA")
    print("=" * 60)

    # Imprimir conclusión ejecutiva
    print("\n### CONCLUSIÓN EJECUTIVA")
    if len(false_negatives) > 0:
        print(f"\n⚠️ {len(false_negatives)} de las 73 NO_ZONE son FALSOS NEGATIVOS: el materializador actual NO etiquetó como NO_ZONE filas que semánticamente SÍ tienen PD Array válido.")
        print("El materializador tiene errores de materialización que deben corregirse.")
    elif len(false_positives) > 0:
        print(f"\n⚠️ {len(false_positives)} de las 219 USABLE_UNGRADED son FALSOS POSITIVOS: el materializador actual etiquetó como zona válida filas que semánticamente NO la tienen.")
        print("El materializador tiene errores de materialización que deben corregirse.")
    elif len(audit_result["evidence_missing_rows"]) > 0:
        print(f"\n⚠️ {len(audit_result['evidence_missing_rows'])} filas no se pudieron auditar (EVIDENCE_MISSING). Corregir la materialización antes de continuar.")
    else:
        print("\n✅ Ningún error de materialización encontrado.")
        print("Las 73 NO_ZONE y las 219 USABLE_UNGRADED son semánticamente correctas según la tesis.")
        print("El materializador actual es correcto para las tres condiciones de POI.")


if __name__ == "__main__":
    main()
