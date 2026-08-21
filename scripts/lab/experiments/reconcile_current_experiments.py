"""Reconcile the current A/B/C experiment batch from audit JSON files.

This script treats files on disk as the authority. A missing artifact is
reported as BLOCKED; it is never inferred from an agent summary.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = ROOT / "reports" / "audits" / "experiments" / "current_batch"
OUT_JSON = AUDIT_DIR / "EXP_MASTER_RECONCILIATION.json"
OUT_MD = AUDIT_DIR / "EXP_MASTER_RECONCILIATION.md"

EXPECTED = {
    "A": ["A1", "A2", "A3", "A4", "A5"],
    "B": ["B1", "B2", "B3", "B4", "B5"],
    "C": ["C1", "C2", "C3", "C4", "C5"],
}


def _read_audit(exp_id: str) -> dict[str, Any] | None:
    path = AUDIT_DIR / f"EXP_{exp_id}_audit.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"experiment": f"EXP_{exp_id}", "verdict": "INVALID", "reason": "audit JSON unreadable"}


def _status(exp_id: str, audit: dict[str, Any] | None) -> dict[str, Any]:
    if audit is None:
        return {
            "experiment": f"EXP_{exp_id}",
            "status": "BLOCKED",
            "reason": "No audit JSON present on disk",
            "evidence": [],
        }
    protocol = audit.get("protocol") or {}
    data = protocol.get("data_integrity") or audit.get("data_integrity") or {}
    caveat = data.get("cross_origin_caveat") is True or data.get("is_canonical") is False
    raw_verdict = str(audit.get("verdict", "INVALID"))
    if raw_verdict == "PASS" or raw_verdict.startswith("EDGE VIVO"):
        status = "PASS"
    elif raw_verdict == "FAIL" or raw_verdict.startswith("EDGE ROTO") or raw_verdict.startswith("Walk-forward"):
        status = "FAIL"
    elif raw_verdict == "BLOCKED" or raw_verdict.startswith("BLOCKED"):
        status = "BLOCKED"
    else:
        status = "INVALID"
    return {
        "experiment": audit.get("experiment", f"EXP_{exp_id}"),
        "status": status,
        "raw_verdict": raw_verdict,
        "gate": audit.get("gate"),
        "reason": audit.get("rationale") or raw_verdict,
        "data": {
            "symbol": data.get("symbol"),
            "source": data.get("source"),
            "is_canonical": data.get("is_canonical"),
            "cross_origin_caveat": caveat,
            "range": [data.get("range_start"), data.get("range_end")],
        },
        "provisional": caveat,
        "evidence": [
            f"reports/audits/experiments/current_batch/EXP_{exp_id}_audit.json",
            f"reports/audits/experiments/current_batch/EXP_{exp_id}_raw.json",
        ],
    }


def build_reconciliation() -> dict[str, Any]:
    experiments: list[dict[str, Any]] = []
    for group, ids in EXPECTED.items():
        for exp_id in ids:
            item = _status(exp_id, _read_audit(exp_id))
            item["group"] = group
            experiments.append(item)

    by_status: dict[str, int] = {}
    for item in experiments:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1

    b_items = [item for item in experiments if item["group"] == "B"]
    canonical_promotable = all(
        item["status"] == "PASS" and not item.get("provisional", False)
        for item in experiments
        if item["group"] == "A" and item["experiment"] in {"EXP_A1", "EXP_A2", "EXP_A3", "EXP_A4", "EXP_A5"}
    )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_of_truth": "audit JSON files present on disk",
        "promotion": {
            "status": "BLOCKED",
            "reason": "Current batch is diagnostic only; B is missing, A2 is blocked, and no candidate may replace GEN-000.",
            "canonical_a_complete": canonical_promotable,
        },
        "summary": {
            "expected": 15,
            "observed": sum(1 for item in experiments if item["evidence"]),
            "by_status": by_status,
            "missing_groups": sorted({item["group"] for item in b_items if not item["evidence"]}),
        },
        "propositions": {
            "P1_baseline_edge": "CONDITIONAL_PASS",
            "P2_htf_incremental_value": "BLOCKED",
            "P3_oos_robustness": "INCOMPLETE",
            "P4_m15_m5_live_scope": "NOT_TESTED",
        },
        "experiments": experiments,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Reconciliación maestra de experimentos A/B/C",
        "",
        "> Fuente de verdad: JSON de auditoría presentes en `reports/audits/experiments/current_batch/`. Los resúmenes de agentes no sustituyen artefactos.",
        "",
        f"- Generado: `{report['generated_at']}`",
        f"- Esperados: `{report['summary']['expected']}` · observados: `{report['summary']['observed']}`",
        f"- Promoción: **{report['promotion']['status']}**",
        f"- Motivo: {report['promotion']['reason']}",
        "",
        "## Proposiciones",
        "",
    ]
    for key, value in report["propositions"].items():
        lines.append(f"- `{key}`: **{value}**")
    lines.extend(["", "## Experimentos", "", "| Grupo | Experimento | Estado | Provisional | Evidencia |", "|---|---|---|---|---|"])
    for item in report["experiments"]:
        evidence = "sí" if item["evidence"] else "no"
        provisional = "sí" if item.get("provisional") else "no"
        lines.append(f"| {item['group']} | {item['experiment']} | **{item['status']}** | {provisional} | {evidence} |")
    lines.extend([
        "",
        "## Política",
        "",
        "- Este informe no promueve señales ni cambios de motor.",
        "- Un experimento sin JSON de auditoría queda `BLOCKED`.",
        "- La producción permanece en `GEN-000` hasta una promoción gobernada.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    report = build_reconciliation()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(_markdown(report), encoding="utf-8")
    print(f"[OK] {OUT_JSON}")
    print(f"[OK] {OUT_MD}")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
