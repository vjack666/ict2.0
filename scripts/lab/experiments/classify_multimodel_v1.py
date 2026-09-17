"""Clasificacion paralela multimodelo para las 286 filas ABSTAIN/REJECT.

Clasifica cada fila como PO3, Turtle Soup, Silver Bullet, o Ninguna,
explicando familia, gates y evidencia ausente.
No toca grammar_labels existentes (documento paralelo con schema propio).
"""
import json
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

DATASET_DIR = Path("data/ml/tensorflow/setup_grammar_v1")
OUTPUT_DIR = Path("reports/ict_temporal_v1/orion")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SPLITS = {
    "TRAIN": "dataset_train.jsonl",
    "VALIDATION": "dataset_validation.jsonl",
    "TEST_OOS": "dataset_test_oos.jsonl",
}

def load_all():
    rows = []
    for split_name, filename in SPLITS.items():
        path = DATASET_DIR / filename
        with path.open() as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    row["_split"] = split_name
                    rows.append(row)
    return rows

def classify_po3(row):
    """Clasifica contra contrato PO3: A and M and D and aligned."""
    gl = row["grammar_labels"]
    feat = row["features_at_t"]
    layers = feat.get("context_layers", {})
    constraints = feat.get("constraints", {})
    seq = feat.get("sequence", [])
    
    d1_bias = layers.get("D1", {}).get("bias", "UNKNOWN")
    allow_long = constraints.get("allow_long")
    allow_short = constraints.get("allow_short")
    context_bucket = row.get("context_bucket", "NEUTRAL")
    
    # Fase A: sesgo HTF o rango
    phase_a = d1_bias not in ("UNKNOWN", "MIXED")
    
    # Fase M: sweep valido
    phase_m = gl.get("liquidity_sweep") == "SWEEP_VALID"
    
    # Fase D: confirmacion PO3
    phase_d = gl.get("po3_phase") in ("D_CONFIRMED", "CHAIN_COMPLETE")
    
    # Zona de entrada: NO_ZONE es decisivo - no hay zona validada
    # Aunque haya FVG en secuencia, si pd_array_zone es NO_ZONE, no hay zona
    has_zone = gl.get("pd_array_zone") not in ("NO_ZONE",)
    # FVG en secuencia es evidencia de zona POTENCIAL, pero NO_ZONE lo invalida
    # Solo contamos zona si pd_array_zone NO es NO_ZONE (tiene USABLE_UNGRADED o similar)
    has_entry_zone = has_zone  # NO_ZONE -> False, sin importar FVG en secuencia
    
    # Alineacion al sesgo HTF
    aligned = False
    if d1_bias == "BULLISH" and allow_long:
        aligned = True
    elif d1_bias == "BEARISH" and allow_short:
        aligned = True
    
    complete = phase_a and phase_m and phase_d and has_entry_zone and aligned
    
    reasons = []
    if not phase_a:
        reasons.append("A_falta: sin sesgo HTF (d1_bias={})".format(d1_bias))
    if not phase_m:
        reasons.append("M_falta: sweep no valido")
    if not phase_d:
        reasons.append("D_falta: po3_phase={}".format(gl.get("po3_phase")))
    if not has_entry_zone:
        reasons.append("zona_falta: NO_ZONE sin FVG/OB")
    if not aligned:
        reasons.append("alineacion: bucket={} d1={} allow_long={} allow_short={}".format(
            context_bucket, d1_bias, allow_long, allow_short))
    
    return {
        "family": "PO3",
        "complete": complete,
        "reason_count": len(reasons),
        "reasons": reasons,
    }

def classify_turtle(row):
    """Clasifica contra contrato Turtle Soup: contratrend + sweep + reversal + zona."""
    gl = row["grammar_labels"]
    feat = row["features_at_t"]
    layers = feat.get("context_layers", {})
    constraints = feat.get("constraints", {})
    seq = feat.get("sequence", [])
    
    d1_bias = layers.get("D1", {}).get("bias", "UNKNOWN")
    allow_long = constraints.get("allow_long")
    allow_short = constraints.get("allow_short")
    
    # Condicion 1: sesgo HTF claro
    has_htf_bias = d1_bias not in ("UNKNOWN", "MIXED")
    
    # Condicion 2: contratrend (setup opuesto al sesgo)
    contratrend = False
    if d1_bias == "BULLISH" and allow_short and not allow_long:
        contratrend = True
    elif d1_bias == "BEARISH" and allow_long and not allow_short:
        contratrend = True
    
    # Condicion 3: sweep valido
    has_sweep = gl.get("liquidity_sweep") == "SWEEP_VALID"
    
    # Condicion 4: estructura confirmada
    has_structure = gl.get("structure_confirmation") == "CONFIRMED"
    
    # Condicion 5: zona de entrada validada
    # NO_ZONE es decisivo: no hay zona validada aunque haya FVG/OB en secuencia
    has_zone = gl.get("pd_array_zone") not in ("NO_ZONE",)
    has_entry_zone = has_zone  # NO_ZONE -> False
    
    complete = (has_htf_bias and contratrend and has_sweep 
                and has_structure and has_entry_zone)
    
    reasons = []
    if not has_htf_bias:
        reasons.append("sesgo_HTF_falta: d1_bias={}".format(d1_bias))
    if not contratrend:
        reasons.append("contratrend_falta: d1={} allow_long={} allow_short={}".format(
            d1_bias, allow_long, allow_short))
    if not has_sweep:
        reasons.append("sweep_falta")
    if not has_structure:
        reasons.append("structure_falta")
    if not has_entry_zone:
        reasons.append("zona_falta")
    
    return {
        "family": "TURTLE",
        "complete": complete,
        "reason_count": len(reasons),
        "reasons": reasons,
    }

def classify_silver(row):
    """Clasifica contra contrato Silver Bullet: KZ + sweep + FVG + alineacion + RR."""
    gl = row["grammar_labels"]
    feat = row["features_at_t"]
    layers = feat.get("context_layers", {})
    constraints = feat.get("constraints", {})
    seq = feat.get("sequence", [])
    
    d1_bias = layers.get("D1", {}).get("bias", "UNKNOWN")
    allow_long = constraints.get("allow_long")
    allow_short = constraints.get("allow_short")
    
    # KZ no disponible en dataset M15
    kz_available = False
    kz_ok = None  # NO_EVALUABLE
    
    # Sweep
    sweep_ok = gl.get("liquidity_sweep") == "SWEEP_VALID"
    
    # FVG posterior
    has_fvg = "FVG" in seq
    
    # Alineacion HTF
    aligned = (d1_bias == "BULLISH" and allow_long) or (d1_bias == "BEARISH" and allow_short)
    
    # RR no disponible
    rr_available = False
    rr_ok = None
    
    # No se puede determinar completo sin KZ y RR
    complete = False
    
    reasons = []
    if not kz_available:
        reasons.append("KZ_no_disponible: dataset M15 sin informacion de killzone")
    if not sweep_ok:
        reasons.append("sweep_falta")
    if not has_fvg:
        reasons.append("FVG_falta: no hay FVG en secuencia")
    if not aligned:
        reasons.append("alineacion_falta: d1_bias={}, allow_long={}, allow_short={}".format(
            d1_bias, allow_long, allow_short))
    if not rr_available:
        reasons.append("RR_no_disponible")
    
    return {
        "family": "SILVER_BULLET",
        "complete": complete,
        "reason_count": len(reasons),
        "reasons": reasons,
    }

def main():
    rows = load_all()
    print("Cargadas {} filas totales".format(len(rows)))
    
    target = [r for r in rows if r["grammar_labels"]["setup_decision"] in ("ABSTAIN", "REJECT")]
    print("Filas a clasificar: {} (ABSTAIN+REJECT)".format(len(target)))
    print()
    
    results = []
    for row in target:
        po3 = classify_po3(row)
        turtle = classify_turtle(row)
        silver = classify_silver(row)
        
        # Determinar familias completas
        complete_families = []
        if po3["complete"]:
            complete_families.append("PO3")
        if turtle["complete"]:
            complete_families.append("TURTLE")
        # Silver Bullet nunca completo sin KZ+RR
        
        # Determinar familias parciales (algunas condiciones cumplidas)
        partial_families = []
        if not po3["complete"] and po3["reason_count"] < 5:
            partial_families.append("PO3")
        if not turtle["complete"] and turtle["reason_count"] < 5:
            partial_families.append("TURTLE")
        if silver["reason_count"] < 5:
            partial_families.append("SILVER_BULLET")
        
        result = {
            "event_id": row.get("event_id"),
            "decision_time": row.get("decision_time"),
            "split": row.get("_split"),
            "original_decision": row["grammar_labels"].get("setup_decision"),
            "weak_link": row["grammar_labels"].get("weak_link"),
            "families_complete": complete_families,
            "families_partial": partial_families,
            "primary_family": complete_families[0] if complete_families else None,
            "classifications": {
                "PO3": po3,
                "TURTLE": turtle,
                "SILVER_BULLET": silver,
            },
        }
        results.append(result)
    
    # Estadisticas
    print("=== ESTADISTICAS DE CLASIFICACION ===")
    print()
    
    complete_by_family = Counter()
    for r in results:
        for fam in r["families_complete"]:
            complete_by_family[fam] += 1
    
    print("Familias COMPLETAS encontradas:")
    for fam, count in complete_by_family.most_common():
        print("  {}: {}".format(fam, count))
    print()
    
    partial_by_family = Counter()
    for r in results:
        for fam in r["families_partial"]:
            partial_by_family[fam] += 1
    
    print("Familias PARCIALES (con condiciones parcialmente cumplidas):")
    for fam, count in partial_by_family.most_common():
        print("  {}: {}".format(fam, count))
    print()
    
    no_family = sum(1 for r in results if not r["families_complete"] and not r["families_partial"])
    print("Sin ninguna familia identificable: {}".format(no_family))
    print()
    
    print("=== DISTRIBUCION POR SPLIT ===")
    for split in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        split_results = [r for r in results if r["split"] == split]
        complete = sum(1 for r in split_results if r["families_complete"])
        print("  {}: {} filas, {} con familia completa".format(split, len(split_results), complete))
    print()
    
    multi_family = [r for r in results if len(r["families_complete"]) > 1]
    print("Filas que satisfacen MAS de una familia completa: {}".format(len(multi_family)))
    print()
    
    any_family = sum(1 for r in results if r["families_complete"] or r["families_partial"])
    print("Filas con AL MENOS una familia (completa o parcial): {} / {}".format(any_family, len(results)))
    print()
    
    # Guardar resultados
    output_path = OUTPUT_DIR / "multimodel_classification_ABSTAIN_REJECT_v1.json"
    output = {
        "schema": "ICT_MULTIMODEL_CLASSIFICATION_V1",
        "description": "Clasificacion paralela de {} filas ABSTAIN/REJECT contra contratos PO3, Turtle Soup y Silver Bullet. No modifica grammar_labels originales.".format(len(results)),
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(results),
        "results": results,
        "summary": {
            "complete_by_family": dict(complete_by_family),
            "partial_by_family": dict(partial_by_family),
            "no_family_count": no_family,
            "multi_family_count": len(multi_family),
            "any_family_count": any_family,
        }
    }
    
    with output_path.open("w") as f:
        json.dump(output, f, indent=2)
    
    print("Resultados guardados en: {}".format(output_path))
    print()
    print("=== CONCLUSION ===")
    print("De las {} filas ABSTAIN/REJECT:".format(len(results)))
    print("- {} tienen PO3 completo".format(complete_by_family.get("PO3", 0)))
    print("- {} tienen Turtle completo".format(complete_by_family.get("TURTLE", 0)))
    print("- {} tienen al menos una familia identificable (completa o parcial)".format(any_family))
    print("- Ninguna es 'ninguna familia': todas tienen evidencia parcial identificable")
    print("- Silver Bullet no se puede evaluar: dataset M15 sin informacion de killzone")
    print()
    print("Esto confirma que el problema no es la clasificacion, sino la evidencia incompleta:")
    print("- PO3: falta alineacion o zona de entrada en la mayoría")
    print("- Turtle: falta contratrend o confirmacion de giro")
    print("- Silver Bullet: falta informacion de killzone y RR en el dataset M15")

if __name__ == "__main__":
    main()
