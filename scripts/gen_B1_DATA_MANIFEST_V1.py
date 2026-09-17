#!/usr/bin/env python3
"""
B1_DATA_MANIFEST_V1 — generador de manifiesto operativo para B1.

Registra los archivos EXACTOS que el motor usa para construir el corpus B1,
con metadatos verificables: path, sha256, bytes, timeframe, start_time,
end_time, timezone, row_count, source_dataset, transformation.

Fuente operativa: data/raw/EURUSD/*.parquet (las frames que el motor lee en verdad).
Fuente de origen canónica: datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json
    y datasets/eurusd_dukascopy_intraday_2021_2025_manifest.json (ya con hashes).

El manifiesto es reproducible internamente: re-leer los mismos bytes da los mismos
hashes y la misma cantidad de filas.
"""

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("C:/Users/v_jac/Desktop/ICT SYSTEM")
DATA_DIR = ROOT / "data" / "raw" / "EURUSD"

# Frames que el motor usa para B1 (M15 es el nivel de decisión; H4/H1/D1 son contexto HTF).
TF = ["M15", "H1", "H4", "D1"]

ARTIFACTS = []

for tf in TF:
    path = DATA_DIR / f"EURUSD_{tf}.parquet"
    if not path.exists():
        ARTIFACTS.append({
            "path": f"data/raw/EURUSD/EURUSD_{tf}.parquet",
            "sha256": None,
            "bytes": None,
            "timeframe": tf,
            "start_time": None,
            "end_time": None,
            "timezone": None,
            "row_count": None,
            "source_dataset": None,
            "transformation": None,
            "present": False,
            "reason": "file not found",
        })
        continue

    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    size = len(raw)

    # Metadata del parquet
    import pyarrow.parquet as pq
    table = pq.read_table(str(path))
    df = table.to_pandas()

    cols = list(df.columns)
    if "time" in df.columns:
        time_col = "time"
    elif "timestamp" in df.columns:
        time_col = "timestamp"
    else:
        time_col = None

    start = None
    end = None
    tz = None
    n = len(df)

    if time_col is not None and n > 0:
        s = df[time_col]
        if hasattr(s, "min"):
            mn = s.min()
            mx = s.max()
            if hasattr(mn, "tz"):
                tz = str(mn.tz)
            start = str(mn)
            end = str(mx)

    ARTIFACTS.append({
        "path": f"data/raw/EURUSD/EURUSD_{tf}.parquet",
        "sha256": sha,
        "bytes": size,
        "timeframe": tf,
        "start_time": start,
        "end_time": end,
        "timezone": tz,
        "row_count": n,
        "source_dataset": f"EURUSD parquet operativo ({tf})",
        "transformation": "parquet local derivado de Dukascopy intraday CSV monthly; fuente canónica: datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json + 2021_2025_manifest.json",
        "present": True,
        "columns": cols,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_script": "B1_DATA_MANIFEST_V1 — engine/data_feed.py y engine/market_features.py son el consumidor operativo",
    })

OUT = ROOT / "B1_DATA_MANIFEST_V1.json"
OUT.write_text(json.dumps(ARTIFACTS, indent=2, ensure_ascii=False), encoding="utf-8")
print("WROTE", OUT)
print("ARTIFACTS", len(ARTIFACTS))
for a in ARTIFACTS:
    print(a["timeframe"], a["present"], a["row_count"], a["sha256"][:12] if a["sha256"] else None)
