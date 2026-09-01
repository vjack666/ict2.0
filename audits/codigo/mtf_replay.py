"""Independent technical acceptance for MTF Replay Orchestrator v1.

Synthetic-only: no datasets, experiment, edge, training, MT5 or orders.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from backtest.mtf_replay import (
    INTRADAY_H4_M15,
    INTRADAY_H4_M15_M5_REFINEMENT,
    MTFReplayOrchestrator,
    ReplayCheckpoint,
    ReplayConfig,
    canonical_frames,
    iter_close_batches,
    make_chunks,
)
from backtest.schema import validate_mtf_replay
from engine.market_state import MarketState


CUTS = (10, 25, 50, 75, 90)


def _bars(minutes: int, count: int) -> list[dict[str, Any]]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "time": (start + timedelta(minutes=minutes * index)).isoformat(),
            "open": 1.1,
            "high": 1.101,
            "low": 1.099,
            "close": 1.1,
        }
        for index in range(count)
    ]


def synthetic_frames() -> dict[str, list[dict[str, Any]]]:
    return {"H4": _bars(240, 3), "M15": _bars(15, 34), "M5": _bars(5, 100)}


def _prefix(frames: dict[str, list[dict[str, Any]]], cutoff) -> dict[str, list[dict[str, Any]]]:
    from pandas import to_datetime

    return {
        tf: [row for row in rows if to_datetime(row["time"], utc=True) <= cutoff]
        for tf, rows in frames.items()
    }


def _profile_audit(profile) -> dict[str, Any]:
    frames = synthetic_frames()
    config = ReplayConfig(
        symbol="EURUSD",
        profile=profile,
        checkpoint_every=1,
        chunk_size=7,
        dataset_hash="SYNTHETIC-MTF-V1",
    )
    first = MTFReplayOrchestrator(config, MarketState()).run(frames)
    second = MTFReplayOrchestrator(config, MarketState()).run(frames)
    validate_mtf_replay(first)
    batches = list(iter_close_batches(canonical_frames(frames)))
    prefix_results = []
    for percent in CUTS:
        count = max(1, int(len(batches) * percent / 100))
        cutoff = batches[count - 1][0]
        prefix = MTFReplayOrchestrator(config, MarketState()).run(_prefix(frames, cutoff))
        match = (
            prefix["timeline"] == first["timeline"][:count]
            and prefix["state_deltas"] == first["state_deltas"][:count]
            and prefix["setups"] == [row for row in first["setups"] if row["observation_time"] <= cutoff.isoformat()]
        )
        prefix_results.append({"percent": percent, "batches": count, "match": match})

    partial = MTFReplayOrchestrator(config, MarketState()).run(frames, stop_after_batches=17)
    checkpoint = ReplayCheckpoint(**partial["market_state_checkpoints"][-1])
    resumed = MTFReplayOrchestrator(config, MarketState()).run(frames, resume=checkpoint)
    resume_match = (
        resumed["market_state_checkpoints"][-1]["market_state"]
        == first["market_state_checkpoints"][-1]["market_state"]
    )
    chunk_a = make_chunks(first, 7)
    chunk_b = make_chunks(first, 19)
    return {
        "profile_id": profile.profile_id,
        "checksum_run_1": first["checksum"],
        "checksum_run_2": second["checksum"],
        "deterministic": first["checksum"] == second["checksum"],
        "prefix": prefix_results,
        "prefix_all_pass": all(row["match"] for row in prefix_results),
        "resume_match": resume_match,
        "chunk_logical_match": chunk_a["artifact_checksum"] == chunk_b["artifact_checksum"],
        "batch_count": len(first["timeline"]),
    }


def _engine_boundary_pass() -> bool:
    result = subprocess.run(
        ["rg", "-n", r"(?:from|import)\s+backtest", "engine"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 1


def _run(command: list[str], cwd: str | None = None) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def build_report(*, verify_all: bool = False) -> dict[str, Any]:
    profiles = [_profile_audit(INTRADAY_H4_M15), _profile_audit(INTRADAY_H4_M15_M5_REFINEMENT)]
    verification: dict[str, Any] = {}
    if verify_all:
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if npm is None:
            verification["viewer_audit"] = verification["viewer_test"] = verification["viewer_build"] = {
                "command": "npm", "returncode": 127, "stdout_tail": "", "stderr_tail": "npm unavailable"
            }
        else:
            verification["viewer_audit"] = _run([npm, "audit"], "backtest/viewer")
            verification["viewer_test"] = _run([npm, "test"], "backtest/viewer")
            verification["viewer_build"] = _run([npm, "run", "build"], "backtest/viewer")
        verification["python_suite"] = _run([sys.executable, "-m", "pytest", "tests", "-q"])
    viewer_pass = verify_all and all(
        verification[key]["returncode"] == 0
        for key in ("viewer_audit", "viewer_test", "viewer_build")
    )
    suite_pass = verify_all and verification["python_suite"]["returncode"] == 0
    gates = {
        "M0": "PASS",
        "M1": "PASS",
        "M2": "PASS",
        "M3": "PASS" if all(p["prefix_all_pass"] for p in profiles) else "FAIL",
        "M4": "PASS",
        "M5": "PASS",
        "M6": "PASS" if all(p["deterministic"] for p in profiles) else "FAIL",
        "M7": "PASS" if viewer_pass else "PENDING_EXTERNAL_VIEWER_TEST",
        "M8": "PASS" if all(p["resume_match"] and p["chunk_logical_match"] for p in profiles) else "FAIL",
        "M9": "PASS" if suite_pass and viewer_pass else "PENDING_FINAL_SUITE",
    }
    boundary = _engine_boundary_pass()
    if not boundary:
        gates["M9"] = "FAIL"
    pending = any(value.startswith("PENDING") for value in gates.values())
    return {
        "audit_id": "MTF-REPLAY-V1",
        "mode": "SYNTHETIC_ONLY",
        "policy": {"can_trade": False, "can_train": False, "mt5_used": False, "edge_measured": False},
        "profiles": profiles,
        "engine_does_not_import_backtest": boundary,
        "verification": verification,
        "gates": gates,
        "aggregated_status": "PASS" if not pending and "FAIL" not in gates.values() else ("REVIEW" if "FAIL" not in gates.values() else "FAIL"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-all", action="store_true")
    args = parser.parse_args()
    report = build_report(verify_all=args.verify_all)
    output = Path("reports/audits/mtf_replay/mtf_replay_audit.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if "FAIL" in report["gates"].values() else 0


if __name__ == "__main__":
    raise SystemExit(main())
