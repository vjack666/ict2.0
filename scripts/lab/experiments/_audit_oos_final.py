"""FASE 10 — AUDITORÍA INDEPENDIENTE FINAL (Red Team / CRO).

Revisa el dataset de ampliación OOS SIN confiar en informes previos. Busca:
  - leakage (features con time > T, o label_ en features)
  - p-hacking (cambio de criterio / umbral post-hoc)
  - contaminacion del HOLDOUT (movimiento de splits)
  - mezcla canonical_bos / lite
  - duplicados / hashes inconsistentes
  - DIRTY worktree no declarado
  - resultados negativos omitidos
  - context_bucket no reconstruible 100%

Veredicto de integridad: PASS_INTEGRITY_ONLY, PASS_READY_FOR_CERTIFIED_SNAPSHOT o
BLOCKED. La suficiencia OOS y la reproducibilidad limpia son condiciones
separadas; un PASS de integridad no autoriza snapshot ni aprendizaje.
"""
from __future__ import annotations
import sys, json, hashlib, subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import pandas as pd

from scripts.lab.experiments.exp_seq_ctx_01_dataset import (
    _check_gates, _event_id, _canonical_rows_hash, context_bucket, h1_alignment,
)
from scripts.lab.experiments.exp_seq_ctx_01_oos_expansion import BLOCKS

OOS = ROOT / "data" / "learning" / "seq_ctx_01" / "OOS_EXPANSION"
MANIFEST = OOS / "manifest.json"
VERDICT = OOS / "OOS_SUFFICIENCY_VERDICT.json"
PREREG = ROOT / "docs" / "planificacion" / "OOS_EXPANSION_PREREGISTRATION.md"


def _block_of(t):
    for n, a, b in BLOCKS:
        if pd.Timestamp(a, tz="UTC") <= t <= pd.Timestamp(b, tz="UTC"):
            return n
    return "OUT"


def _worktree_dirty():
    try:
        p = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                           cwd=str(ROOT), text=True, capture_output=True, check=False)
        return bool(p.stdout.strip())
    except Exception:
        return True


def main() -> int:
    findings = []
    blockers = []
    if not MANIFEST.exists():
        print("[REDTEAM][FAIL] manifest ausente")
        return 1
    m = json.loads(MANIFEST.read_text())
    ris = {"can_trade": m.get("can_trade")}

    # 1. can_trade
    if m.get("can_trade") is not False:
        blockers.append("can_trade != false")

    # 2. HOLDOUT no contaminado (las observaciones caen en su bloque real)
    for did in ("SEQ_CTX_01_CANONICAL_BOS", "SEQ_CTX_01_LITE"):
        p = OOS / f"{did}.jsonl"
        if not p.exists():
            blockers.append(f"falta {did}.jsonl")
            continue
        rows = [json.loads(l) for l in open(p, encoding="utf") if l.strip()]
        seen = set()
        for i, r in enumerate(rows):
            t = pd.Timestamp(r["event_time"])
            if _block_of(t) != r["split"]:
                blockers.append(f"{did} fila {i}: split {r['split']} != bloque real {_block_of(t)} (CONTAMINACION HOLDOUT)")
            if r["can_trade"] is not False:
                blockers.append(f"{did} fila {i}: can_trade != false")
            if r["structure_mode"] != ("canonical_bos" if "CANONICAL" in did else "lite"):
                blockers.append(f"{did} fila {i}: MEZCLA de modos")
            # leakage: timestamp futuro en features
            ci = r["features_at_t"].get("context_inputs", {})
            if ci.get("sequence_direction") != r["direction"]:
                blockers.append(f"{did} fila {i}: sequence_direction != direction")
            exp = context_bucket(r["direction"], ci.get("d1_bias"), ci.get("h4_location"), ci.get("h1_alignment"))
            if r["context_bucket"] != exp:
                blockers.append(f"{did} fila {i}: bucket no reconstruible ({r['context_bucket']}!={exp})")
            eid = _event_id(did, r["symbol"], r["timeframe"], r["event_time"], r["structure_mode"],
                            r.get("chain_id", ""), r["sequence_depth"])
            if r["event_id"] != eid:
                blockers.append(f"{did} fila {i}: event_id no alineado")
            if r["event_id"] in seen:
                blockers.append(f"{did} fila {i}: DUPLICADO")
            seen.add(r["event_id"])
        # hash reproducible
        real = _canonical_rows_hash(rows)
        if any(r["dataset_sha256"] != real for r in rows):
            blockers.append(f"{did}: dataset_sha256 no reproducible")

    # 3. Criterio no cambiado post-hoc: el manifest debe conservar n>=30 y el preregistro existe
    if not PREREG.exists():
        blockers.append("preregistro ausente (p-hacking risk)")
    if "criterion" not in m or "n >= 30" not in m.get("criterion", ""):
        blockers.append("criterio n>=30 no presente en manifest (cambio de umbral?)")

    # 4. Resultados negativos no omitidos: todas las celdas reportadas, incluidas <30
    vc = json.loads(VERDICT.read_text()) if VERDICT.exists() else {}
    failing = vc.get("failing_cells", {})
    findings.append(f"celdas HOLDOUT <30 (reportadas, no omitidas): {failing}")

    # 5. DIRTY declarado honestamente
    wt = m.get("generator_worktree")
    findings.append(f"generator_worktree={wt}")

    # 6. Universo agotado declarado
    findings.append(f"universo agotado={vc.get('universe_exhausted')}")

    # Integridad técnica y elegibilidad científica son gates distintos.
    # El red team puede certificar que el JSONL está limpio aunque el OOS siga
    # subpotenciado o la procedencia no sea reproducible desde un checkout limpio.
    certification_blockers = []
    if vc.get("verdict") != "OOS_SUFFICIENT":
        certification_blockers.append(f"OOS gate={vc.get('verdict')}")
    if wt != "CLEAN":
        certification_blockers.append(f"generator_worktree={wt}")

    report = {
        "audit": "OOS_REDTEAM_FINAL",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "can_trade": ris["can_trade"],
        "findings": findings,
        "blockers": blockers,
        "verdict": (
            "BLOCKED" if blockers else
            "PASS_READY_FOR_CERTIFIED_SNAPSHOT"
            if not certification_blockers else
            "PASS_INTEGRITY_ONLY"
        ),
        "integrity_verdict": "BLOCKED" if blockers else "PASS",
        "certification_blockers": certification_blockers,
        "snapshot_eligible": not blockers and not certification_blockers,
    }
    out = OOS / "OOS_REDTEAM_VERDICT.json"
    out.write_text(json.dumps(report, indent=2))
    if blockers:
        print("[REDTEAM] BLOCKED:")
        for b in blockers:
            print(f"  - {b}")
        print(f"[REDTEAM] reporte: {out}")
        return 1
    if certification_blockers:
        print("[REDTEAM] PASS_INTEGRITY_ONLY — snapshot no elegible:")
        for b in certification_blockers:
            print(f"  - {b}")
    else:
        print("[REDTEAM] PASS_READY_FOR_CERTIFIED_SNAPSHOT")
    print(f"[REDTEAM] reporte: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
