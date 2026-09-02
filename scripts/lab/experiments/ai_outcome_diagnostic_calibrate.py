"""Write a deterministic first calibration report from a diagnostic artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from runtime.ai_learning.diagnostic_calibration import calibrate_diagnostic_artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--jsonl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    report = calibrate_diagnostic_artifact(source, jsonl_path=str(args.jsonl))
    body = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(body).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "fit_partition": report["fit_partition"], "can_trade": False}))


if __name__ == "__main__":
    main()
