"""CLI for Mission 1 six-TF funnel/backtest/AI shadow artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mission1_six_tf_pipeline import Mission1Config, run_mission1_pipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="reports/audits/experiments/mission1",
        help="Directory where Mission 1 artifacts will be written.",
    )
    parser.add_argument("--rows", type=int, default=60)
    args = parser.parse_args()
    summary = run_mission1_pipeline(
        Path(args.output_dir),
        Mission1Config(rows=args.rows),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
