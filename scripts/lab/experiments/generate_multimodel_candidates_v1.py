"""
Generador común multimodelo ICT — paso 4 del plan.

Orquesta los detectores existentes (po3, turtle_soup, silver_bullet, killzone)
bajo un contrato unificado. Las familias son salidas separadas, no tres motores
incoherentes.

Contrato:
  - Recibe features_at_t del dataset existente (no modifica grammar_labels)
  - Aplica PO3, Turtle Soup, Silver Bullet en paralelo
  - Devuelve familias con estado, gates y evidencia
  - Registra lineage por evento economico
"""
from __future__ import annotations

import sys
from pathlib import Path

# Asegurar que el path del proyecto este en sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# Detectores existentes (NO crear duplicados)
from engine.po3 import build_po3_state
from engine.turtle_soup import is_turtle_soup
from engine.silver_bullet import is_silver_bullet
from engine.killzone import killzone_en


# ============================================================================
# Contratos de familia (de los documentos oficiales)
# ============================================================================

@dataclass
class FamilyResult:
    """Resultado de clasificacion para una familia."""
    family: str
    complete: bool
    phase_states: dict[str, Any] = field(default_factory=dict)
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    evidence_present: list[str] = field(default_factory=list)
    evidence_missing: list[str] = field(default_factory=list)
    confidence: str = "LOW"
    note: str = ""


@dataclass
class EpisodeCandidate:
    """Candidato multimodelo con lineage y familias."""
    event_id: str
    decision_time: datetime
    symbol: str
    split: str
    direction: str  # LONG | SHORT | NEUTRAL
    families: dict[str, FamilyResult] = field(default_factory=dict)
    primary_family: str | None = None
    is_duplicate: bool = False
    duplicate_of: str | None = None
    original_decision: str = ""  # ABSTAIN | REJECT | PASS


# ============================================================================
# Clasificacion PO3
# ============================================================================

def classify_po3(features: dict, grammar: dict) -> FamilyResult:
    """
    Clasifica contra contrato PO3: A and M and D and aligned.
    
    A: sesgo HTF o rango explicito
    M: sweep en contra del sesgo (con filtro de open del dia si disponible)
    D: CHoCH/BOS a favor + FVG/OB (despues de M)
    aligned: direction alineado al sesgo HTF
    """
    layers = features.get("context_layers", {})
    constraints = features.get("constraints", {})
    seq = features.get("sequence", [])
    bias = layers.get("D1", {}).get("bias", "UNKNOWN")
    allow_long = constraints.get("allow_long")
    allow_short = constraints.get("allow_short")
    context_bucket = features.get("context_bucket", "NEUTRAL")
    
    # Construir estructura para build_po3_state
    # El detector espera: {tf: {trend, sweep_up, sweep_down, bos_dir, bos_status,
    #                             choch_status, fvg_state, ob_dir, session_range}}
    estructura = {}
    for tf_name in ("D1", "H4", "H1", "M15"):
        tf_data = layers.get(tf_name, {})
        estructura[tf_name] = {
            "trend": tf_data.get("bias", "NEUTRAL"),
            "sweep_up": tf_data.get("sweep_up", False),
            "sweep_down": tf_data.get("sweep_down", False),
            "bos_dir": tf_data.get("bos_dir", 0),
            "bos_status": tf_data.get("bos_status", ""),
            "choch_status": tf_data.get("choch_status", ""),
            "fvg_state": tf_data.get("fvg_state", ""),
            "ob_dir": tf_data.get("ob_dir", ""),
            "session_range": tf_data.get("session_range", None),
        }
    
    # build_po3_state necesita bias y estructura
    # bias viene de D1 o H4
    htf_bias = bias if bias != "UNKNOWN" else layers.get("H4", {}).get("bias", "UNKNOWN")
    
    po3_state = build_po3_state(
        estructura=estructura,
        bias=htf_bias,
        exec_tf="M15",
        htf="H4",
    )
    
    # Verificar zona de entrada
    has_zone = grammar.get("pd_array_zone") not in ("NO_ZONE",)
    
    # Si NO_ZONE, no hay zona validada
    zone_ok = has_zone
    
    # Construir resultado
    gates_passed = []
    gates_failed = []
    evidence_present = []
    evidence_missing = []
    
    if po3_state.A:
        gates_passed.append("A_acumulacion")
        evidence_present.append("htf_bias_or_session_range")
    else:
        gates_failed.append("A_falta")
        evidence_missing.append("htf_bias_or_session_range")
    
    if po3_state.M:
        gates_passed.append("M_manipulacion")
        evidence_present.append("sweep_opposes_bias")
    else:
        gates_failed.append("M_falta")
        evidence_missing.append("sweep_opposes_bias")
    
    if po3_state.D:
        gates_passed.append("D_distribucion")
        evidence_present.append("choch_bos_aligned")
    else:
        gates_failed.append("D_falta")
        evidence_missing.append("choch_bos_aligned")
    
    if zone_ok:
        gates_passed.append("zona_entrada")
        evidence_present.append("pd_array_zone_valid")
    else:
        gates_failed.append("zona_falta")
        evidence_missing.append("pd_array_zone_valid")
    
    aligned = po3_state.aligned
    if aligned:
        gates_passed.append("alineacion")
    else:
        gates_failed.append("alineacion_fallida")
        evidence_missing.append("setup_aligned_to_htf")
    
    complete = po3_state.complete and zone_ok
    
    # Determinar fase de la secuencia (del dataset)
    po3_phase = grammar.get("po3_phase", "NONE")
    
    return FamilyResult(
        family="PO3",
        complete=complete,
        phase_states={
            "A": po3_state.A,
            "M": po3_state.M,
            "D": po3_state.D,
            "aligned": aligned,
            "complete": po3_state.complete,
            "direction": po3_state.direction,
            "broke_open": po3_state.broke_open,
            "dataset_po3_phase": po3_phase,
        },
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        evidence_present=evidence_present,
        evidence_missing=evidence_missing,
        confidence="HIGH" if complete else ("MEDIUM" if len(gates_passed) >= 3 else "LOW"),
        note=po3_state.incomplete_reason[0] if po3_state.incomplete_reason else "",
    )


# ============================================================================
# Clasificacion Turtle Soup
# ============================================================================

def classify_turtle(features: dict, grammar: dict) -> FamilyResult:
    """
    Clasifica contra contrato Turtle Soup:
    1. Sesgo HTF claro (BULLISH o BEARISH)
    2. Setup OPuesto al sesgo (contratrend)
    3. Sweep de liquidez del lado tramposo (PDH/PDL dia previo)
    4. Confirmacion MSS/CHOCH/BOS de giro en LTF
    5. Zona FVG/OB + RR
    """
    layers = features.get("context_layers", {})
    constraints = features.get("constraints", {})
    seq = features.get("sequence", [])
    
    d1_bias = layers.get("D1", {}).get("bias", "UNKNOWN")
    allow_long = constraints.get("allow_long")
    allow_short = constraints.get("allow_short")
    
    gates_passed = []
    gates_failed = []
    evidence_present = []
    evidence_missing = []
    
    # Condicion 1: sesgo HTF claro
    has_htf_bias = d1_bias not in ("UNKNOWN", "MIXED")
    if has_htf_bias:
        gates_passed.append("sesgo_HTF")
        evidence_present.append("d1_bias_defined")
    else:
        gates_failed.append("sesgo_HTF_falta")
        evidence_missing.append("d1_bias_defined")
    
    # Condicion 2: contratrend
    contratrend = False
    contractrend_note = ""
    if d1_bias == "BULLISH" and allow_short and not allow_long:
        contratrend = True
        contractrend_note = "short contra bullish"
    elif d1_bias == "BEARISH" and allow_long and not allow_short:
        contratrend = True
        contractrend_note = "long contra bearish"
    
    if contratrend:
        gates_passed.append("contratrend")
        evidence_present.append("setup_opposite_to_htf")
    else:
        gates_failed.append("contratrend_falta")
        evidence_missing.append("setup_opposite_to_htf")
        contractrend_note = "d1={} allow_long={} allow_short={}".format(
            d1_bias, allow_long, allow_short)
    
    # Condicion 3: sweep
    has_sweep = grammar.get("liquidity_sweep") == "SWEEP_VALID"
    if has_sweep:
        gates_passed.append("sweep")
        evidence_present.append("liquidity_sweep_valid")
    else:
        gates_failed.append("sweep_falta")
        evidence_missing.append("liquidity_sweep_valid")
    
    # Condicion 4: confirmacion de giro
    has_structure = grammar.get("structure_confirmation") == "CONFIRMED"
    if has_structure:
        gates_passed.append("confirmacion_giro")
        evidence_present.append("structure_confirmed")
    else:
        gates_failed.append("confirmacion_falta")
        evidence_missing.append("structure_confirmed")
    
    # Condicion 5: zona de entrada validada
    has_zone = grammar.get("pd_array_zone") not in ("NO_ZONE",)
    
    if has_zone:
        gates_passed.append("zona_entrada")
        evidence_present.append("pd_array_zone_valid")
    else:
        gates_failed.append("zona_no_validada")
        evidence_missing.append("pd_array_zone_valid")
    
    complete = (has_htf_bias and contratrend and has_sweep 
                and has_structure and has_zone)
    
    # Determinar direction del contractrend
    direction = "NEUTRAL"
    if d1_bias == "BULLISH" and allow_short:
        direction = "SHORT"
    elif d1_bias == "BEARISH" and allow_long:
        direction = "LONG"
    
    return FamilyResult(
        family="TURTLE",
        complete=complete,
        phase_states={
            "sesgo_HTF": has_htf_bias,
            "contratrend": contratrend,
            "direction": direction,
            "sweep": has_sweep,
            "confirmacion": has_structure,
            "zona_validada": has_zone,
        },
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        evidence_present=evidence_present,
        evidence_missing=evidence_missing,
        confidence="HIGH" if complete else ("MEDIUM" if len(gates_passed) >= 3 else "LOW"),
        note=contractrend_note,
    )


# ============================================================================
# Clasificacion Silver Bullet
# ============================================================================

def classify_silver(features: dict, grammar: dict, decision_time: datetime, 
                    killzone_fn=None) -> FamilyResult:
    """
    Clasifica contra contrato Silver Bullet:
    1. Dentro de killzone London Open / NY AM
    2. Sweep de liquidez en LTF
    3. FVG posterior al sweep
    4. Alineacion con sesgo del dia (D1/H4)
    5. RR >= 1:2
    """
    layers = features.get("context_layers", {})
    constraints = features.get("constraints", {})
    seq = features.get("sequence", [])
    
    d1_bias = layers.get("D1", {}).get("bias", "UNKNOWN")
    h4_bias = layers.get("H4", {}).get("bias", "UNKNOWN")
    allow_long = constraints.get("allow_long")
    allow_short = constraints.get("allow_short")
    
    gates_passed = []
    gates_failed = []
    evidence_present = []
    evidence_missing = []
    
    # Condicion 1: killzone (no disponible en dataset M15 actual)
    kz_name = None
    if killzone_fn is not None:
        try:
            kz_name = killzone_fn(decision_time)
        except Exception:
            kz_name = None
    
    kz_ok = kz_name in ("London Open", "New York AM")
    in_kz = kz_ok or kz_name is None  # None = no hay datos de KZ, no se puede evaluar
    
    if kz_name is not None:
        if kz_ok:
            gates_passed.append("killzone")
            evidence_present.append("in_killzone_{}".format(kz_name))
        else:
            gates_failed.append("fuera_de_killzone")
            evidence_missing.append("in_killzone")
    else:
        # No hay datos de KZ en este dataset
        gates_failed.append("KZ_no_disponible")
        evidence_missing.append("killzone_data")
    
    # Condicion 2: sweep
    has_sweep = grammar.get("liquidity_sweep") == "SWEEP_VALID"
    if has_sweep:
        gates_passed.append("sweep")
        evidence_present.append("liquidity_sweep_valid")
    else:
        gates_failed.append("sweep_falta")
        evidence_missing.append("liquidity_sweep_valid")
    
    # Condicion 3: FVG posterior al sweep
    has_fvg = "FVG" in seq
    if has_fvg:
        gates_passed.append("fvg_posterior")
        evidence_present.append("fvg_in_sequence")
    else:
        gates_failed.append("fvg_falta")
        evidence_missing.append("fvg_in_sequence")
    
    # Condicion 4: alineacion con sesgo HTF
    aligned = False
    if d1_bias == "BULLISH" and allow_long:
        aligned = True
    elif d1_bias == "BEARISH" and allow_short:
        aligned = True
    elif h4_bias == "BULLISH" and allow_long:
        aligned = True
    elif h4_bias == "BEARISH" and allow_short:
        aligned = True
    
    if aligned:
        gates_passed.append("alineacion_HTF")
    else:
        gates_failed.append("alineacion_falta")
        evidence_missing.append("setup_aligned_to_htf")
    
    # Condicion 5: RR >= 1:2 (no disponible en dataset)
    rr_available = False
    
    # Para completar, necesitamos KZ + sweep + FVG + alineacion + RR
    complete = False
    
    return FamilyResult(
        family="SILVER_BULLET",
        complete=complete,
        phase_states={
            "killzone": kz_name,
            "killzone_ok": kz_ok,
            "killzone_evaluable": kz_name is not None,
            "sweep": has_sweep,
            "fvg": has_fvg,
            "aligned": aligned,
            "rr_available": rr_available,
        },
        gates_passed=gates_passed,
        gates_failed=gates_failed,
        evidence_present=evidence_present,
        evidence_missing=evidence_missing,
        confidence="LOW" if kz_name is None else ("MEDIUM" if len(gates_passed) >= 3 else "LOW"),
        note="KZ y RR no disponibles en dataset M15" if kz_name is None else "",
    )


# ============================================================================
# Generador comun
# ============================================================================

def generate_candidate(row: dict, killzone_fn=None) -> EpisodeCandidate:
    """
    Genera un candidato multimodelo desde una fila del dataset.
    
    Recibe una fila del dataset existente (con features_at_t y grammar_labels)
    y aplica los tres detectores en paralelo.
    
    NO modifica grammar_labels originales. Devuelve familias separadas.
    """
    features = row.get("features_at_t", {})
    grammar = row.get("grammar_labels", {})
    
    decision_time_str = row.get("decision_time", "")
    if decision_time_str:
        decision_time = pd.to_datetime(decision_time_str, utc=True).to_pydatetime()
    else:
        decision_time = datetime.now(timezone.utc)
    
    constraints = features.get("constraints", {})
    allow_long = constraints.get("allow_long")
    allow_short = constraints.get("allow_short")
    
    # Determinar direccion
    if allow_long and not allow_short:
        direction = "LONG"
    elif allow_short and not allow_long:
        direction = "SHORT"
    else:
        direction = "NEUTRAL"
    
    # Aplicar los tres clasificadores
    po3_result = classify_po3(features, grammar)
    turtle_result = classify_turtle(features, grammar)
    silver_result = classify_silver(features, grammar, decision_time, killzone_fn)
    
    families = {
        "PO3": po3_result,
        "TURTLE": turtle_result,
        "SILVER_BULLET": silver_result,
    }
    
    # Determinar familia primaria (la primera completa)
    primary = None
    for fam_name in ("PO3", "TURTLE", "SILVER_BULLET"):
        if families[fam_name].complete:
            primary = fam_name
            break
    
    return EpisodeCandidate(
        event_id=row.get("event_id", ""),
        decision_time=decision_time,
        symbol=row.get("symbol", "EURUSD"),
        split=row.get("_split", "UNKNOWN"),
        direction=direction,
        families=families,
        primary_family=primary,
        original_decision=grammar.get("setup_decision", "UNKNOWN"),
    )


def generate_candidates_from_dataset(
    dataset_path: str,
    killzone_fn=None,
) -> list[EpisodeCandidate]:
    """
    Genera candidatos desde un archivo JSONL del dataset.
    """
    candidates = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = __import__("json").loads(line)
                row["_split"] = dataset_path.split("_")[-1].replace(".jsonl", "").upper()
                candidate = generate_candidate(row, killzone_fn)
                candidates.append(candidate)
    return candidates


# ============================================================================
# Deduplicacion por evento economico
# ============================================================================

def deduplicate_candidates(candidates: list[EpisodeCandidate]) -> list[EpisodeCandidate]:
    """
    Deduplica candidatos por evento economico.
    """
    seen_event_ids: dict[str, EpisodeCandidate] = {}
    result: list[EpisodeCandidate] = []
    
    for candidate in candidates:
        event_id = candidate.event_id
        if event_id in seen_event_ids:
            candidate.is_duplicate = True
            candidate.duplicate_of = seen_event_ids[event_id].event_id
        else:
            seen_event_ids[event_id] = candidate
        
        result.append(candidate)
    
    return result


# ============================================================================
# Reporte de frecuencia
# ============================================================================

def report_frequency(candidates: list[EpisodeCandidate]) -> dict:
    """
    Genera reporte de frecuencia por familia, split, mes, ano, sesion, direccion, simbolo.
    """
    from collections import defaultdict
    
    stats = {
        "total_candidates": len(candidates),
        "unique_events": len(set(c.event_id for c in candidates)),
        "duplicates": sum(1 for c in candidates if c.is_duplicate),
        "by_family": defaultdict(lambda: {"complete": 0, "partial": 0, "total": 0}),
        "by_split": defaultdict(lambda: {"complete": 0, "total": 0}),
        "by_direction": defaultdict(int),
        "by_original_decision": defaultdict(int),
        "by_week": defaultdict(lambda: defaultdict(int)),
    }
    
    for c in candidates:
        for fam_name, fam_result in c.families.items():
            stats["by_family"][fam_name]["total"] += 1
            if fam_result.complete:
                stats["by_family"][fam_name]["complete"] += 1
            else:
                stats["by_family"][fam_name]["partial"] += 1
        
        stats["by_split"][c.split]["total"] += 1
        if c.primary_family:
            stats["by_split"][c.split]["complete"] += 1
        
        stats["by_direction"][c.direction] += 1
        stats["by_original_decision"][c.original_decision] += 1
        
        # Por semana calendario
        week_key = c.decision_time.strftime("%Y-W%W")
        if c.primary_family:
            stats["by_week"][week_key]["complete"] += 1
        stats["by_week"][week_key]["total"] += 1
    
    # Convertir defaultdicts a dicts regulares
    for key in stats:
        if isinstance(stats[key], defaultdict):
            stats[key] = dict(stats[key])
            for subkey in stats[key]:
                if isinstance(stats[key][subkey], defaultdict):
                    stats[key][subkey] = dict(stats[key][subkey])
    
    return stats


# ============================================================================
# Main: ejecucion sobre el dataset existente
# ============================================================================

if __name__ == "__main__":
    import json
    from pathlib import Path
    
    DATASET_DIR = PROJECT_ROOT / "data" / "ml" / "tensorflow" / "setup_grammar_v1"
    OUTPUT_DIR = PROJECT_ROOT / "reports" / "ict_temporal_v1" / "orion"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    SPLITS = {
        "TRAIN": "dataset_train.jsonl",
        "VALIDATION": "dataset_validation.jsonl",
        "TEST_OOS": "dataset_test_oos.jsonl",
    }
    
    print("=== GENERADOR MULTIMODELO COMUN ===")
    print()
    print("Aplicando contratos PO3, Turtle Soup, Silver Bullet sobre dataset existente")
    print(" NO modifica grammar_labels originales")
    print()
    
    all_candidates: list[EpisodeCandidate] = []
    
    for split_name, filename in SPLITS.items():
        path = DATASET_DIR / filename
        print("Procesando {}: {} filas".format(split_name, path.stat().st_size))
        candidates = generate_candidates_from_dataset(str(path))
        all_candidates.extend(candidates)
    
    print("Total candidatos generados: {}".format(len(all_candidates)))
    print()
    
    # Deduplicar
    deduplicated = deduplicate_candidates(all_candidates)
    unique = len(set(c.event_id for c in deduplicated))
    dupes = sum(1 for c in deduplicated if c.is_duplicate)
    print("Despues de deduplicacion:")
    print("  Eventos unicos: {}".format(unique))
    print("  Duplicados: {}".format(dupes))
    print()
    
    # Estadisticas por familia
    print("=== ESTADISTICAS POR FAMILIA ===")
    for fam_name in ("PO3", "TURTLE", "SILVER_BULLET"):
        complete = sum(1 for c in deduplicated if c.families[fam_name].complete)
        partial = sum(1 for c in deduplicated if not c.families[fam_name].complete 
                      and len(c.families[fam_name].gates_passed) > 0)
        print("  {}: {} completos, {} parciales".format(fam_name, complete, partial))
    print()
    
    # Familias completas por split
    print("=== FAMILIAS COMPLETAS POR SPLIT ===")
    for split in ("TRAIN", "VALIDATION", "TEST_OOS"):
        split_cands = [c for c in deduplicated if c.split == split]
        for fam_name in ("PO3", "TURTLE", "SILVER_BULLET"):
            complete = sum(1 for c in split_cands if c.families[fam_name].complete)
            if complete > 0:
                print("  {}/{:8s}: {}".format(split, fam_name, complete))
    print()
    
    # Generar reporte de frecuencia
    freq_report = report_frequency(deduplicated)
    
    # Guardar resultados
    output_path = OUTPUT_DIR / "multimodel_candidates_episodes_v1.json"
    output = {
        "schema": "ICT_MULTIMODEL_EPISODES_V1",
        "description": "Candidatos multimodelo generados desde dataset existente.",
        "generated": __import__("datetime").datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(deduplicated),
        "unique_events": unique,
        "duplicates": dupes,
        "frequency_report": freq_report,
        "candidates": [
            {
                "event_id": c.event_id,
                "decision_time": c.decision_time.isoformat(),
                "symbol": c.symbol,
                "split": c.split,
                "direction": c.direction,
                "primary_family": c.primary_family,
                "original_decision": c.original_decision,
                "is_duplicate": c.is_duplicate,
                "families": {
                    fam: {
                        "complete": fam_res.complete,
                        "gates_passed": fam_res.gates_passed,
                        "gates_failed": fam_res.gates_failed,
                        "evidence_present": fam_res.evidence_present,
                        "evidence_missing": fam_res.evidence_missing,
                        "confidence": fam_res.confidence,
                        "note": fam_res.note,
                    }
                    for fam, fam_res in c.families.items()
                }
            }
            for c in deduplicated
        ]
    }
    
    with output_path.open("w") as f:
        json.dump(output, f, indent=2)
    
    print("Resultados guardados en: {}".format(output_path))
    print()
    
    # Resumen ejecutivo
    print("=== RESUMEN EJECUTIVO ===")
    print()
    totals = freq_report["by_family"]
    for fam_name, fam_stats in totals.items():
        pct = round(100 * fam_stats["complete"] / fam_stats["total"]) if fam_stats["total"] > 0 else 0
        print("{}: {} completos / {} totales ({}%)".format(
            fam_name, fam_stats["complete"], fam_stats["total"], pct
        ))
    print()
    print("clave: completo = todas las condiciones del contrato satisfechas")
    print("       parcial = algunas condiciones cumplidas pero no todas")
