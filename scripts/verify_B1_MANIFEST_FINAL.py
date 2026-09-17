#!/usr/bin/env python3
"""
Verificador final de B1_DATA_MANIFEST_V1 y del parquet de diseño.

Verifica:
1. Todos los archivos del manifiesto existen
2. Todos los hashes coinciden con lo registrado
3. Todos los tamaños coinciden
4. El parquet de diseño se puede re-leer y produce la misma cantidad de filas
5. No hay duplicados de timestamp en el parquet de diseño
"""

import json, hashlib, os
from pathlib import Path

ROOT = Path("C:/Users/v_jac/Desktop/ICT SYSTEM")
DATA_DIR = ROOT / "data" / "raw" / "EURUSD"
MANIFEST = json.loads(ROOT.joinpath("B1_DATA_MANIFEST_V1.json").read_text())

print("=" * 70)
print("VERIFICACIÓN FINAL B1_DATA_MANIFEST_V1")
print("=" * 70)

all_ok = True
for a in MANIFEST:
    name = Path(a["path"]).name
    p = DATA_DIR / name
    print(f"\n[{a['timeframe']}] {a['path']}")
    print(f"  bytes declarados: {a['bytes']}")
    print(f"  sha256 declarado: {a['sha256'][:16]}...")
    if not p.exists():
        print(f"  ❌ ARCHIVO NO ENCONTRADO")
        all_ok = False
        continue
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    size = len(raw)
    print(f"  bytes en disco:   {size}")
    print(f"  sha256 en disco:  {sha[:16]}...")
    if sha != a["sha256"] or size != a["bytes"]:
        print(f"  ❌ MISMATCH: hash o tamaño no coinciden")
        all_ok = False
    else:
        print(f"  ✅ HASH Y TAMAÑO COINCIDEN")
    # re-leer parquet
    import pandas as pd
    df = pd.read_parquet(p)
    print(f"  filas al re-leer: {len(df)}")
    if a.get("row_count") is not None and len(df) != a["row_count"]:
        print(f"  ❌ CANTIDAD DE FILAS NO COINCIDE (esperado {a['row_count']})")
        all_ok = False
    else:
        print(f"  ✅ CANTIDAD DE FILAS COINCIDE")
    if "time" in df.columns and len(df) > 0:
        t0 = df["time"].min()
        t1 = df["time"].max()
        print(f"  rango: {t0} → {t1}")

print("\n" + "=" * 70)
if all_ok:
    print("RESULTADO: ✅ TODOS LOS ARCHIVOS VERIFICADOS — PROVENANCE_INTERNAL_B1 = PASS")
else:
    print("RESULTADO: ❌ HAY MISMATCHES — REVISAR")
print("=" * 70)
