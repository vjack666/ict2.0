"""Run the local, non-promotional economic proxy pilot.

The script composes the canonical causal replay with the independent economic
accounting layer. It is intentionally not a promotion or trading entrypoint.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.economics import EconomicScenario, account_trade_economics
from backtest.replay import ReplayConfig, load_raw_frames, run_visual_replay
from engine.sequential_outcome import OutcomeConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2022-12-31 23:59:59")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    timeframes = ("D1", "H4", "H1", "M15", "M5")
    frames = load_raw_frames(
        "EURUSD", timeframes, data_dir=Path("data/raw"),
        start=args.start, end=args.end,
    )
    config = ReplayConfig(
        timeframe="M15", timeframes=timeframes, execution_tf="M5",
        htf_timeframe="H4",
        outcome=OutcomeConfig(horizon_bars=12, sl_buffer=0.0001,
                              tie_policy="pessimistic"),
    )
    technical = run_visual_replay(frames, config)
    scenario = EconomicScenario(
        spread_pips=1.0, slippage_pips=0.3,
        commission_per_lot_side=5.0,
    )
    economic_trades = [account_trade_economics(t, scenario) for t in technical.trades]
    resolved = [t for t in economic_trades if t["net_R"] is not None]
    summary = {
        "artifact_kind": "PASS_EDGE_PROXY_PILOT",
        "status": "REVIEW",
        "policy": {"local_only": True, "can_trade": False, "can_train": False,
                   "promotion_authorized": False},
        "period": {"start": args.start, "end": args.end},
        "technical_counts": {"candles": len(technical.candles),
                             "events": len(technical.events),
                             "signals": len(technical.signals),
                             "trades": len(technical.trades)},
        "economic_counts": {"resolved": len(resolved),
                            "unresolved": len(economic_trades) - len(resolved)},
        "mean_net_R": (sum(t["net_R"] for t in resolved) / len(resolved)
                       if resolved else None),
        "scenario": economic_trades[0].get("economic_scenario", {
            "spread_pips": 1.0, "slippage_pips": 0.3,
            "commission_per_lot_side": 5.0, "lot_size": 1.0,
            "contract_size": 100000.0, "pip_size": 0.0001,
        }),
        "technical_geometry_note": (
            "The current canonical resolver uses its configured fixed price "
            "buffer; this pilot does not certify the preregistered 0.3 ATR "
            "stop geometry."
        ),
        "trades": economic_trades,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ("status", "period", "technical_counts", "economic_counts", "mean_net_R")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
