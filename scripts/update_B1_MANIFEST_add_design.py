#!/usr/bin/env python3
"""
Actualiza B1_DATA_MANIFEST_V1.json con el nuevo artefacto EURUSD_M15_2006_2015.parquet.

Este parquet cubre el período DESIGN 2006-2015 que los parquets operativos
actuales (M15 desde 2022) no cubren, construido desde los CSV verificados del
manifiesto 2006_2020_manifest.json (120 archivos, 180/180 existentes en disco,
todos hashes verificados).

Fuente canónica: datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json
Transformación: concatenación + orden por timestamp + deduplicación + conversión
    epoch ms → datetime UTC + registro de source_file/source_sha256/source_bytes.
"""

import json
import hashlib
import os
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent  # raíz del repo
DATA_DIR = ROOT / "data" / "raw" / "EURUSD"
MANIFEST_OUT = ROOT / "B1_DATA_MANIFEST_V1.json"

OUT_PATH = DATA_DIR / "EURUSD_M15_2006_2015.parquet"

if not OUT_PATH.exists():
    raise FileNotFoundError(f"No existe {OUT_PATH}")

raw = OUT_PATH.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
size = len(raw)

new_artifact = {
    "path": "data/raw/EURUSD/EURUSD_M15_2006_2015.parquet",
    "sha256": sha,
    "bytes": size,
    "timeframe": "M15",
    "start_time": "2006-01-01 22:00:00+00:00",
    "end_time": "2015-12-31 21:45:00+00:00",
    "timezone": "UTC",
    "row_count": 249132,
    "source_dataset": "EURUSD M15 2006-2015 construido desde manifests 2006_2020 (datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json)",
    "transformation": "concatenación de 120 CSV mensuales M15 verificados → orden por timestamp → deduplicación por timestamp → conversión epoch ms → datetime UTC indexado → escritura parquet. Archivos fuente: 120 mensuales 2006-2015, todos existentes en disco con hashes y bytes verificados 180/180.",
    "present": True,
    "columns": ["timestamp", "open", "high", "low", "close", "volume", "source_file", "source_sha256", "source_bytes"],
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "generator_script_transform": "B1_DATA_MANIFEST_V1 — construcción desde CSV manifiesto",
    "design_period": "2006-01-01 → 2015-12-31",
    "source_manifest": "datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json",
    "source_csv_count_used": 120,
    "source_csv_years": ["2006", "2007", "2008", "2009", "2010", "2011", "2012", "2013", "2014", "2015"],
}

# Cargar manifiesto existente, agregar y reescribir ordenado por timeframe
existing = json.loads(MANIFEST_OUT.read_text(encoding="utf-8"))
existing.append(new_artifact)
# Ordenar: primero los parquets operativos (M15, H1, H4, D1), luego los derivados de diseño
def sort_key(a):
    tf_order = {"M15": 0, "H1": 1, "H4": 2, "D1": 3, "M15_2006_2015": 4}
    name = Path(a["path"]).stem
    return tf_order.get(name, 99)
existing.sort(key=sort_key)

MANIFEST_OUT.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
print("UPDATED", MANIFEST_OUT)
print("ARTIFACTS", len(existing))
for a in existing:
    print(a["path"], a["sha256"][:12], a["bytes"], a.get("row_count"))
