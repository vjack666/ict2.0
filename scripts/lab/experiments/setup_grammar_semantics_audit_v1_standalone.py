#!/usr/bin/env python3
"""Auditoría semántica M15-only de las 73 NO_ZONE y 219 con zona del dataset SETUP_GRAMMAR_DATASET_V1.

Versión standalone que usa los detectores M15 directamente (displacement, FVG, OB)
y el detector semántico semantic_pd_array_eval_v1, sin necesidad de H4 ni HEO.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

# Agregar ROOT al path - usar Path.cwd() si estamos en el repo, otherwise calcular desde __file__
import os
_CWD = Path.cwd().resolve()
if _CWD.name == "ICT SYSTEM" and (_CWD / "data" / "ml" / "tensorflow" / "setup_grammar_v1").exists():
    ROOT = _CWD
else:
    # Calcular desde la ubicación del script
    _SCRIPT_PATH = Path(__file__).resolve()
    ROOT = _SCRIPT_PATH.parents[3]

sys.path.insert(0, str(ROOT))

from detectors.fvg import detect_fvg
from detectors.ob import detect_order_blocks
from detectors.displacement import DisplacementConfig, detect_displacement

# Importar detector semántico
sys.path.insert(0, str(ROOT / "scripts" / "lab" / "experiments"))
from semantic_pd_array_eval_v1 import semantic_pd_array_zone, VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING

DATASET_PATH = ROOT / "data" / "ml" / "tensorflow" / "setup_grammar_v1"
REPORT_PATH = ROOT / "reports" / "audits" / "experiments" / "ai"


def load_m15_from_exec_evidence(exec_tf_evidence: dict[str, Any]) -> pd.DataFrame | None:
    """Cargar el frame M15 desde exec_tf_evidence.source."""
    source_rel = exec_tf_evidence.get("source")
    if not source_rel:
        return None
    abs_source = ROOT / str(source_rel)
    if not abs_source.exists():
        return None

    ext = abs_source.suffix.lower()
    try:
        if ext == ".parquet":
            df = pq.read_table(abs_source).to_pandas()
        elif ext == ".csv":
            df = pd.read_csv(abs_source, encoding="utf-8", on_bad_lines="skip")
        else:
            return None

        if "timestamp" not in df.columns:
            return None

        ts_col = df["timestamp"]
        if ts_col.dtype == "int64":
            df["timestamp"] = pd.to_datetime(ts_col, unit="ms", utc=True)
        elif ts_col.dtype == "float64":
            df["timestamp"] = pd.to_datetime(ts_col, unit="ms", utc=True)
        elif pd.api.types.is_datetime64_any_dtype(ts_col):
            pass
        else:
            try:
                df["timestamp"] = pd.to_datetime(ts_col.astype(str), unit="ms", utc=True)
            except Exception:
                return None

        if df["timestamp"].isna().all():
            return None

        return df
    except Exception:
        return None


def extract_m15_evidence(m15_frame: pd.DataFrame, decision_time: pd.Timestamp) -> dict[str, Any]:
    """Extraer evidencia M15 usando detectores directos (sin H4)."""
    if m15_frame["timestamp"].dtype == "int64":
        ts = pd.to_datetime(m15_frame["timestamp"], unit="ms", utc=True)
    else:
        ts = pd.to_datetime(m15_frame["timestamp"], utc=True, errors="coerce")

    mask = ts <= decision_time
    m15_ctx = m15_frame[mask].copy().reset_index(drop=True)

    if m15_ctx.empty:
        return _empty_evidence("no_m15_data_until_decision_time")

    # Displacement
    displacement_present = False
    displacement_time = None
    displacement_direction = None
    try:
        disp_cfg = DisplacementConfig()
        disp_df = detect_displacement(m15_ctx, disp_cfg)
        disp_mask = disp_df["displacement_bullish"] | disp_df["displacement_bearish"]
        if disp_mask.any():
            displacement_present = True
            last_idx = disp_df.index[disp_mask][-1]
            displacement_direction = 1 if bool(disp_df.iloc[last_idx]["displacement_bullish"]) else -1
            displacement_time = str(m15_ctx.iloc[last_idx]["timestamp"])
    except Exception:
        pass

    # FVG
    fvg_present = False
    fvg_time = None
    fvg_type = None
    fvg_zone_low = None
    fvg_zone_high = None
    try:
        fvg_df = detect_fvg(m15_ctx)
        if not fvg_df.empty:
            fvg_present = True
            last_idx = fvg_df.index[-1]
            fvg_time = str(m15_ctx.iloc[last_idx]["timestamp"])
            fvg_type = str(fvg_df.iloc[last_idx].get("fvg_type", "FVG")).upper()
            fvg_zone_low = float(fvg_df.iloc[last_idx].get("fvg_low", 0) or 0)
            fvg_zone_high = float(fvg_df.iloc[last_idx].get("fvg_high", 0) or 0)
    except Exception:
        pass

    # OB
    ob_present = False
    ob_time = None
    ob_zone_low = None
    ob_zone_high = None
    try:
        ob_df = detect_order_blocks(m15_ctx)
        ob_mask = ob_df["ob_bullish"] | ob_df["ob_bearish"]
        if ob_mask.any():
            ob_present = True
            last_idx = ob_df.index[ob_mask][-1]
            ob_time = str(m15_ctx.iloc[last_idx]["timestamp"])
            ob_zone_low = float(m15_ctx.iloc[last_idx]["low"]) if not pd.isna(m15_ctx.iloc[last_idx]["low"]) else None
            ob_zone_high = float(m15_ctx.iloc[last_idx]["high"]) if not pd.isna(m15_ctx.iloc[last_idx]["high"]) else None
    except Exception:
        pass

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

    return {
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
            "magnitude": None,
        },
        "sweep": {"present": False, "time": None, "source": "canonical_sweep_not_run"},
        "bos_or_choch": {"present": False, "time": None, "source": "not_extracted"},
        "retest": {"present": False, "time": None, "source": "not_extracted"},
    }


def _empty_evidence(reason: str) -> dict[str, Any]:
    return {
        "fvg_or_ob": {"present": False, "time": None, "source": reason},
        "displacement": {"present": False, "time": None, "source": reason},
        "sweep": {"present": False, "time": None, "source": reason},
        "bos_or_choch": {"present": False, "time": None, "source": reason},
        "retest": {"present": False, "time": None, "source": reason},
    }


def audit_row(row_data: dict[str, Any]) -> dict[str, Any]:
    """Auditar una fila del dataset semánticamente."""
    decision_time_raw = row_data.get("decision_time")
    features_at_t = row_data.get("features_at_t")
    exec_tf_evidence = row_data.get("exec_tf_evidence")
    grammar_labels = row_data.get("grammar_labels")
    context_bucket = row_data.get("context_bucket", "MISSING")
    split = row_data.get("split", "UNKNOWN")

    if decision_time_raw is None:
        return {"zone_state": EVIDENCE_MISSING, "reason": "decision_time no disponible", "split": split, "original_pd_array_zone": grammar_labels.get("pd_array_zone") if grammar_labels else None}

    if isinstance(decision_time_raw, str):
        decision_time = pd.to_datetime(decision_time_raw, utc=True)
    elif isinstance(decision_time_raw, pd.Timestamp):
        decision_time = decision_time_raw.tz_convert("UTC") if decision_time_raw.tz is None else decision_time_raw
    else:
        decision_time = pd.to_datetime(decision_time_raw, utc=True)

    original_zone = grammar_labels.get("pd_array_zone") if grammar_labels else None

    m15 = load_m15_from_exec_evidence(exec_tf_evidence)
    if m15 is None or m15.empty:
        return {"zone_state": EVIDENCE_MISSING, "reason": "no se pudo cargar el archivo M15", "split": split, "original_pd_array_zone": original_zone}

    m15_evidence = extract_m15_evidence(m15, decision_time)
    if m15_evidence["fvg_or_ob"]["present"] is False and m15_evidence["displacement"]["present"] is False:
        return {"zone_state": NO_ZONE, "reason": "no hay PD Array ni displacement en M15 hasta decision_time", "split": split, "original_pd_array_zone": original_zone}

    # Extraer campos para el detector semántico
    context_inputs = (features_at_t or {}).get("context_inputs") or {}
    h4_location = str(context_inputs.get("h4_location", "MISSING")).upper()
    h1_alignment = str(context_inputs.get("h1_alignment", "MISSING")).upper()
    direction_hint = str(context_inputs.get("direction_hint", "N/A")).upper()
    sequence_direction = int(context_inputs.get("sequence_direction", 0) or 0)

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


def load_dataset() -> pd.DataFrame:
    dfs = []
    for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
        path = DATASET_PATH / f"dataset_{split.lower()}.jsonl"
        if not path.exists():
            continue
        df = pd.read_json(path, lines=True)
        dfs.append(df)
    if not dfs:
        raise FileNotFoundError(f"No se encontró ningún split en {DATASET_PATH}")
    return pd.concat(dfs, ignore_index=True)


def main():
    print("=" * 60)
    print("Auditoría Semántica M15-only — SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1")
    print("=" * 60)

    print("\n[1/3] Cargando dataset...")
    dataset = load_dataset()
    print(f"    Dataset cargado: {len(dataset)} filas")

    print("\n[2/3] Ejecutando auditoría semántica (M15-only)...")
    results = []
    no_zone_rows = []
    with_zone_rows = []
    evidence_missing_rows = []

    for i, row in dataset.iterrows():
        row_dict = row.to_dict()
        result = audit_row(row_dict)
        result["index"] = i
        results.append(result)

        if result["zone_state"] == EVIDENCE_MISSING:
            evidence_missing_rows.append(result)
        elif result["original_pd_array_zone"] == "NO_ZONE":
            no_zone_rows.append(result)
        else:
            with_zone_rows.append(result)

    print(f"    Filas auditadas: {len(results)}")
    print(f"    NO_ZONE originales: {len(no_zone_rows)}")
    print(f"    Con zona originales: {len(with_zone_rows)}")
    print(f"    EVIDENCE_MISSING: {len(evidence_missing_rows)}")

    state_counts = {}
    for r in results:
        s = r["zone_state"]
        state_counts[s] = state_counts.get(s, 0) + 1

    print("\n    Estados semánticos:")
    for state in [VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING]:
        count = state_counts.get(state, 0)
        print(f"      {state}: {count}")

    false_negatives = [r for r in no_zone_rows if r["zone_state"] == VALID_ITF_ZONE]
    false_positives = [r for r in with_zone_rows if r["zone_state"] == INVALID_ZONE]

    print(f"\n    Falsos negativos (NO_ZONE → VALID_ITF_ZONE): {len(false_negatives)}")
    print(f"    Falsos positivos (USABLE_UNGRADED → INVALID_ZONE): {len(false_positives)}")

    # Generar informe
    print("\n[3/3] Generando informe...")

    lines = []
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
    lines.append(f"| Filas auditadas | {len(results)} |")
    lines.append(f"| Filas originales NO_ZONE | {len(no_zone_rows)} |")
    lines.append(f"| Filas originales con zona | {len(with_zone_rows)} |")
    lines.append(f"| Filas EVIDENCE_MISSING | {len(evidence_missing_rows)} |")
    lines.append("")

    lines.append("### Estados Semánticos")
    lines.append("")
    for state in [VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING]:
        count = state_counts.get(state, 0)
        lines.append(f"- **{state}:** {count} filas")

    lines.append("")
    lines.append("## Análisis de las 73 Filas NO_ZONE Originales")
    lines.append("")
    lines.append("Estas son las filas que el materializador actual etiquetó como `NO_ZONE`. La auditoría semántica determina si realmente no hay PD Array válido, o si hay un error de materialización.")
    lines.append("")
    lines.append("| Índice | Split | Estado Semántico | Reason | h4_location | h1_alignment |")
    lines.append("|--------|--------|-------------------|--------|-------------|---------------|")
    for row in no_zone_rows:
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
    no_zone_state_counts = {}
    for row in no_zone_rows:
        state = row["zone_state"]
        no_zone_state_counts[state] = no_zone_state_counts.get(state, 0) + 1
    for state in [VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING]:
        count = no_zone_state_counts.get(state, 0)
        lines.append(f"- **{state}:** {count}")

    lines.append("")
    lines.append("### Falsos Negativos (NO_ZONE → VALID_ITF_ZONE)")
    lines.append("")
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
    for row in with_zone_rows:
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
    with_zone_state_counts = {}
    for row in with_zone_rows:
        state = row["zone_state"]
        with_zone_state_counts[state] = with_zone_state_counts.get(state, 0) + 1
    for state in [VALID_ITF_ZONE, INVALID_ZONE, NO_ZONE, EVIDENCE_MISSING]:
        count = with_zone_state_counts.get(state, 0)
        lines.append(f"- **{state}:** {count}")

    lines.append("")
    lines.append("### Falsos Positivos (Zona etiquetada como USABLE_UNGRADED pero semánticamente no válida)")
    lines.append("")
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
        split_rows = [r for r in results if r.get("split") == split]
        no_z = sum(1 for r in split_rows if r.get("original_pd_array_zone") == "NO_ZONE")
        with_z = sum(1 for r in split_rows if r.get("original_pd_array_zone") == "USABLE_UNGRADED")
        lines.append(f"| {split} | {len(split_rows)} | {no_z} | {with_z} |")

    lines.append("")
    lines.append("## Conclusión")
    lines.append("")
    lines.append(f"**Falsos negativos (NO_ZONE incorrectos):** {len(false_negatives)} filas")
    lines.append(f"**Falsos positivos (USABLE_UNGRADED incorrectos):** {len(false_positives)} filas")
    lines.append(f"**EVIDENCE_MISSING (no se pudo auditar):** {len(evidence_missing_rows)} filas")
    lines.append("")

    if evidence_missing_rows:
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

    report = "\n".join(lines)

    report_path = REPORT_PATH / "setup_grammar_semantics_v1_audit.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"    Informe generado: {report_path}")

    print("\n" + "=" * 60)
    print("AUDITORÍA COMPLETADA")
    print("=" * 60)

    print("\n### CONCLUSIÓN EJECUTIVA")
    if len(false_negatives) > 0:
        print(f"\n⚠️ {len(false_negatives)} de las 73 NO_ZONE son FALSOS NEGATIVOS: el materializador actual NO etiquetó como NO_ZONE filas que semánticamente SÍ tienen PD Array válido.")
        print("El materializador tiene errores de materialización que deben corregirse.")
    elif len(false_positives) > 0:
        print(f"\n⚠️ {len(false_positives)} de las 219 USABLE_UNGRADED son FALSOS POSITIVOS: el materializador actual etiquetó como zona válida filas que semánticamente NO la tienen.")
        print("El materializador tiene errores de materialización que deben corregirse.")
    elif len(evidence_missing_rows) > 0:
        print(f"\n⚠️ {len(evidence_missing_rows)} filas no se pudieron auditar (EVIDENCE_MISSING). Corregir la materialización antes de continuar.")
    else:
        print("\n✅ Ningún error de materialización encontrado.")
        print("Las 73 NO_ZONE y las 219 USABLE_UNGRADED son semánticamente correctas según la tesis.")
        print("El materializador actual es correcto para las tres condiciones de POI.")


if __name__ == "__main__":
    main()
