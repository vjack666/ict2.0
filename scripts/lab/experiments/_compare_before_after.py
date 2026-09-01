"""Script auxiliar de comparacion ANTES vs DESPUES de la regeneracion
EXP-SEQ-CTX-01 (context_bucket corregido). Solo lectura; no modifica nada.
Usa los manifest guardados en disco: ANTES = manifest_before.json (copia de
respaldo tomada antes de regenerar), DESPUES = manifest.json actual.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "learning" / "seq_ctx_01"

def cell(map_before, did, bucket, split="HOLDOUT"):
    return map_before["datasets"][did]["by_bucket_split"][split][bucket]

def main():
    before = json.loads((OUT / "manifest_before.json").read_text())
    after = json.loads((OUT / "manifest.json").read_text())

    print("=== COMPARACION ANTES vs DESPUES (regeneracion context_bucket corregido) ===\n")
    for tag, m in (("ANTES", before), ("DESPUES", after)):
        print(f"--- {tag} ---")
        for did, meta in m["datasets"].items():
            bs = meta["by_bucket_split"]
            ho = bs["HOLDOUT"]
            print(f"  {did}: total={meta['rows']} | DESIGN {bs['DESIGN']} | "
                  f"VAL {bs['VALIDATION']} | HOLDOUT {ho}")
        print(f"  OOS status: {m['oos_sufficiency']['status']}\n")

    print("=== DIFERENCIA HOLDOUT (DESPUES - ANTES) ===")
    for did in before["datasets"]:
        for bucket in ("ALIGNED", "NEUTRAL", "AGAINST"):
            b = before["datasets"][did]["by_bucket_split"]["HOLDOUT"][bucket]
            a = after["datasets"][did]["by_bucket_split"]["HOLDOUT"][bucket]
            delta = a - b
            print(f"  {did} HOLDOUT {bucket}: ANTES={b} DESPUES={a} Δ={delta:+d}")

    print("\n=== GATE OOS (criterio pre-registrado n>=30 por celda variante×bucket×HOLDOUT) ===")
    cells = {}
    for did in after["datasets"]:
        for bucket in ("ALIGNED", "NEUTRAL", "AGAINST"):
            n = after["datasets"][did]["by_bucket_split"]["HOLDOUT"][bucket]
            cells[f"{did}:{bucket}"] = n
    sufficient = all(n >= 30 for n in cells.values())
    for k, v in cells.items():
        mark = "OK" if v >= 30 else "SUBPOWERED"
        print(f"  {k}: n={v} [{mark}]")
    print(f"\n  OOS_EVIDENCE_GATE = {'PASS' if sufficient else 'SUBPOWERED'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
