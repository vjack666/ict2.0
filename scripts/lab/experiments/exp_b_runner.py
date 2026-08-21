#!/usr/bin/env python3
"""B1–B5 preflight/runner contract for the reconstructed EXP-B design.

Default mode is deliberately preflight-only. It writes explicit BLOCKED
artifacts when the required PIT-stable navigator branch or canonical M15 data
is unavailable. ``--execute-diagnostic`` is reserved for a separately isolated
diagnostic worktree on ``engine-seq-v2-causal``; it is not a promotion path.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "reports/audits/experiments/current_batch"
SPEC = "docs/experimentos/EXP_B_DESIGN.md"
EXPECTED_BRANCH = "engine-seq-v2-causal"
CANONICAL_M15 = ROOT / "datasets/eurusd_dukascopy_20y/EURUSD_M15.csv"
EXPERIMENTS = {
    "B1": "Context State ALIGNED / AGAINST / NEUTRAL",
    "B2": "HTF ALIGNED-only vs unconditional treatment",
    "B3": "M15 replication with canonical Dukascopy data",
    "B4": "EQ50 location favorable vs non-favorable",
    "B5": "HTF context vs LTF-only ablation",
}


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_branch() -> str:
    return subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute-diagnostic", action="store_true", help="reserved; refuses execution until a B implementation is explicitly enabled")
    args = ap.parse_args()
    branch = git_branch()
    head = git_head()
    now = datetime.now(timezone.utc).isoformat()
    branch_ok = branch == EXPECTED_BRANCH
    m15_ok = CANONICAL_M15.exists()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for exp_id, component in EXPERIMENTS.items():
        blocking_reasons = []
        if exp_id == "B3" and not m15_ok:
            blocking_reasons.append("canonical EURUSD M15 Dukascopy snapshot is absent; parquet substitution is prohibited")
        if exp_id != "B3" and not branch_ok:
            blocking_reasons.append(f"required diagnostic branch is {EXPECTED_BRANCH!r}; current branch is {branch!r}")
        if args.execute_diagnostic:
            blocking_reasons.append("diagnostic execution is not enabled by this preflight runner; implement and review the outcome-R adapter first")
        status = "BLOCKED" if blocking_reasons else "READY"
        reasons = blocking_reasons or ["preflight passed; execution adapter remains a separate reviewed step"]
        raw = {
            "schema_version": "1.0",
            "experiment": f"EXP_{exp_id}",
            "component_isolated": component,
            "status": status,
            "executed": False,
            "pre_registration": SPEC,
            "code_commit": head,
            "branch": branch,
            "generated_at": now,
            "reasons": reasons,
            "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
        }
        audit = {
            "schema_version": "1.0",
            "experiment": f"EXP_{exp_id}",
            "component_isolated": component,
            "code_commit": head,
            "branch": branch,
            "generated_at": now,
            "pre_registration": SPEC,
            "preconditions": {
                "g0_sequence_pit": "PASS scoped; not a navigator FULL-vs-PREFIX proof",
                "required_branch": EXPECTED_BRANCH,
                "current_branch": branch,
                "canonical_m15_present": m15_ok,
            },
            "gate": {"n_ge_30": False, "expectancy_gt_0": False, "ci_lower_gt_0": False, "note": "not executed"},
            "verdict": status,
            "rationale": "; ".join(reasons),
            "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
        }
        (OUT / f"EXP_{exp_id}_raw.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        (OUT / f"EXP_{exp_id}_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
        rows.append({"experiment": f"EXP_{exp_id}", "verdict": status, "reasons": reasons})
    suite = {
        "schema_version": "1.0",
        "suite": "EXP_B_PREFLIGHT",
        "generated_at": now,
        "code_commit": head,
        "branch": branch,
        "pre_registration": SPEC,
        "results": rows,
        "promotion": "BLOCKED",
        "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
    }
    (OUT / "EXP_B_PREFLIGHT.json").write_text(json.dumps(suite, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# EXP-B preflight", "", f"- Branch: `{branch}`", f"- HEAD: `{head}`", f"- Canonical M15 present: `{m15_ok}`", "", "| Experiment | Status | Reason |", "|---|---|---|"]
    lines.extend(f"| {r['experiment']} | **{r['verdict']}** | {'; '.join(r['reasons'])} |" for r in rows)
    lines += ["", "Promotion: **BLOCKED**. These artifacts are explicit preflight decisions, not experimental results."]
    (OUT / "EXP_B_PREFLIGHT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"suite": "EXP_B_PREFLIGHT", "branch": branch, "results": rows}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
