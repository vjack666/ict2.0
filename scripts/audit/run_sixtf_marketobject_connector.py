"""Run the six-TF MarketObject connector audit.

This is a local diagnostic/audit runner.  It does not modify raw data, train
models, connect MT5, issue orders, or claim edge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.data_feed import load_frames
from engine.sixtf_marketobject_connector import SIX_TFS, SixTFConnectorConfig, build_sixtf_episodes


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


def _sha(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _truncate_frames(frames: dict[str, pd.DataFrame], decision: pd.Timestamp) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for tf, frame in frames.items():
        times = pd.to_datetime(frame["time"], utc=True, errors="coerce")
        out[tf] = frame.loc[times <= decision].copy().reset_index(drop=True)
    return out


def _core_for_prefix(artifact: dict[str, Any]) -> dict[str, Any]:
    """Stable causal subset used for FULL/PREFIX equality."""
    return {
        "status": artifact.get("status"),
        "setup_count": artifact.get("setup_count", 0),
        "lineage_summary": artifact.get("lineage_summary", {}),
        "records": artifact.get("records", []),
        "episodes": artifact.get("episodes", []),
        "rejections": artifact.get("rejections", []),
    }


def _decision_times(
    frames: dict[str, pd.DataFrame],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    count: int,
    step_minutes: int,
) -> list[pd.Timestamp]:
    m1 = frames["M1"]
    times = pd.to_datetime(m1["time"], utc=True, errors="coerce")
    available = [pd.Timestamp(t) for t in times[(times >= start) & (times <= end)]]
    if not available:
        raise ValueError("EMPTY_DECISION_WINDOW")
    if step_minutes > 0:
        selected: list[pd.Timestamp] = []
        last: pd.Timestamp | None = None
        for ts in available:
            if last is None or ts >= last + pd.Timedelta(minutes=step_minutes):
                selected.append(ts)
                last = ts
            if len(selected) >= count:
                break
        return selected
    if count >= len(available):
        return available
    indexes = [round(i * (len(available) - 1) / max(1, count - 1)) for i in range(count)]
    return [available[i] for i in indexes]


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


def run_window(
    *,
    data_dir: Path,
    start_time: str,
    end_time: str,
    decisions: int,
    step_minutes: int,
    output: Path,
    fast_backtest_mode: bool = False,
) -> dict[str, Any]:
    start = pd.Timestamp(start_time, tz="UTC")
    end = pd.Timestamp(end_time, tz="UTC")
    warmup = (start - pd.Timedelta(days=90)).isoformat()
    frames = load_frames("EURUSD", SIX_TFS, data_dir=data_dir, start=warmup, end=end.isoformat())
    decision_times = _decision_times(
        frames,
        start=start,
        end=end,
        count=decisions,
        step_minutes=step_minutes,
    )
    rows: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    full_prefix_failures: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    connector_config = SixTFConnectorConfig(build_context_snapshot=not fast_backtest_mode)
    for decision in decision_times:
        try:
            full = build_sixtf_episodes(frames, decision, config=connector_config)
            prefix = build_sixtf_episodes(_truncate_frames(frames, decision), decision, config=connector_config)
            full_core = _core_for_prefix(full)
            prefix_core = _core_for_prefix(prefix)
            full_hash = _sha(full_core)
            prefix_hash = _sha(prefix_core)
            full_prefix_pass = full_hash == prefix_hash
            if not full_prefix_pass:
                full_prefix_failures.append(
                    {
                        "decision_time": decision.isoformat(),
                        "full_hash": full_hash,
                        "prefix_hash": prefix_hash,
                        "full_status": full.get("status"),
                        "prefix_status": prefix.get("status"),
                    }
                )
            rows.append(
                {
                    "decision_time": decision.isoformat(),
                    "status": full.get("status"),
                    "setup_count": full.get("setup_count", 0),
                    "episode_count": len(full.get("episodes", [])),
                    "rejection_count": len(full.get("rejections", [])),
                    "lineage_status": (full.get("lineage_summary") or {}).get("status"),
                    "six_tfs_complete": (full.get("lineage_summary") or {}).get("six_tfs_complete"),
                    "full_prefix_pass": full_prefix_pass,
                    "full_hash": full_hash,
                    "prefix_hash": prefix_hash,
                }
            )
            for episode in full.get("episodes", []):
                episodes.append(dict(episode))
            for rejection in full.get("rejections", []):
                rejections.append(dict(rejection))
        except Exception as exc:  # fail closed, keep the evidence
            errors.append(
                {
                    "decision_time": decision.isoformat(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    pass_count = sum(1 for row in rows if row["status"] == "PASS")
    no_episode_count = sum(1 for row in rows if row["status"] == "NO_EPISODES")
    status = "PASS" if rows and not errors and not full_prefix_failures and pass_count > 0 else "REVIEW"
    report = {
        "status": status,
        "source": str(data_dir),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "decision_count_requested": decisions,
        "decision_count": len(decision_times),
        "timeframes": list(SIX_TFS),
        "can_trade": False,
        "diagnostic_only": True,
        "edge_claimed": False,
        "fast_backtest_mode": fast_backtest_mode,
        "window_gates": {
            "all_runs_executed": len(errors) == 0,
            "full_prefix_all_pass": len(full_prefix_failures) == 0,
            "at_least_one_episode": len(episodes) > 0,
            "at_least_one_rejection": len(rejections) > 0,
            "all_lineage_valid": all(row.get("lineage_status") == "LINEAGE_VALID" for row in rows),
            "all_six_tfs_complete": all(row.get("six_tfs_complete") is True for row in rows),
        },
        "aggregates": {
            "pass_count": pass_count,
            "no_episode_count": no_episode_count,
            "error_count": len(errors),
            "episode_count": len(episodes),
            "rejection_count": len(rejections),
            "full_prefix_failure_count": len(full_prefix_failures),
            "window_checksum": _sha(rows),
        },
        "rows": rows,
        "episodes": episodes,
        "rejections": rejections,
        "full_prefix_failures": full_prefix_failures,
        "errors": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(_jsonable(report), indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode")
    single = sub.add_parser("single")
    single.add_argument("--data-dir", type=Path, default=Path("data/raw/EURUSD"))
    single.add_argument("--decision-time", required=True)
    single.add_argument("--output", type=Path, default=Path("reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json"))
    window = sub.add_parser("window")
    window.add_argument("--data-dir", type=Path, default=Path("data/raw/EURUSD"))
    window.add_argument("--start-time", required=True)
    window.add_argument("--end-time", required=True)
    window.add_argument("--decisions", type=int, default=24)
    window.add_argument("--step-minutes", type=int, default=60)
    window.add_argument("--fast-backtest-mode", action="store_true")
    window.add_argument("--output", type=Path, default=Path("reports/audits/experiments/mission3/sixtf_window_report.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/EURUSD"))
    parser.add_argument("--decision-time")
    parser.add_argument("--output", type=Path, default=Path("reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json"))
    args = parser.parse_args()
    if args.mode == "window":
        report = run_window(
            data_dir=args.data_dir,
            start_time=args.start_time,
            end_time=args.end_time,
            decisions=args.decisions,
            step_minutes=args.step_minutes,
            output=args.output,
            fast_backtest_mode=args.fast_backtest_mode,
        )
    else:
        if not args.decision_time:
            parser.error("--decision-time is required for single mode")
        report = run(data_dir=args.data_dir, decision_time=args.decision_time, output=args.output)
    print(json.dumps(_jsonable(report), indent=2, sort_keys=True))
    return 0 if report["status"] in {"PASS", "NO_EPISODES"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
