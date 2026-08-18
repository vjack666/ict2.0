"""Bootstrap de auditorías: primera operación obligatoria de Hermes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

from .gate import AuditResult, GateStatus, medianamente_bueno
from .data_integrity import audit_ohlc
from .temporal import audit_events
from .funnel import FunnelAudit

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".hermes" / "audit_state.json"


def _load_rows() -> list[dict]:
    """Carga un fixture mínimo para el smoke audit; datasets reales se conectan después."""
    return [
        {"id": "smoke-1", "time": 1, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1},
        {"id": "smoke-2", "time": 2, "open": 1.1, "high": 1.3, "low": 1.0, "close": 1.2},
    ]


def _run_fix_command() -> int:
    command = os.environ.get("HERMES_FIX_COMMAND", "").strip()
    if not command:
        print("HERMES_FIX_COMMAND no está definido; se detiene para intervención de Hermes.")
        return 2
    return subprocess.call(command, shell=True, cwd=ROOT)


def run_once() -> dict[str, object]:
    rows = _load_rows()
    a0 = audit_ohlc(rows)
    temporal = audit_events([{"id": "smoke-event", "candidate_time": 1, "confirmation_time": 2, "tradable_time": 2, "observation_time": 2}])
    funnel, summary = FunnelAudit().run([
        {"stage": "VALID_BARS", "id": "1", "accepted": True},
        {"stage": "FVG", "id": "fvg-1", "accepted": True},
        {"stage": "OB", "id": "ob-1", "accepted": True},
        {"stage": "LINEAGE", "id": "lin-1", "accepted": True},
        {"stage": "SETUP", "id": "setup-1", "accepted": True},
    ])
    findings = list(a0.findings)
    if temporal:
        findings.extend([])
    score = (a0.metrics.get("audit_score", 0.0) + funnel.metrics.get("audit_score", 0.0)) / 2
    combined_status = GateStatus.FAIL if a0.status is GateStatus.FAIL or temporal else funnel.status
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": combined_status.value,
        "audit_score": score,
        "a0": a0,
        "a7": funnel,
        "funnel_summary": [s.__dict__ for s in summary],
        "temporal_violations": [v.__dict__ for v in temporal],
    }
    return result


def main() -> int:
    max_iter = int(os.environ.get("HERMES_AUDIT_MAX_ITER", "5"))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    for iteration in range(1, max_iter + 1):
        result = run_once()
        result["iteration"] = iteration
        serializable = {
            "timestamp": result["timestamp"],
            "status": result["status"],
            "audit_score": result["audit_score"],
            "temporal_violations": result["temporal_violations"],
            "a0": result["a0"].__dict__,
            "a7": result["a7"].__dict__,
            "funnel_summary": result["funnel_summary"],
            "iteration": iteration,
        }
        STATE.write_text(json.dumps(serializable, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        acceptable = (
            not result["temporal_violations"]
            and result["a0"].status is GateStatus.PASS
            and result["a7"].status is GateStatus.PASS
            and result["audit_score"] >= 0.80
            and medianamente_bueno(
                AuditResult("BOOTSTRAP",  # type: ignore[arg-type]
                            GateStatus.PASS,
                            1,
                            1,
                            0,
                            (),
                            {"audit_score": result["audit_score"]}),
                0.80,
            )
        )
        print(f"Hermes audit iteration {iteration}: status={result['status']} score={result['audit_score']:.3f}")
        if acceptable:
            print("AUDIT GATE: MEDIANAMENTE BUENO — Hermes puede continuar.")
            return 0
        if _run_fix_command() != 0:
            return 2
    print("AUDIT GATE: no se alcanzó el umbral dentro del máximo de iteraciones.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
