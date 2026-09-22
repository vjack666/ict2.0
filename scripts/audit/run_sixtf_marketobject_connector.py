"""Run the six-TF MarketObject connector audit.

This is a local diagnostic/audit runner.  It does not modify raw data, train
models, connect MT5, issue orders, or claim edge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_feed import load_frames
from engine.sixtf_marketobject_connector import SIX_TFS, build_sixtf_episodes


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def run(*, data_dir: Path, decision_time: str, output: Path) -> dict[str, Any]:
    decision = pd.Timestamp(decision_time, tz="UTC")
    start = (decision - pd.Timedelta(days=90)).isoformat()
    end = decision.isoformat()
    frames = load_frames("EURUSD", SIX_TFS, data_dir=data_dir, start=start, end=end)
    artifact = build_sixtf_episodes(frames, decision)
    report = {
        "status": artifact["status"],
        "decision_time": decision.isoformat(),
        "source": str(data_dir),
        "timeframes": list(SIX_TFS),
        "can_trade": False,
        "diagnostic_only": True,
        "edge_claimed": False,
        "setup_count": artifact.get("setup_count", 0),
        "episode_count": len(artifact.get("episodes", [])),
        "rejection_count": len(artifact.get("rejections", [])),
        "lineage_summary": artifact.get("lineage_summary", {}),
        "records": artifact.get("records", []),
        "episodes": artifact.get("episodes", []),
        "rejections": artifact.get("rejections", []),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_jsonable(report), indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/EURUSD"))
    parser.add_argument("--decision-time", required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json"))
    args = parser.parse_args()
    report = run(data_dir=args.data_dir, decision_time=args.decision_time, output=args.output)
    print(json.dumps(_jsonable(report), indent=2, sort_keys=True))
    return 0 if report["status"] in {"PASS", "NO_EPISODES"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
