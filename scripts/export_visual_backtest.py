"""Export a deterministic causal ICT + Wyckoff visual replay v1.1."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.replay import DEFAULT_TFS, ReplayConfig, load_raw_frames, run_visual_replay
from backtest.schema import json_safe, write_visual_backtest
from engine.sequential_outcome import OutcomeConfig


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--tfs", nargs="+", default=list(DEFAULT_TFS))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--start", required=True, help="UTC visible-window start")
    parser.add_argument("--end", required=True, help="UTC exclusive end; a date includes that full date")
    parser.add_argument("--warmup-bars", type=int, default=200)
    parser.add_argument("--timestamp-semantics", choices=("open", "close"), required=True)
    parser.add_argument("--wyckoff", action="store_true", help="Call the real engine.Wyckoff adapter per candle")
    parser.add_argument("--wyckoff-authority-tf", default="H1")
    parser.add_argument("--wyckoff-layers", nargs="+", default=["D1", "H4", "H1", "M15"])
    parser.add_argument("--multitf-context", action="store_true")
    parser.add_argument("--horizon-bars", type=int, default=200)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "backtest" / "runs")
    parser.add_argument("--output", type=Path)
    return parser


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _git_branch() -> str:
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return branch or "DETACHED"
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _git_worktree_clean() -> bool:
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return not status.strip()
    except (OSError, subprocess.CalledProcessError):
        return False


def _node_version() -> str:
    try:
        return subprocess.check_output(
            ["node", "--version"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "NOT_APPLICABLE"


def _normalized_command(args: argparse.Namespace, timeframes: tuple[str, ...]) -> str:
    parts = [
        "python", "scripts/export_visual_backtest.py",
        "--symbol", args.symbol,
        "--timeframe", args.timeframe.upper(),
        "--tfs", *timeframes,
        "--data-dir", "<DATA_DIR>",
        "--start", args.start,
        "--end", args.end,
        "--warmup-bars", str(args.warmup_bars),
        "--timestamp-semantics", args.timestamp_semantics,
        "--wyckoff-authority-tf", args.wyckoff_authority_tf.upper(),
        "--wyckoff-layers", *(tf.upper() for tf in args.wyckoff_layers),
        "--horizon-bars", str(args.horizon_bars),
    ]
    if args.wyckoff:
        parts.append("--wyckoff")
    if args.multitf_context:
        parts.append("--multitf-context")
    return shlex.join(parts)


def _write_json_atomic(payload: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    git_commit = _git_commit()
    git_branch = _git_branch()
    worktree_clean_before_run = _git_worktree_clean()
    python_version = platform.python_version()
    node_version = _node_version()
    requested = [*(tf.upper() for tf in args.tfs), args.timeframe.upper()]
    if args.wyckoff:
        requested.extend(tf.upper() for tf in args.wyckoff_layers)
        requested.append(args.wyckoff_authority_tf.upper())
    timeframes = tuple(dict.fromkeys(requested))
    missing_layers = sorted(
        set(tf.upper() for tf in args.wyckoff_layers) - set(timeframes)
    ) if args.wyckoff else []
    if missing_layers:
        raise SystemExit(f"missing required Wyckoff layers: {missing_layers}")

    raw_frames = load_raw_frames(
        args.symbol,
        timeframes,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
        warmup_bars=args.warmup_bars,
        timestamp_semantics=args.timestamp_semantics,
    )
    config = ReplayConfig(
        symbol=args.symbol,
        timeframe=args.timeframe.upper(),
        timeframes=timeframes,
        authority_tf=args.wyckoff_authority_tf.upper(),
        wyckoff_layers=tuple(tf.upper() for tf in args.wyckoff_layers),
        timestamp_semantics=args.timestamp_semantics,
        warmup_bars=args.warmup_bars,
        visible_start=args.start,
        visible_end=args.end,
        wyckoff_enabled=args.wyckoff,
        use_multitf_context=args.multitf_context,
        git_commit=git_commit,
        git_branch=git_branch,
        generator_worktree_clean_before_run=worktree_clean_before_run,
        python_version=python_version,
        node_version=node_version,
        outcome=OutcomeConfig(horizon_bars=args.horizon_bars),
    )
    artifact = run_visual_replay(raw_frames, config)
    artifact.run_metadata["command"] = _normalized_command(args, timeframes)
    payload = artifact.to_dict()
    run_id = payload["run_metadata"]["run_id"]
    run_path = args.run_dir.resolve() / run_id
    output = args.output.resolve() if args.output else run_path / "visual_backtest.json"
    manifest_path = run_path / "manifest.json"
    write_visual_backtest(payload, output)
    _write_json_atomic(
        {
            "schema_version": payload["schema_version"],
            "run_id": run_id,
            "artifact": output.name if output.parent == run_path else output.as_posix(),
            "visible_window": payload["visible_window"],
            "policy": payload["policy"],
            "data_manifest": payload["data_manifest"],
            "run_metadata": payload["run_metadata"],
            "scientific_status": payload["scientific_status"],
        },
        manifest_path,
    )

    print(f"run_id={run_id}")
    print(f"artifact={output}")
    print(f"manifest={manifest_path}")
    print(
        f"window={payload['visible_window']['start']}..{payload['visible_window']['end']} "
        f"visible_candles={len(payload['candles'])}"
    )
    for tf, item in payload["data_manifest"]["timeframes"].items():
        print(
            f"tf={tf} visible={item['visible_rows']} warmup={item['warmup_rows']} "
            f"volume={item['volume_source']} slice_sha256={item['slice_sha256']}"
        )
    print(
        f"structure_events={len(payload['structure_events'])} "
        f"wyckoff_events={len(payload['wyckoff_events'])} trades={len(payload['trades'])}"
    )
    print(f"artifact_content_sha256={payload['run_metadata']['artifact_content_sha256']}")
    print("security=diagnostic_only:true entry_authorized:false can_trade:false can_train:false promotion_authorized:false")
    if any(
        item["volume_source"] == "TICK_VOLUME_PROXY"
        for item in payload["data_manifest"]["timeframes"].values()
    ):
        print("warning=volume is MT5 tick-volume proxy, not exchange volume")
    if not args.wyckoff:
        print("warning=Wyckoff timeline disabled; rerun with --wyckoff for real snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
