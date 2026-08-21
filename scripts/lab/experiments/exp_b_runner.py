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
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

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


def _bucket(direction: int, bias: str) -> str:
    if bias in {"UNKNOWN", "MIXED", "None"}:
        return "NEUTRAL"
    wanted = "BULLISH" if direction == 1 else "BEARISH"
    return "ALIGNED" if bias == wanted else "AGAINST"


def _location_label(state, direction: int) -> str:
    layers = getattr(state, "layers", {}) or {}
    layer = layers.get("H4") or layers.get("D1")
    if layer is None or layer.range_high is None or layer.range_low is None:
        return "UNKNOWN"
    mid = 0.5 * (float(layer.range_high) + float(layer.range_low))
    close = float(layer.last_close)
    location = "DISCOUNT" if close < mid else ("PREMIUM" if close > mid else "EQ")
    favorable = (direction == 1 and location == "DISCOUNT") or (direction == -1 and location == "PREMIUM")
    return "FAVORABLE" if favorable else "OTHER"


def _delta_wr_ci(left: list[dict], right: list[dict], seed: int = 424242) -> dict:
    left_closed = [r for r in left if r.get("exit_r") is not None]
    right_closed = [r for r in right if r.get("exit_r") is not None]
    if not left_closed or not right_closed:
        return {"delta_wr": None, "ci95": None, "n_left": len(left_closed), "n_right": len(right_closed)}
    lx = np.array([1.0 if float(r["exit_r"]) > 0 else 0.0 for r in left_closed])
    rx = np.array([1.0 if float(r["exit_r"]) > 0 else 0.0 for r in right_closed])
    rng = np.random.default_rng(seed)
    draws = np.empty(2000, dtype=float)
    for i in range(len(draws)):
        draws[i] = float(rng.choice(lx, len(lx), replace=True).mean() - rng.choice(rx, len(rx), replace=True).mean())
    return {
        "delta_wr": round(float(lx.mean() - rx.mean()), 4),
        "ci95": [round(float(np.quantile(draws, 0.025)), 6), round(float(np.quantile(draws, 0.975)), 6)],
        "n_left": len(left_closed),
        "n_right": len(right_closed),
        "bootstrap_resamples": 2000,
        "bootstrap_seed": seed,
    }


def _run_diagnostic() -> int:
    """Run B1/B2/B4/B5 as explicitly non-promotable diagnostics."""
    from engine.mtf_navigation import MTFNavigator, NavigatorConfig
    from scripts.lab.experiments import exp_agentA_runner as protocol

    t0 = time.time()
    protocol.RANGE_START = "2019-01-01"
    protocol.RANGE_END = "2024-12-31"
    frames = {}
    for tf in ("D1", "H4", "H1"):
        frames[tf] = protocol.load_slice_csv(ROOT / "datasets/eurusd_dukascopy_20y" / f"EURUSD_{tf}.csv")
    h1 = frames["H1"]
    nav = MTFNavigator(frames, NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
    times = list(h1["time"])
    context_cache: dict[tuple[int, int], str] = {}

    def context_label(bar: int, direction: int) -> str:
        key = (int(bar), int(direction))
        if key in context_cache:
            return context_cache[key]
        state = nav.navigate(decision_time=times[int(bar)], exec_tf="H1")
        constraints = state.constraints
        htf_bias = getattr(getattr(constraints, "direction_hint", None), "value", "UNKNOWN")
        h1_layer = (getattr(state, "layers", {}) or {}).get("H1")
        ltf_bias = getattr(getattr(h1_layer, "structure_bias", None), "value", "UNKNOWN")
        label = f"HTF_{_bucket(direction, htf_bias)}|LTF_{_bucket(direction, ltf_bias)}|LOC_{_location_label(state, direction)}"
        context_cache[key] = label
        return label

    result = protocol.run_depth_experiment(
        h1, depth_min=4, paired=True, tf_label="H1",
        context_bucket_fn=context_label, include_records=True,
    )
    records = result["treatment_records"]
    groups: dict[str, list[dict]] = {}
    for row in records:
        groups.setdefault(str(row.get("context_bucket", "UNKNOWN")), []).append(row)

    def subset(prefix: str, value: str | None = None) -> list[dict]:
        if value is None:
            return [r for r in records if str(r.get("context_bucket", "")).startswith(prefix)]
        return [r for r in records if str(r.get("context_bucket", "")) == f"{prefix}{value}"]

    all_rows = records
    htf_aligned = subset("HTF_", "ALIGNED|LTF_ALIGNED|LOC_FAVORABLE")  # replaced below; explicit filter avoids prefix ambiguity
    htf_aligned = [r for r in records if "HTF_ALIGNED" in str(r.get("context_bucket", ""))]
    htf_against = [r for r in records if "HTF_AGAINST" in str(r.get("context_bucket", ""))]
    htf_favorable = [r for r in records if "LOC_FAVORABLE" in str(r.get("context_bucket", ""))]
    htf_other = [r for r in records if "LOC_OTHER" in str(r.get("context_bucket", ""))]
    ltf_aligned = [r for r in records if "LTF_ALIGNED" in str(r.get("context_bucket", ""))]

    comparisons = {
        "B1_HTF_ALIGNED_MINUS_AGAINST": _delta_wr_ci(htf_aligned, htf_against, seed=424242),
        "B2_HTF_ALIGNED_MINUS_ALL": _delta_wr_ci(htf_aligned, all_rows, seed=424243),
        "B4_LOCATION_FAVORABLE_MINUS_OTHER": _delta_wr_ci(htf_favorable, htf_other, seed=424244),
        "B5_HTF_ALIGNED_MINUS_LTF_ALIGNED": _delta_wr_ci(htf_aligned, ltf_aligned, seed=424245),
    }
    gates = {}
    for name, comp in comparisons.items():
        ci = comp.get("ci95") or []
        gates[name] = {
            "n_ge_30_both": comp.get("n_left", 0) >= 30 and comp.get("n_right", 0) >= 30,
            "ci_lower_gt_0": bool(ci and ci[0] > 0),
            "pass": bool(comp.get("n_left", 0) >= 30 and comp.get("n_right", 0) >= 30 and ci and ci[0] > 0),
        }

    def metric(rows: list[dict]) -> dict:
        return protocol.compute_metrics(rows, "chain_id")

    dataset = {
        "symbol": "EURUSD", "exec_tf": "H1",
        "source": "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv",
        "range_start": "2019-01-01", "range_end": "2024-12-31",
        "bars": len(h1), "is_canonical": True,
    }
    head = git_head()
    now = datetime.now(timezone.utc).isoformat()
    overall = "PASS" if all(g["pass"] for g in gates.values()) else ("FAIL" if all(g["n_ge_30_both"] for g in gates.values()) else "BLOCKED")
    raw = {
        "schema_version": "1.0", "suite": "EXP_B_DIAGNOSTIC",
        "status": "EXECUTED_DIAGNOSTIC", "verdict": overall,
        "pre_registration": SPEC, "code_commit": head,
        "branch": git_branch(), "generated_at": now,
        "dataset": dataset,
        "protocol": {
            "source_runner": "scripts/lab/experiments/exp_agentA_runner.py",
            "depth_min": 4, "structure_mode": "lite", "outcome": "real R via sequential_outcome",
            "bootstrap": {"resamples": 2000, "seed": 42},
            "navigator_pit_status": "DIAGNOSTIC_ONLY; current branch G0 proves sequence scope, not navigator FULL-vs-PREFIX",
        },
        "counts": {"treatment_records": len(records), "context_groups": {k: len(v) for k, v in sorted(groups.items())}},
        "aggregate_metrics": {"ALL": metric(all_rows), "HTF_ALIGNED": metric(htf_aligned), "HTF_AGAINST": metric(htf_against), "LOCATION_FAVORABLE": metric(htf_favorable), "LOCATION_OTHER": metric(htf_other), "LTF_ALIGNED": metric(ltf_aligned)},
        "comparisons": comparisons, "gates": gates,
        "promotion": "BLOCKED",
        "limitations": ["Current branch is not engine-seq-v2-causal; this run is diagnostic only.", "B2 compares a subset with the unconditional cohort; it is not a causal intervention.", "B5 compares selected cohorts, not counterfactual outcomes.", "No B result authorizes a signal or replaces GEN-000."],
        "elapsed_s": round(time.time() - t0, 2),
        "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
    }
    audit = {
        "schema_version": "1.0", "experiment": "EXP_B_SUITE",
        "component_isolated": "HTF/context incremental diagnostic B1/B2/B4/B5",
        "code_commit": head, "branch": git_branch(), "generated_at": now,
        "pre_registration": SPEC, "gate": gates, "verdict": overall,
        "protocol": {"data_integrity": dataset, "parameter_change": False, "leakage_check": "DIAGNOSTIC_ONLY; navigator PIT debt remains open"},
        "rationale": "Resultados de diagnóstico; promoción bloqueada hasta ejecutar en worktree PIT-stable y revisar comparaciones.",
        "promotion": "BLOCKED", "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "EXP_B_DIAGNOSTIC_raw.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (OUT / "EXP_B_DIAGNOSTIC_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    diagnostic_specs = {
        "B1": ("B1_HTF_ALIGNED_MINUS_AGAINST", "HTF_ALIGNED", htf_aligned, "HTF_AGAINST", htf_against),
        "B2": ("B2_HTF_ALIGNED_MINUS_ALL", "HTF_ALIGNED", htf_aligned, "ALL", all_rows),
        "B4": ("B4_LOCATION_FAVORABLE_MINUS_OTHER", "LOCATION_FAVORABLE", htf_favorable, "LOCATION_OTHER", htf_other),
        "B5": ("B5_HTF_ALIGNED_MINUS_LTF_ALIGNED", "HTF_ALIGNED", htf_aligned, "LTF_ALIGNED", ltf_aligned),
    }
    for exp_id, (comparison_key, left_name, left_rows, right_name, right_rows) in diagnostic_specs.items():
        gate = gates[comparison_key]
        verdict = "PASS" if gate["pass"] else ("FAIL" if gate["n_ge_30_both"] else "BLOCKED")
        diagnostic = {
            "schema_version": "1.0",
            "experiment": f"EXP_{exp_id}_DIAGNOSTIC",
            "status": "EXECUTED_DIAGNOSTIC",
            "verdict": verdict,
            "pre_registration": SPEC,
            "code_commit": head,
            "branch": git_branch(),
            "generated_at": now,
            "dataset": dataset,
            "comparison": {"key": comparison_key, "left": left_name, "right": right_name, **comparisons[comparison_key]},
            "left_metrics": metric(left_rows),
            "right_metrics": metric(right_rows),
            "gate": gate,
            "promotion": "BLOCKED",
            "rationale": "Diagnostic only; navigator FULL-vs-PREFIX debt remains open and no result may replace GEN-000.",
            "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
        }
        (OUT / f"EXP_{exp_id}_diagnostic.json").write_text(json.dumps(diagnostic, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({"suite": "EXP_B_DIAGNOSTIC", "verdict": overall, "counts": raw["counts"], "comparisons": comparisons, "elapsed_s": raw["elapsed_s"]}, indent=2, ensure_ascii=False))
    return 0


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_branch() -> str:
    return subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute-diagnostic", action="store_true", help="run B1/B2/B4/B5 as non-promotable diagnostics")
    ap.add_argument("--allow-current-engine", action="store_true", help="explicitly allow a diagnostic run outside engine-seq-v2-causal")
    args = ap.parse_args()
    branch = git_branch()
    head = git_head()
    if args.execute_diagnostic:
        if branch != EXPECTED_BRANCH and not args.allow_current_engine:
            raise SystemExit(f"refusing diagnostic execution on {branch!r}; pass --allow-current-engine explicitly")
        return _run_diagnostic()
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
