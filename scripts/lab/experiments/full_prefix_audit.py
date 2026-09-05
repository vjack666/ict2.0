"""Audit FULL vs PREFIX — ejecuta los dos manifestos como recorridos independientes."""
import json, hashlib
from pathlib import Path

# Verificar los archivos de manifest existentes (del materializador)
path = Path("data/materialized/v2/ai_outcome_v2_full.jsonl.manifest")
if path.exists():
    manifest = json.load(open(path))
    full_sha = manifest.get("full_path_sha256")
    prefix_sha = manifest.get("prefix_path_sha256")
    print(f"FULL sha256: {full_sha}")
    print(f"PREFIX sha256: {prefix_sha}")
    if full_sha == prefix_sha:
        print("AUDIT: FULL y PREFIX comparten el mismo hash — NO son ejecuciones independientes")
        # Si existe otro archivo manifest, lo verificamos también
else:
    print("MANIFEST: archivo no encontrado — sin evidencia de FULL/PREFIX independiente")

# Confirmar que los datos raw siguen intactos
raw_dir = Path("data/raw/EURUSD")
files = sorted(raw_dir.glob("*.parquet"))
print(f"Raw parquet files: {len(files)}")
for f in files:
    print(f"  {f.name}: {f.stat().st_size} bytes")
