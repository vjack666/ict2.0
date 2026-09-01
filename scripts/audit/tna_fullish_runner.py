"""TNA Full-ish — cobertura estratificada amplia (STRATIFIED_WIDE).

Muestrea decision times a lo largo de todo el H1 2006–2025 con stride fijo
para obtener ~2.5k–4k steps (según STRIDE).

NO es full-span (124k barras). NO declara PASS full-span del plan normativo.

Uso:
  python scripts/tna_fullish_runner.py

Policy: AHF_STATE_NOT_ENTRY / TEMPORAL_AUDIT_NOT_PNL
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
OUT_DIR = ROOT / "reports" / "audits"
OUT_JSON = OUT_DIR / "ahf_temporal_navigation_FULLISH.json"
OUT_MD = OUT_DIR / "ahf_temporal_navigation_FULLISH.md"
CHECKPOINT = OUT_DIR / "ahf_temporal_navigation_FULLISH.checkpoint.json"
LOG = OUT_DIR / "ahf_temporal_navigation_FULLISH.run.log"

# Ajustar según máquina: STRIDE=30 → ~4.1k steps; 40 → ~3.1k; 50 → ~2.5k
STRIDE = 40
CHUNK_SIZE = 350


def log(msg: str) -> None:
    print(msg, flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def load_tf(tf: str) -> pd.DataFrame:
    p = DATASET / f"EURUSD_{tf}.csv"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}")
    df = pd.read_csv(p, parse_dates=["time"])
    return df.sort_values("time").reset_index(drop=True)


def reset_ahf(ahf: AdaptiveHierarchicalFunnel) -> None:
    ahf._state = AHFState.WAIT_D1
    ahf._history.clear()
    ahf._confirmed.clear()
    ahf._lock_bias.clear()


def main() -> dict:
    if LOG.exists():
        LOG.unlink()
    log("=== TNA FULL-ISH (STRATIFIED_WIDE) ===")
    log(f"STRIDE={STRIDE} CHUNK_SIZE={CHUNK_SIZE}")

    frames = {tf: load_tf(tf) for tf in ("D1", "H4", "H1")}
    h1 = frames["H1"]
    all_times = list(h1["time"].iloc[::STRIDE])
    log(f"H1 total={len(h1)} sampled_steps={len(all_times)}")

    ahf = AdaptiveHierarchicalFunnel(
        frames,
        AHFConfig(navigator=NavigatorConfig(precompute_sequences=False, sequence_tf="H1")),
    )

    chunk_reports: list[dict] = []
    t_global = time.time()
    n_chunks = (len(all_times) + CHUNK_SIZE - 1) // CHUNK_SIZE

    for ci in range(n_chunks):
        chunk = all_times[ci * CHUNK_SIZE : (ci + 1) * CHUNK_SIZE]
        if len(chunk) < 15:
            continue
        log(f"--- chunk {ci+1}/{n_chunks} steps={len(chunk)} [{chunk[0]} → {chunk[-1]}] ---")
        reset_ahf(ahf)
        t0 = time.time()
        snaps = ahf.run_timeline(chunk, exec_tf="H1")
        result = audit_snapshots(
            [s.to_dict() for s in snaps],
            decision_bars=list(range(len(snaps))),
            config=TemporalAuditConfig(),
        )
        elapsed = round(time.time() - t0, 1)
        rb = result.get("rollback_depth_bars") or {}
        row = {
            "chunk": ci + 1,
            "steps": len(chunk),
            "t_start": str(chunk[0]),
            "t_end": str(chunk[-1]),
            "elapsed_s": elapsed,
            "status": result.get("status"),
            "trace_count": result.get("trace_count"),
            "transition_count": result.get("transition_count"),
            "invalidations": result.get("invalidations"),
            "downward_switches": result.get("downward_switches"),
            "upward_switches": result.get("upward_switches"),
            "final_state": result.get("final_state"),
            "stuck_state_count": result.get("stuck_state_count"),
            "rollback_depth_bars": {
                "n": rb.get("n"),
                "median": rb.get("median"),
                "max": rb.get("max"),
                "mean": rb.get("mean"),
            },
            "state_durations_summary": {
                k: {"n": v.get("n"), "median": v.get("median"), "max": v.get("max")}
                for k, v in (result.get("state_durations_bars") or {}).items()
            },
        }
        chunk_reports.append(row)
        log(
            f"  {row['status']} inv={row['invalidations']} rb_max={rb.get('max')} "
            f"down/up={row['downward_switches']}/{row['upward_switches']} {elapsed}s"
        )
        CHECKPOINT.write_text(json.dumps({"chunks_done": chunk_reports}, indent=2, default=str))

    total_elapsed = round(time.time() - t_global, 1)
    ok = [c for c in chunk_reports if c.get("status") == "PASS_TRACE_INTEGRITY"]
    total_steps = sum(c.get("steps", 0) for c in chunk_reports)
    total_inv = sum(c.get("invalidations") or 0 for c in ok)
    total_trans = sum(c.get("transition_count") or 0 for c in ok)
    rb_maxes = [float((c.get("rollback_depth_bars") or {}).get("max") or 0) for c in ok]
    down = sum(c.get("downward_switches") or 0 for c in ok)
    up = sum(c.get("upward_switches") or 0 for c in ok)
    setup_chunks = sum(
        1
        for c in ok
        if (c.get("state_durations_summary") or {}).get("SETUP_READY", {}).get("n", 0)
    )

    agg = {
        "chunks_pass_trace": len(ok),
        "chunks_total": len(chunk_reports),
        "total_steps": total_steps,
        "total_transitions": total_trans,
        "total_invalidations": total_inv,
        "downward_switches": down,
        "upward_switches": up,
        "rollback_depth_max_observed": max(rb_maxes) if rb_maxes else 0,
        "rollback_fix_validated": any(m > 0 for m in rb_maxes),
        "chunks_with_SETUP_READY": setup_chunks,
        "elapsed_s": total_elapsed,
        "stride": STRIDE,
        "coverage_pct_approx": round(100.0 * total_steps / max(len(h1), 1), 2),
        "gates": {
            "TNA-TRACE-INTEGRITY": "PASS" if ok and len(ok) == len(chunk_reports) else "FAIL",
            "ROLLBACK_DEPTH_INSTRUMENTATION": "PASS" if any(m > 0 for m in rb_maxes) else "FAIL",
        },
        "overall": (
            "PASS"
            if (ok and len(ok) == len(chunk_reports) and any(m > 0 for m in rb_maxes))
            else "PARTIAL"
        ),
    }

    report = {
        "audit": "AHF_TEMPORAL_NAVIGATION_FULLISH",
        "coverage": "STRATIFIED_WIDE",
        "dataset": "datasets/eurusd_dukascopy_20y",
        "policy": "AHF_STATE_NOT_ENTRY",
        "precompute_sequences": False,
        "stride": STRIDE,
        "chunk_size": CHUNK_SIZE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "scripts/tna_fullish_runner.py",
        "note": (
            f"STRATIFIED_WIDE: cada {STRIDE} barras H1 (~{total_steps} steps, "
            f"~{agg['coverage_pct_approx']}% timeline). NO es full-span 124k. "
            "NO declara PASS full-span del plan normativo."
        ),
        "aggregate": agg,
        "chunks": chunk_reports,
    }

    OUT_JSON.write_text(json.dumps(report, indent=2, default=str))

    lines = [
        "# TNA FULL-ISH — STRATIFIED_WIDE",
        "",
        f"- **Cobertura:** `{report['coverage']}` — **NO es full-span**",
        f"- **Overall:** **{agg['overall']}**",
        f"- **Steps:** {agg['total_steps']} (stride={STRIDE}, ~{agg['coverage_pct_approx']}%)",
        f"- **Invalidaciones:** {agg['total_invalidations']}",
        f"- **Rollback depth max:** {agg['rollback_depth_max_observed']}",
        f"- **Switches down/up:** {down}/{up}",
        f"- **Chunks con SETUP_READY:** {setup_chunks}",
        f"- **Tiempo:** {total_elapsed}s",
        "",
        "## Gates",
        "",
        "| Gate | Estado |",
        "|------|--------|",
        f"| TNA-TRACE-INTEGRITY | **{agg['gates']['TNA-TRACE-INTEGRITY']}** |",
        f"| ROLLBACK_DEPTH_INSTRUMENTATION | **{agg['gates']['ROLLBACK_DEPTH_INSTRUMENTATION']}** |",
        f"| **OVERALL (full-ish)** | **{agg['overall']}** |",
        "",
        "## Por chunk",
        "",
        "| # | Steps | Status | Inv | RB max | Down/Up | s |",
        "|--:|------:|--------|----:|-------:|---------|--:|",
    ]
    for c in chunk_reports:
        rb = (c.get("rollback_depth_bars") or {}).get("max")
        lines.append(
            f"| {c.get('chunk')} | {c.get('steps')} | {c.get('status')} | "
            f"{c.get('invalidations')} | {rb} | "
            f"{c.get('downward_switches')}/{c.get('upward_switches')} | {c.get('elapsed_s')} |"
        )
    lines += ["", "## Nota", "", report["note"], ""]
    OUT_MD.write_text("\n".join(lines))

    log(json.dumps(agg, indent=2))
    log(f"JSON → {OUT_JSON}")
    return report


if __name__ == "__main__":
    main()
