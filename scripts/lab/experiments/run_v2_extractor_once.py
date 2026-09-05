"""Run one canonical V2 extraction with a lightweight live black-box log.

This is a single bounded invocation: no retries, no backtest, no training, and
no order path. The child process is the canonical extractor; this wrapper only
records phase, elapsed time, exit code, and final manifest metadata.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def event(log: Path, phase: str, **extra) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "can_trade": False,
        "backtest": False,
        **extra,
    }
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-02T00:00:00Z")
    parser.add_argument("--end", default="2022-03-31T23:59:59Z")
    parser.add_argument("--output", type=Path, default=Path("data/materialized/v2/v2_engine_2022_q1.jsonl"))
    parser.add_argument("--log", type=Path, default=Path(".hermes-worklog/live/v2_extractor_run.jsonl"))
    parser.add_argument("--heartbeat-sec", type=float, default=30.0)
    args = parser.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(Path(__file__).with_name("v2_extractor_engine.py")), "--start", args.start, "--end", args.end, "--output", str(args.output)]
    started = time.monotonic()
    event(args.log, "STARTED", start=args.start, end=args.end, output=str(args.output), command=cmd)
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while child.poll() is None:
        time.sleep(args.heartbeat_sec)
        event(args.log, "RUNNING", elapsed_sec=round(time.monotonic() - started, 1), pid=child.pid, activity="canonical engine snapshot extraction")
    output = child.stdout.read() if child.stdout else ""
    if output:
        args.log.with_suffix(".stdout.log").write_text(output, encoding="utf-8")
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    event(args.log, "FINISHED" if child.returncode == 0 else "FAILED", elapsed_sec=round(time.monotonic() - started, 1), returncode=child.returncode, rows=manifest.get("rows", 0), training_eligible=manifest.get("training_eligible", False), manifest=str(manifest_path))
    return child.returncode


if __name__ == "__main__":
    raise SystemExit(main())
