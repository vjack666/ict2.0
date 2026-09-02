"""Aggregate the frozen yearly T7f audits without rewriting replay evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audits.codigo.mtf_replay_t7f import DEFAULT_OUTPUT


REQUIRED_GATES = ("determinism", "full_prefix", "schema", "chunk_manifest")


def aggregate(root: Path, *, years: range = range(2006, 2011)) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    missing: list[int] = []
    for year in years:
        path = root / str(year) / "t7f_audit.json"
        if not path.is_file():
            missing.append(year)
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        reports.append(report)
    technical_pass = not missing and all(
        report.get("status") == "PASS_TECHNICAL_BLOCKED_PROVENANCE"
        and all(report.get("gates", {}).get(gate) is True for gate in REQUIRED_GATES)
        for report in reports
    )
    return {
        "run_id": "t7f_2006_2010_completion",
        "years_requested": list(years),
        "years_found": [report.get("year") for report in reports],
        "missing_years": missing,
        "technical_gates_pass": technical_pass,
        "population": {
            "complete_records": sum(int(report["counts"]["complete_records"]) for report in reports),
            "eligible_records": sum(int(report["counts"]["eligible_records"]) for report in reports),
            "episodes": sum(int(report["counts"]["episodes"]) for report in reports),
        },
        "yearly": [
            {
                "year": report["year"], "status": report["status"],
                "gates": {gate: report["gates"][gate] for gate in REQUIRED_GATES},
                "counts": report["counts"], "checksum": report["checksum"],
                "dataset_hash": report["dataset_hash"],
            }
            for report in reports
        ],
        "provenance": {
            "formal_status": "BLOCKED_PROVENANCE",
            "certified": False,
            "reason": "Dukascopy license/permitted-use and acquired_at_utc remain unknown.",
        },
        "ai_training_authorized": False,
        "can_trade": False,
        "status": "PASS_TECHNICAL_BLOCKED_PROVENANCE" if technical_pass else "FAIL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT / "t7f_2006_2010_completion.json")
    args = parser.parse_args()
    result = aggregate(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "population": result["population"]}, sort_keys=True))
    if result["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
