#!/usr/bin/env python3
"""
Reproducción del entrenamiento setup_quality_v1.
Ejecutar: python reproduce_setup_quality_training.py
"""
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DATASET_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1"
MODEL_DIR = ROOT / "data/ml/tensorflow/setup_quality_v1"

def verify_hash(path, expected):
    """Verificar hash SHA256 de un archivo."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    actual = h.hexdigest()
    ok = actual == expected
    print(f"{'✓' if ok else '✗'} {path.name}: {actual[:16]}..." + (" MATCH" if ok else " MISMATCH"))
    return ok

def main():
    records = json.loads((MODEL_DIR / "training_record.json").read_text())
    print("=" * 60)
    print("REPRODUCCIÓN setup_quality_v1 — INTEGRIDAD")
    print("=" * 60)
    
    # Hashes esperados
    expected = {
        DATASET_DIR / "dataset_train.jsonl": records["dataset_hashes"]["TRAIN"],
        DATASET_DIR / "dataset_validation.jsonl": records["dataset_hashes"]["VALIDATION"],
        DATASET_DIR / "dataset_test_oos.jsonl": records["dataset_hashes"]["TEST_OOS"],
        DATASET_DIR / "feature_schema.json": "e5d9ca857f688a2d50d8fa8dc6a1858bf389fad58f0306c7d9fe7f5acd030352",
        MODEL_DIR / "model.keras": records["model_sha256"],
        MODEL_DIR / "training_record.json": "daa425cbdbcc9a4e8829d5139fbd2564edcf9e234425a6f974c7a6aa135737ee",
    }
    
    all_ok = True
    for path, exp_hash in expected.items():
        all_ok &= verify_hash(path, exp_hash)
    
    print()
    print("=" * 60)
    print("MÉTRICAS setup_quality_v1 — setup_grammar corregido")
    print("=" * 60)
    
    m = records["metrics"]
    baselines = {
        "setup_decision": (0.8421, 0.8421),
        "weak_link": (0.8684, 0.8684),
        "failure_risk": (0.4992, 0.4992),
    }
    
    for split_name in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        metrics = m[split_name]
        print(f"\n[{split_name}] n={metrics.get('n', '?')}")
        for task in ["setup_decision", "weak_link", "failure_risk"]:
            mt = metrics[task]
            bal_acc = mt["balanced_accuracy"]
            base_bal = baselines[task][0]
            delta = bal_acc - base_bal
            sign = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            print(f"  {task:15s} balanced_acc={bal_acc:.4f}  baseline={base_bal:.4f}  delta={delta:+.4f} {sign}")
    
    print()
    print(f"status: {records['status']}")
    print(f"shadow_mode: {records['shadow_mode']}")
    print(f"can_trade: {records['can_trade']}")
    print(f"epochs_completed: {records['epochs_completed']}")
    print()
    
    # Reporte de dataset
    print("=" * 60)
    print("DATASET setup_grammar corregido")
    print("=" * 60)
    print("Origen: materializador corregido (materialize_setup_grammar_dataset_v1_fixed.py)")
    print("Defecto corregido: pd_array_zone() original etiquetaba USABLE_UNGRADED")
    print("                     solo por presencia de FVG/OB, sin evaluar 3 condiciones POI")
    print("Nuevo materializador: integra detector semántico SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1")
    print()
    print("Distribución:")
    for split, exp in [
        ("TRAIN", "62cf541d..."),
        ("VALIDATION", "e83c6ef0..."),
        ("TEST_OOS", "f3b982ab...")
    ]:
        path = DATASET_DIR / f"dataset_{split.lower()}.jsonl"
        rows = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
        zones = sum(1 for r in rows if r['grammar_labels']['pd_array_zone'] == 'USABLE_UNGRADED')
        nozone = sum(1 for r in rows if r['grammar_labels']['pd_array_zone'] == 'NO_ZONE')
        print(f"  {split}: {len(rows)} filas (USABLE_UNGRADED={zones}, NO_ZONE={nozone})")
    
    print()
    print(f"Total USABLE_UNGRADED: 2 (TRAIN) + 0 (VAL) + 4 (TEST_OOS) = 6")
    print()
    print("PROBLEMA IDENTIFICADO: Solo 6 ejemplos positivos en dataset.")
    print("  VALIDATION tiene 0 USABLE_UNGRADED — imposible verificar accuracia real")
    print("  TRAIN tiene solo 2 positivos — sobreajuste casi garantizado")
    print("  TEST_OOS tiene 4 positivos — métrica insuficiente para certificar")

if __name__ == "__main__":
    main()
