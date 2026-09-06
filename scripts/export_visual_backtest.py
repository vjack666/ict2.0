"""Export the canonical ICT engine replay for ICT Structure Lab.

This is a new entrypoint.  It does not import or execute any historical
backtest package; it loads raw repository data, calls ``backtest.run_visual_replay``
and writes ``visual_backtest.json``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.replay import DEFAULT_TFS, ReplayConfig, load_raw_frames, run_visual_replay
from backtest.schema import write_visual_backtest
from engine.sequential_outcome import OutcomeConfig


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--tfs", nargs="+", default=list(DEFAULT_TFS))
    parser.add_argument(
        "--htf-timeframe",
        default="H4",
        help="Closed-bar higher-timeframe context for the sequence (default: H4).",
    )
    parser.add_argument(
        "--execution-timeframe",
        default="M5",
        help="Execution timeframe recorded for the replay (default: M5).",
    )
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--output", type=Path, default=ROOT / "backtest" / "visual_backtest.json")
    parser.add_argument("--horizon-bars", type=int, default=200)
    parser.add_argument(
        "--multitf-context",
        action="store_true",
        help="Use the full closed-only D1..M1 context stack; slower than the canonical single-HTF batch path.",
    )
    return parser


def _required_timeframes(args: argparse.Namespace) -> tuple[str, ...]:
    """Keep the causal context explicit even when a caller narrows ``--tfs``.

    A M15 replay with only M15/M5/M1 previously fell back to M15 as its own
    HTF. That makes the directional bias flip bar by bar and can discard a
    valid sweep before its following displacement is evaluated.
    """
    context_stack = ("D1", "H4", "H1") if args.multitf_context else ()
    return tuple(dict.fromkeys(
        [*args.tfs, *context_stack, args.timeframe, args.htf_timeframe, args.execution_timeframe]
    ))


def main() -> int:
    args = _parser().parse_args()
    timeframes = _required_timeframes(args)
    raw_frames = load_raw_frames(
        args.symbol,
        timeframes,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
    )
    config = ReplayConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        timeframes=timeframes,
        execution_tf=args.execution_timeframe,
        htf_timeframe=args.htf_timeframe,
        use_multitf_context=args.multitf_context,
        outcome=OutcomeConfig(horizon_bars=args.horizon_bars),
    )
    artifact = run_visual_replay(raw_frames, config)
    write_visual_backtest(artifact.to_dict(), args.output)
    print(
        f"visual backtest exported: {args.output} "
        f"candles={len(artifact.candles)} events={len(artifact.events)} trades={len(artifact.trades)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
