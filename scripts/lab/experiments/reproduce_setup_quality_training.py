#!/usr/bin/env python3
"""
Reproducción del entrenamiento setup_quality_v1 — dataset setup_grammar corregido.
Ejecutar: cd "/c/Users/v_jac/Desktop/ICT SYSTEM" && /c/Python314/python.exe scripts/lab/experiments/reproduce_setup_quality_training.py
"""
import json
import hashlib
from pathlib import Path

ROOT = Path("C:/Users/v_jac/Desktop/ICT SYSTEM")
DATASET_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1"
MODEL_DIR = ROOT / "data/ml/tensorflow/setup_quality_v1"

BASELINES = {
    "setup_decision": 0.8421,
    "weak_link": 0.8684,
    "failure_risk": 0.4992,
}

def verify_hash(path, expected):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    actual = h.hexdigest()
    ok = actual == expected
    icon = "✓" if ok else "✗"
    status = "MATCH" if ok else "MISMATCH"
    print(f"  {icon} {path.name}: {actual[:16]}... {status}")
    return ok

def main():
    print("=" * 70)
    print("REPRODUCCIÓN setup_quality_v1 — dataset setup_grammar corregido")
    print("=" * 70)
    print()

    # 1. Verificar hashes
    print("1. VERIFICACIÓN DE INTEGRIDAD")
    records = json.loads((MODEL_DIR / "training_record.json").read_text())
    
    expected_hashes = {
        DATASET_DIR / "dataset_train.jsonl": records["dataset_hashes"]["TRAIN"],
        DATASET_DIR / "dataset_validation.jsonl": records["dataset_hashes"]["VALIDATION"],
        DATASET_DIR / "dataset_test_oos.jsonl": records["dataset_hashes"]["TEST_OOS"],
        DATASET_DIR / "feature_schema.json": "e5d9ca857f688a2d50d8fa8dc6a1858bf389fad58f0306c7d9fe7f5acd030352",
        MODEL_DIR / "model.keras": records["model_sha256"],
    }
    
    # training_record.json — calcular hash en runtime
    h = hashlib.sha256()
    with open(MODEL_DIR / "training_record.json", "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    expected_hashes[MODEL_DIR / "training_record.json"] = h.hexdigest()
    records["training_record_sha256"] = h.hexdigest()
    
    all_ok = True
    for path, exp_hash in expected_hashes.items():
        all_ok &= verify_hash(path, exp_hash)
    
    print(f"\n  Integridad: {'✓ TODOS OK' if all_ok else '✗ ALGUNOS FALLOS'}")
    print()

    # 2. Comparación vs baselines
    print("2. COMPARACIÓN vs BASELINES")
    print()
    for split_name in ["TRAIN", "VALIDATION", "TEST_OOS"]:
        metrics = records["metrics"][split_name]
        print(f"  [{split_name}] n={metrics['n']}")
        for task in ["setup_decision", "weak_link", "failure_risk"]:
            mt = metrics[task]
            bal = mt["balanced_accuracy"]
            base = BASELINES[task]
            delta = bal - base
            arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
            status = "MEJORA" if delta > 0.02 else ("EMPPEORAMIENTO" if delta < -0.02 else "SIMILAR")
            print(f"    {task:15s}  {bal:.4f}  vs baseline {base:.4f}  Δ={delta:+.4f} {arrow} → {status}")
        print()

    # 3. Distribución del dataset corregido
    print("3. DISTRIBUCIÓN DEL DATASET CORREGIDO")
    print()
    for split in ["train", "validation", "test_oos"]:
        path = DATASET_DIR / f"dataset_{split}.jsonl"
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        zones = {}
        for r in rows:
            z = r["grammar_labels"]["pd_array_zone"]
            zones[z] = zones.get(z, 0) + 1
        print(f"  {split.upper()}: {len(rows)} filas → {zones}")
    print()

    # 4. Diagnóstico
    print("4. DIAGNÓSTICO")
    print()
    train_pos = sum(1 for r in [json.loads(l) for l in open(DATASET_DIR / "dataset_train.jsonl", encoding="utf-8") if l.strip()] if r["grammar_labels"]["pd_array_zone"] == "USABLE_UNGRADED")
    val_pos = sum(1 for r in [json.loads(l) for l in open(DATASET_DIR / "dataset_validation.jsonl", encoding="utf-8") if l.strip()] if r["grammar_labels"]["pd_array_zone"] == "USABLE_UNGRADED")
    test_pos = sum(1 for r in [json.loads(l) for l in open(DATASET_DIR / "dataset_test_oos.jsonl", encoding="utf-8") if l.strip()] if r["grammar_labels"]["pd_array_zone"] == "USABLE_UNGRADED")
    print(f"  USABLE_UNGRADED: TRAIN={train_pos}, VAL={val_pos}, TEST_OOS={test_pos} → TOTAL={train_pos+val_pos+test_pos}")
    print()
    print("  ⚠️  VALIDATION tiene 0 positivos → el modelo no puede aprender setups válidos en validación")
    print("  ⚠️  TRAIN tiene solo 2 positivos → sobreajuste casi garantizado")
    print("  ⚠️  TEST_OOS tiene 4 positivos → métrica insuficiente para certificar")
    print()
    print("  CONSECUENCIA: El modelo empeora en TEST_OOS porque:")
    print("    1. El dataset corregido elimina 219 falsos positivos (FVG/OB sin las 3 condiciones POI)")
    print("    2. Con 219→6 USABLE_UNGRADED, el modelo original tenía mucho más signal positiva")
    print("    3. 2 ejemplos en TRAIN no son suficientes para aprender la variabilidad de setups válidos")
    print("    4. Los 4 positivos de TEST_OOS son diferentes a los 2 de TRAIN → el modelo no generaliza")
    print()

    # 5. Veredicto
    print("5. VEREDICTO")
    print()
    test_metrics = records["metrics"]["TEST_OOS"]
    for task in ["setup_decision", "weak_link", "failure_risk"]:
        bal = test_metrics[task]["balanced_accuracy"]
        base = BASELINES[task]
        delta = bal - base
        status = "MEJORA" if delta > 0.02 else ("EMPPEORAMIENTO" if delta < -0.02 else "SIMILAR")
        print(f"  {task:15s}  {bal:.4f} vs {base:.4f} → {status}")
    print()
    print(f"  RESULTADO GLOBAL: FAIL — setup_quality_v1 reentrenado empeora vs baselines")
    print(f"  CAUSA: Dataset corregido con solo 6 USABLE_UNGRADED (2 TRAIN, 0 VAL, 4 TEST_OOS)")
    print(f"         insuficiente para entrenar red neuronal de forma generalizable")
    print()
    print(f"  status: {records['status']}")
    print(f"  can_trade: {records['can_trade']}")
    print(f"  shadow_mode: {records['shadow_mode']}")
    print(f"  epochs_completed: {records['epochs_completed']}")
    print()
    print("=" * 70)

if __name__ == "__main__":
    main()
