"""FASE 6 — GATE DE SUFICIENCIA OOS (Estadístico Independiente).

Lee el manifest de la ampliación OOS y emite veredicto INDEPENDIENTE del
ejecutor (Agente 5). No calcula edge; solo potencia muestral.

Veredicto permitido:
  - OOS_SUFFICIENT: toda celda (structure_mode, context_bucket, HOLDOUT) >= 30
  - SUBPOWERED: alguna celda < 30 y aun queda universo pre-registrado
  - OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE: alguna celda < 30 y
    universo pre-registrado agotado

NO reduce el umbral. NO combina celdas. NO cambia buckets.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "data" / "learning" / "seq_ctx_01" / "OOS_EXPANSION" / "manifest.json"
PREREG = ROOT / "docs" / "planificacion" / "OOS_EXPANSION_PREREGISTRATION.md"
UNIVERSE_SYMS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY", "XAUUSD"]
MODES = ["canonical_bos", "lite"]
CRITERION_N = 30


def main() -> int:
    if not MANIFEST.exists():
        print(f"[FASE6][FAIL] manifest ausente: {MANIFEST}")
        return 1
    if not PREREG.exists():
        print(f"[FASE6][FAIL] preregistro ausente: {PREREG}")
        return 1
    m = json.loads(MANIFEST.read_text())
    cells = m.get("holdout_cells", {})
    universe = m.get("universe", {})
    syms_used = universe.get("symbols", [])

    print(f"[FASE6] celdas HOLDOUT evaluadas: {len(cells)}")
    failing = {k: v for k, v in cells.items() if v < CRITERION_N}
    for k, v in sorted(cells.items()):
        flag = "OK" if v >= CRITERION_N else "BAJO"
        print(f"  {k:42s} n={v:4d}  [{flag}]")

    # ¿Universo pre-registrado agotado? (los 8 símbolos procesados)
    exhausted = set(syms_used) >= set(UNIVERSE_SYMS)

    if not failing:
        verdict = "OOS_SUFFICIENT"
    elif exhausted:
        verdict = "OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE"
    else:
        verdict = "SUBPOWERED"

    report = {
        "gate": "OOS_SUFFICIENCY",
        "criterion": f"n >= {CRITERION_N} per (structure_mode, context_bucket, HOLDOUT)",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "holdout_cells": cells,
        "failing_cells": failing,
        "universe_symbols_used": syms_used,
        "universe_exhausted": exhausted,
        "verdict": verdict,
        "note": ("Todas las celdas HOLDOUT alcanzan potencia." if verdict == "OOS_SUFFICIENT"
                 else "Celdas con n<30. Universo agotado => cierre cientifico negativo honesto (no rebajar umbral)."
                 if verdict.startswith("OOS_EXPANSION_EXHAUSTED") else
                 "Celdas con n<30 pero universo no agotado."),
    }
    out = ROOT / "data" / "learning" / "seq_ctx_01" / "OOS_EXPANSION" / "OOS_SUFFICIENCY_VERDICT.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\n[FASE6] VEREDICTO: {verdict}")
    print(f"[FASE6] reporte: {out}")
    # Codigo de salida: 0 si SUFFICIENT, 2 si EXHAUSTED (negativo cientifico), 1 si SUBPOWERED
    return {"OOS_SUFFICIENT": 0, "SUBPOWERED": 1,
            "OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE": 2}[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
