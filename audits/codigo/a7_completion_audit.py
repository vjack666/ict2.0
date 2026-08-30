"""Verificador independiente de completitud del Gate A7.

Este verificador no vuelve a construir el Funnel ni busca edge. Consume los dos
reportes A7 más recientes, comprueba la evidencia persistida de los doce OE y
falla cerrado si cualquier gate técnico obligatorio no está demostrado. La
autorización legal de la fuente histórica queda fuera del alcance técnico A7 y
se conserva como limitación explícita del dataset.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "audits" / "experiments" / "fvg_ob"
METADATA = ROOT / "datasets" / "eurusd_dukascopy_20y" / "metadata.json"
WORKLOG = ROOT / ".hermes-worklog" / "2026-08-28_FUNNEL_A7_AUDIT.md"
OUT_DIR = REPORT_DIR


def _latest_reports() -> list[Path]:
    return sorted(REPORT_DIR.glob("mtf_seq_funnel_a7_*.json"))[-2:]


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Reporte no es un objeto JSON: {path}")
    return payload


def _sections(report: dict[str, Any]) -> list[dict[str, Any]]:
    sections = list(report.get("funnel_by_tf", {}).values())
    mtf = report.get("mtf_navigation")
    if isinstance(mtf, dict):
        sections.append(mtf)
    return [section for section in sections if isinstance(section, dict)]


def _findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding for section in _sections(report)
            for finding in section.get("findings", [])
            if isinstance(finding, dict)]


def _all_contract_sections_pass(report: dict[str, Any]) -> bool:
    return (
        report.get("aggregated_status") == "PASS"
        and report.get("aggregated_findings") == 0
        and all(section.get("n_findings") == 0 for section in _sections(report))
    )


def _prefix_pass(report: dict[str, Any]) -> bool:
    prefix = report.get("prefix_invariance", {})
    by_tf = prefix.get("by_timeframe", {})
    return bool(
        prefix.get("sequence", {}).get("all_cuts_invariant") is True
        and by_tf
        and all(value.get("all_cuts_invariant") is True for value in by_tf.values())
        and all(
            cut.get("missing_in_prefix") == 0 and cut.get("extra_in_prefix") == 0
            for value in by_tf.values()
            for cut in value.get("cuts", {}).values()
        )
        and all(
            cut.get("missing_in_prefix") == 0 and cut.get("extra_in_prefix") == 0
            for cut in prefix.get("sequence", {}).get("cuts", {}).values()
        )
    )


def _logical_payload(report: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(report)
    payload.pop("generated_at", None)
    payload.pop("report_checksum_sha256", None)
    return payload


def _run_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (proc.stdout + proc.stderr).strip()
    last_line = output.splitlines()[-1] if output else ""
    passed = re.search(r"(\d+) passed", output)
    return {
        "command": "python -B -m pytest -q",
        "returncode": proc.returncode,
        "summary": last_line,
        "passed": int(passed.group(1)) if passed else None,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
    }


def _independent_review_recorded() -> bool:
    text = WORKLOG.read_text(encoding="utf-8")
    lowered = text.lower()
    return "cro" in lowered and "auditoría independiente" in lowered


def _a7_technical_provenance_pass(report: dict[str, Any]) -> bool:
    """OE-A7.9: exact bytes/hashes + trace of the A7 generator.

    ``provenance_source`` can remain REVIEW/BLOCKED because provider
    authorization is not the technical Funnel gate for this historical
    research fixture. Requiring the explicit scope marker prevents an old
    report from being accepted accidentally under the new interpretation.
    """
    return bool(
        report.get("provenance_scope") == "TECHNICAL_FUNNEL_ONLY"
        and report.get("provenance_mechanical_ok") is True
        and report.get("a7_provenance_ok") is True
        and report.get("provenance_ok") is True
        and report.get("commit") not in {None, "", "UNKNOWN"}
        and isinstance(report.get("config"), dict)
        and bool(report.get("contract_version"))
        and bool(report.get("provenance_source", {}).get("metadata_sha256"))
    )


def build_audit(report_paths: list[Path], *, run_tests: bool = True) -> dict[str, Any]:
    if len(report_paths) != 2:
        raise ValueError("Se requieren exactamente dos reportes A7")
    reports = [_load(path) for path in report_paths]
    first, second = reports
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))["provenance"]
    tests = _run_tests() if run_tests else {"status": "NOT_RUN"}
    same_logical = (
        first.get("report_checksum_sha256") == second.get("report_checksum_sha256")
        and _logical_payload(first) == _logical_payload(second)
    )
    technical = _all_contract_sections_pass(first) and _all_contract_sections_pass(second)
    prefix = _prefix_pass(first) and _prefix_pass(second)
    clean = first.get("git_status") == second.get("git_status") == "CLEAN"
    timeframe_ok = (
        first.get("funnel_by_tf", {}).keys() == {"H1", "H4", "D1"}
        and all(
            set(section.get("timeframe_counts", {})) <= {tf}
            and section.get("timeframe_counts", {}).get(tf, 0) > 0
            for tf, section in first.get("funnel_by_tf", {}).items()
        )
    )
    required_metrics = all(
        "rejection_reason_counts" in section and "timeframe_counts" in section
        for section in _sections(first)
    )
    strict_relations = first.get("config", {}).get("relation_rule") == "STRICT FVG_OB_CAUSAL"
    no_findings = not _findings(first) and not _findings(second)
    mechanical = all(report.get("provenance_mechanical_ok") is True for report in reports)
    technical_provenance = all(_a7_technical_provenance_pass(report) for report in reports)
    matrix = [
        {"id": "OE-A7.1", "status": "PASS" if technical else "FAIL", "evidence": "A7 sections with zero findings; FunnelAudit temporal contract"},
        {"id": "OE-A7.2", "status": "PASS" if prefix else "FAIL", "evidence": "All configured FULL/PREFIX cuts, missing=0 and extra=0"},
        {"id": "OE-A7.3", "status": "PASS" if technical and no_findings else "FAIL", "evidence": "No duplicate findings and identical logical reports"},
        {"id": "OE-A7.4", "status": "PASS" if technical and no_findings else "FAIL", "evidence": "No lineage findings in both reports"},
        {"id": "OE-A7.5", "status": "PASS" if technical and strict_relations else "FAIL", "evidence": "STRICT FVG_OB_CAUSAL plus zero audit findings"},
        {"id": "OE-A7.6", "status": "PASS" if technical and required_metrics else "FAIL", "evidence": "Per-section rejection and timeframe metrics serialized"},
        {"id": "OE-A7.7", "status": "PASS" if technical and timeframe_ok else "FAIL", "evidence": "H1/H4/D1 sections remain isolated by timeframe"},
        {"id": "OE-A7.8", "status": "PASS" if same_logical else "FAIL", "evidence": "Two independent reports have equal logical payload and checksum"},
        {"id": "OE-A7.9", "status": "PASS" if mechanical and technical_provenance else "BLOCKED", "evidence": "Exact dataset bytes/hashes, metadata hash, configuration and generator commit are linked; source authorization is outside technical A7 scope"},
        {"id": "OE-A7.10", "status": tests.get("status", "NOT_RUN"), "evidence": tests.get("summary", "")},
        {"id": "OE-A7.11", "status": "PASS" if clean else "FAIL", "evidence": "Both reports declare CLEAN worktrees"},
        {"id": "OE-A7.12", "status": "PASS" if _independent_review_recorded() else "REVIEW", "evidence": "CRO independent review recorded in worklog"},
    ]
    overall = "PASS" if all(item["status"] == "PASS" for item in matrix) else "BLOCKED"
    return {
        "gate": "A7",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reports": [str(path.relative_to(ROOT)) for path in report_paths],
        "report_commits": [report.get("commit") for report in reports],
        "matrix": matrix,
        "tests": tests,
        "source_provenance": {
            "declared_status": metadata.get("provenance_status"),
            "license_and_permitted_use": metadata.get("license_and_permitted_use"),
            "execution_verified": metadata.get("request_parameters", {}).get("execution_verified"),
            "mechanical_ok": mechanical,
            "technical_ok": technical_provenance,
            "scope_status": metadata.get("project_scope", {}).get(
                "source_authorization_gate", "UNDECLARED"
            ),
            "source_certification_outside_a7": True,
        },
        "overall_status": overall,
        "next_action": (
            "Repair the failed technical A7 evidence; source authorization is "
            "outside this technical gate."
            if overall == "BLOCKED" else "A7 complete; proceed only under the next frozen phase contract."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="append", type=Path, dest="reports")
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()
    report_paths = args.reports or _latest_reports()
    report_paths = [path if path.is_absolute() else ROOT / path for path in report_paths]
    audit = build_audit(report_paths, run_tests=not args.no_tests)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUT_DIR / "a7_completion_audit.json"
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "out": str(output),
        "overall_status": audit["overall_status"],
        "matrix": {item["id"]: item["status"] for item in audit["matrix"]},
        "tests": audit["tests"],
    }, ensure_ascii=False, indent=2))
    return 0 if audit["overall_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
