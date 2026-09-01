"""ORCHESTRATOR REMAINDER — FASE 6 -> 8 -> 9 -> 10 (EXP-SEQ-CTX-01 OOS).

Se lanza UNA vez que FASE 5 (exp_seq_ctx_01_oos_expansion.py) terminó y escribió
data/learning/seq_ctx_01/OOS_EXPANSION/manifest.json.

Ejecuta en secuencia, fallando cerrado si algún paso falla:
  FASE 6: _oos_sufficiency_verdict.py  (estadístico independiente)
  FASE 8: validate_oos_expansion.py    (data contract + bucket 100%)
  FASE 9: exp_seq_ctx_01_oos_snapshot.py (SOLO si FASE6 = OOS_SUFFICIENT)
  FASE 10: auditoria independiente final (red team) via _audit_oos_final.py

Si FASE 6 = EXHAUSTED (negativo cientifico): NO crea snapshot; emite cierre
cientifico y detiene la investigacion de IA (sin falsificar PASS).

Este script es el encadenamiento autonomo; se corre en background con
notify_on_complete para no requerir sondeo.
"""
from __future__ import annotations
import sys, subprocess, json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
LAB = ROOT / "scripts" / "lab" / "experiments"
OOS = ROOT / "data" / "learning" / "seq_ctx_01" / "OOS_EXPANSION"
PY = "C:/Python314/python.exe"
LOG = OOS / "REMAINDER_run.log"


def run(label: str, script: str) -> int:
    print(f"\n=== {label}: {script} ===", flush=True)
    rc = subprocess.run([PY, str(LAB / script)], cwd=str(ROOT)).returncode
    print(f"=== {label} exit={rc} ===", flush=True)
    return rc


def main() -> int:
    print(f"[REMAINDER] inicio {datetime.now(timezone.utc).isoformat()}", flush=True)
    if not (OOS / "manifest.json").exists():
        print("[REMAINDER][FAIL] FASE5 no escribio manifest.json todavia", flush=True)
        return 1

    # FASE 6 — suficiencia OOS (independiente)
    rc6 = run("FASE6", "_oos_sufficiency_verdict.py")
    verdict_path = OOS / "OOS_SUFFICIENCY_VERDICT.json"
    verdict = json.loads(verdict_path.read_text()).get("verdict") if verdict_path.exists() else None
    print(f"[REMAINDER] FASE6 verdict={verdict} rc={rc6}", flush=True)

    if verdict == "OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE":
        print("[REMAINDER] CIERRE CIENTIFICO NEGATIVO — universo agotado, celdas <30.",
              flush=True)
        print("[REMAINDER] NO se crea snapshot. NO se entrena IA. Se detiene la investigacion.",
              flush=True)
        # FASE 10 (red team) igual documenta el cierre.
        run("FASE10", "_audit_oos_final.py")
        return 0  # cierre honesto, no error de ejecucion

    if verdict != "OOS_SUFFICIENT":
        print(f"[REMAINDER] FASE6 no SUFFICIENT (rc={rc6}); detener sin snapshot.", flush=True)
        return rc6

    # FASE 8 — data contract + bucket 100%
    rc8 = run("FASE8", "validate_oos_expansion.py")
    if rc8:
        print("[REMAINDER][FAIL] FASE8 validacion no PASS; detener.", flush=True)
        return rc8

    # FASE 9 — snapshot (solo porque FASE6=SUFFICIENT y FASE8=PASS)
    rc9 = run("FASE9", "exp_seq_ctx_01_oos_snapshot.py")
    if rc9:
        print("[REMAINDER][FAIL] FASE9 snapshot no creado.", flush=True)
        return rc9

    # FASE 10 — auditoria independiente final
    rc10 = run("FASE10", "_audit_oos_final.py")
    print(f"[REMAINDER] FIN rc10={rc10}", flush=True)
    return rc10


if __name__ == "__main__":
    raise SystemExit(main())
