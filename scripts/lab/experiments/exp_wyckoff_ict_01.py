"""EXP-WYCKOFF-ICT-01 — WYCKOFF x ICT CONFLICT (ejecucion cientifica local).

Pre-registro: docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md
Este script aplica el VEREDICTO MECANICO (§9) sobre els JSON de conteos ya
generado por wyckoff_feasibility_counts.py (v2 corregido, procedencia limpia).

NO re-corre el motor de secuencia (reusa el JSON). NO entrena IA, NO opera,
NO modifica datasets. can_train=false, can_trade=false.

Veredicto mecanico (§9):
  SUPPORTED     : >=1 celda primaria con n>=n_required Y delta excluye 0 (IC95)
                  tras correccion por comparaciones multiples.
  FALSIFIED     : modelo anidado no mejora (delta no significativo en ninguna
                  celda primaria tras correccion) con n suficiente.
  INSUFFICIENT_N: n por celda < n_required (o inestabilidad de signo / holdout
                  subpotenciado). Cierre negativo honesto; NO se fuerza PASS.
  INVALID       : cualquier leakage PIT, cambio de protocolo post-result, o
                  violacion de can_train=false.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "wyckoff_ict_01"
COUNTS_JSON = OUT_DIR / "feasibility_counts_v2.json"
REPORT_JSON = OUT_DIR / "exp_wyckoff_ict_01_report.json"
HOLDOUT_START = "2021-01-01"

PRIMARY_CELLS = [("ALIGNED",), ("AGAINST",)]  # celdas de interes primarias (§4, §7)


def _load() -> dict:
    if not COUNTS_JSON.exists():
        raise SystemExit(f"Falta {COUNTS_JSON}. Ejecuta primero wyckoff_feasibility_counts.py")
    return json.loads(COUNTS_JSON.read_text(encoding="utf-8"))


def _verdict(counts: dict) -> dict:
    n_req = counts.get("n_required_per_group", 389)
    tfs = counts.get("timeframes", [])
    audit = {"n_required": n_req, "per_tf": {}, "primary_cells": {}, "gates": {}}

    # Gate PIT (reusa gate_wyckoff_pit.json si existe)
    pit = (OUT_DIR / "gate_wyckoff_pit.json")
    if pit.exists():
        g = json.loads(pit.read_text(encoding="utf-8"))
        audit["gates"]["pit"] = g.get("status", "UNKNOWN")
    else:
        audit["gates"]["pit"] = "NOT_RUN"

    # Procedencia
    audit["gates"]["provenance"] = counts.get("generator_worktree", "UNKNOWN")
    audit["gates"]["generator_commit"] = counts.get("generator_commit", "UNKNOWN")

    insufficient_any = False
    supported_any = False
    for tf in tfs:
        c = counts["counts"][tf]["cells_primary"]
        audit["per_tf"][tf] = {
            "ALIGNED": dict(c.get("ALIGNED", {})),
            "AGAINST": dict(c.get("AGAINST", {})),
            "NEUTRAL": dict(c.get("NEUTRAL", {})),
        }
        for ict in ("ALIGNED", "AGAINST"):
            cell = c.get(ict, {})
            conflict = cell.get("CONFLICT", 0)
            non = cell.get("NON_CONFLICT", 0)
            audit["primary_cells"][f"{tf}|{ict}"] = {
                "CONFLICT": conflict, "NON_CONFLICT": non,
                "n_primary_sum": conflict + non,
            }
            # Criterio §9: para SUPPORTED necesitaria n>=n_req en celda primaria
            # y delta significativo; sin outcomes aqui solo evaluamos factibilidad.
            if max(conflict, non) < n_req:
                insufficient_any = True
            # (delta significativo requiere outcomes; no disponibles en factibilidad)

    # Veredicto mecanico (factibilidad pre-registro §9 + §5)
    if audit["gates"]["provenance"] != "CLEAN":
        verdict = "INVALID_PROVENANCE"
    elif audit["gates"]["pit"] not in ("PASS", "NOT_RUN"):
        verdict = "INVALID_PIT"
    elif insufficient_any:
        verdict = "INSUFFICIENT_N"
    else:
        # n suficiente en todas las celdas primarias; sin outcomes no puede decir
        # SUPPORTED/FALSIFIED -> requiere la fase de outcomes (fuera de alcance hoy)
        verdict = "FEASIBLE_AWAITING_OUTCOMES"

    audit["verdict"] = verdict
    return audit


def main() -> int:
    counts = _load()
    audit = _verdict(counts)
    REPORT_JSON.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    print("=== EXP-WYCKOFF-ICT-01 — VEREDICTO MECANICO ===")
    print(f"  generator_commit   : {audit['gates']['generator_commit']}")
    print(f"  generator_worktree  : {audit['gates']['provenance']}")
    print(f"  PIT gate            : {audit['gates']['pit']}")
    print(f"  n_required/grupo    : {audit['n_required']}")
    for k, v in audit["primary_cells"].items():
        print(f"  celda {k}: CONFLICT={v['CONFLICT']} NON={v['NON_CONFLICT']} (max<{audit['n_required']}? {max(v['CONFLICT'], v['NON_CONFLICT']) < audit['n_required']})")
    print(f"  VERDICTO            : {audit['verdict']}")
    print(f"  report -> {REPORT_JSON}")
    # Salida legible para el cerrador
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
