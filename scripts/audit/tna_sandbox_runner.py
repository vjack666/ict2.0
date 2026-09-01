"""TNA Sandbox — multi-ventana mínima para entornos con CPU limitada.

- 3 ventanas cortas (~40-80 decision steps c/u, STEP=4)
- CSV Dukascopy 20Y
- precompute_sequences=False (velocidad)
- Valida fix rollback_depth (state→TF)
- Emite JSON + MD + bitácora

Policy: AHF_STATE_NOT_ENTRY. No PnL.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.ahf import AdaptiveHierarchicalFunnel, AHFConfig, AHFState
from engine.mtf_navigation import NavigatorConfig
from audits.codigo.ahf_temporal_navigation_audit import audit_snapshots, TemporalAuditConfig

DATASET = ROOT / "datasets" / "eurusd_dukascopy_20y"
OUT_JSON = ROOT / "reports" / "audits" / "ahf_temporal_navigation_SANDBOX.json"
OUT_MD = ROOT / "reports" / "audits" / "ahf_temporal_navigation_SANDBOX.md"

WINDOWS = [
    ("2017-smoke", "2017-03-20", "2017-03-31"),
    ("2020-covid", "2020-03-15", "2020-03-28"),
    ("2024-recent", "2024-06-15", "2024-06-28"),
]
STEP = 4


def load_tf(tf: str) -> pd.DataFrame:
    df = pd.read_csv(DATASET / f"EURUSD_{tf}.csv", parse_dates=["time"])
    return df.sort_values("time").reset_index(drop=True)


def reset_ahf(ahf: AdaptiveHierarchicalFunnel) -> None:
    ahf._state = AHFState.WAIT_D1
    ahf._history.clear()
    ahf._confirmed.clear()
    ahf._lock_bias.clear()


def main() -> dict:
    print("TNA SANDBOX — loading CSV...", flush=True)
    frames = {tf: load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    print(f"H1 n={len(h1)}", flush=True)

    ahf = AdaptiveHierarchicalFunnel(
        frames,
        AHFConfig(navigator=NavigatorConfig(precompute_sequences=False, sequence_tf="H1")),
    )
    print("AHF ready", flush=True)

    windows_out = []
    for name, t0, t1 in WINDOWS:
        times = list(h1.loc[(h1["time"] >= t0) & (h1["time"] <= t1), "time"])[::STEP]
        print(f"\n{name}: bars={len(times)} [{t0}→{t1}]", flush=True)
        if len(times) < 20:
            windows_out.append({"window": name, "status": "SKIP", "bars": len(times)})
            continue
        reset_ahf(ahf)
        t_run = time.time()
        snaps = ahf.run_timeline(times, exec_tf="H1")
        result = audit_snapshots(
            [s.to_dict() for s in snaps],
            decision_bars=list(range(len(snaps))),
            config=TemporalAuditConfig(),
        )
        elapsed = round(time.time() - t_run, 2)
        rb = result.get("rollback_depth_bars") or {}
        row = {
            "window": name,
            "range": [t0, t1],
            "bars": len(times),
            "step": STEP,
            "elapsed_s": elapsed,
            "status": result.get("status"),
            "trace_count": result.get("trace_count"),
            "transition_count": result.get("transition_count"),
            "invalidations": result.get("invalidations"),
            "downward_switches": result.get("downward_switches"),
            "upward_switches": result.get("upward_switches"),
            "final_state": result.get("final_state"),
            "rollback_depth_bars": rb,
            "stuck_state_count": result.get("stuck_state_count"),
        }
        windows_out.append(row)
        print(
            f"  {row['status']} inv={row['invalidations']} "
            f"rb_max={rb.get('max')} down/up={row['downward_switches']}/{row['upward_switches']} "
            f"{elapsed}s",
            flush=True,
        )

    ok = [w for w in windows_out if w.get("status") == "PASS_TRACE_INTEGRITY"]
    rb_maxes = [
        float((w.get("rollback_depth_bars") or {}).get("max") or 0) for w in ok
    ]
    inv_total = sum(w.get("invalidations") or 0 for w in ok)
    rollback_fixed = any(m > 0 for m in rb_maxes)

    agg = {
        "windows_pass_trace": len(ok),
        "windows_total": len(windows_out),
        "total_bars": sum(w.get("bars", 0) for w in windows_out),
        "total_invalidations": inv_total,
        "rollback_depth_max_observed": max(rb_maxes) if rb_maxes else 0,
        "rollback_fix_validated": rollback_fixed,
        "gates": {
            "TNA-TRACE-INTEGRITY": "PASS" if len(ok) == len(windows_out) else "PARTIAL",
            "ROLLBACK_DEPTH_INSTRUMENTATION": "PASS" if rollback_fixed else "FAIL",
        },
        "overall": "PASS" if (len(ok) == len(windows_out) and rollback_fixed) else "PARTIAL",
    }

    report = {
        "audit": "AHF_TEMPORAL_NAVIGATION_SANDBOX",
        "coverage": "STRATIFIED_MULTI_WINDOW_MINI",
        "dataset": "datasets/eurusd_dukascopy_20y",
        "policy": "AHF_STATE_NOT_ENTRY",
        "precompute_sequences": False,
        "step": STEP,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/tna_sandbox_runner.py",
        "note": (
            "Corrida sandbox: ventanas cortas + STEP=4 + precompute=False. "
            "Valida instrumentación de rollback_depth (fix state→TF). "
            "NO declara PASS full-span 20Y."
        ),
        "aggregate": agg,
        "windows": windows_out,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))

    md = [
        "# TNA SANDBOX — Multi-ventana mínima",
        "",
        f"- Cobertura: `{report['coverage']}`",
        f"- Overall: **{agg['overall']}**",
        f"- Rollback fix validado: **{rollback_fixed}** (max depth observado = {agg['rollback_depth_max_observed']})",
        f"- Barras totales: {agg['total_bars']}",
        f"- Invalidaciones: {agg['total_invalidations']}",
        "",
        "| Ventana | Barras | Status | Inv | RB max | Down/Up |",
        "|---------|-------:|--------|----:|-------:|---------|",
    ]
    for w in windows_out:
        rb = (w.get("rollback_depth_bars") or {}).get("max")
        md.append(
            f"| {w.get('window')} | {w.get('bars')} | {w.get('status')} | "
            f"{w.get('invalidations')} | {rb} | {w.get('downward_switches')}/{w.get('upward_switches')} |"
        )
    md += ["", report["note"], ""]
    OUT_MD.write_text("\n".join(md))

    print("\n=== AGGREGATE ===", flush=True)
    print(json.dumps(agg, indent=2), flush=True)
    print(f"JSON → {OUT_JSON}", flush=True)
    return report


if __name__ == "__main__":
    main()
