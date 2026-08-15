"""CLI Backtest v2.

Modes:
  sequence — SAME as production run_backtest (H4→M15 + R6 defaults) + live structure table
  legacy   — alias of sequence (compat)

Usage:
  python -m ict_backtest.v2.run_v2 --mode sequence --symbol XAUUSD --htf H4 --ltf M15
  python scripts/runner_monitor.py --window --title "bt-v2-seq-XAU" -- python -m ict_backtest.v2.run_v2 --mode sequence --symbol XAUUSD

Live table (while running):
  results/bt_v2/<symbol>/sequence/live_structure.csv
  Get-Content results\\bt_v2\\XAUUSD\\sequence\\live_structure.csv -Wait -Tail 30
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.v2.orchestrator import (  # noqa: E402
    run_legacy_subset,
    run_sequence_parity,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Backtest v2")
    ap.add_argument(
        "--mode",
        choices=("sequence", "legacy"),
        default="sequence",
        help="sequence=parity with current prod motor (default)",
    )
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--htf", default="H4", help="sequence/legacy HTF (default H4)")
    ap.add_argument("--ltf", default="M15")
    ap.add_argument("--max-hold", type=int, default=None)
    ap.add_argument("--counter-trend", action="store_true")
    ap.add_argument("--no-displacement", action="store_true")
    ap.add_argument("--no-cost", action="store_true")
    ap.add_argument("--oos", type=float, default=0.3, help="OOS fraction for mtf (0=off)")
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--no-live-table",
        action="store_true",
        help="disable live structure CSV streaming",
    )
    ap.add_argument(
        "--quiet-live",
        action="store_true",
        help="(default behavior) CSV only; kept for compatibility",
    )
    ap.add_argument(
        "--verbose-live",
        action="store_true",
        help="print every structure row to console (noisy; off by default)",
    )
    args = ap.parse_args()

    mode = args.mode
    if mode == "legacy":
        mode = "sequence"  # same motor

    mode_dir = "sequence"
    out = Path(args.out) if args.out else ROOT / "results" / "bt_v2" / args.symbol / mode_dir

    live = not args.no_live_table
    # Professional default: CSV streaming only. Row dump requires --verbose-live.
    live_console = bool(getattr(args, "verbose_live", False))

    print(f"[v2] mode={mode}  symbol={args.symbol}  {args.htf}->{args.ltf}", flush=True)
    print(
        "[v2] Clock=LTF; HTF closed-only; fill=next_open; costs ON unless --no-cost.",
        flush=True,
    )
    if live:
        print(
            f"[v2] Structure table → {out / 'live_structure.csv'} "
            f"(quiet milestones; use --verbose-live only if you want every row)",
            flush=True,
        )

    max_hold = args.max_hold if args.max_hold is not None else 48
    payload = run_sequence_parity(
        args.symbol,
        htf=args.htf,
        ltf=args.ltf,
        max_hold=max_hold,
        counter_trend=args.counter_trend,
        require_displacement=not args.no_displacement,
        no_cost=args.no_cost,
        out_dir=out,
        live_table=live,
        live_console=live_console,
    )

    m = payload["metrics"]
    c = payload["coverage"]
    print(f"\n===== RESULT [{payload['coverage_mode']}] =====", flush=True)
    print(f"  symbol       : {payload['symbol']}", flush=True)
    if "cascade" in payload:
        print(f"  cascade      : {payload['cascade']}", flush=True)
    if payload.get("parity_with"):
        print(f"  parity       : {payload['parity_with']}", flush=True)
    print(f"  orders       : {payload['n_orders']}", flush=True)
    print(f"  trades       : {m['trades']}", flush=True)
    print(f"  winrate      : {m['winrate']*100:.1f}%", flush=True)
    print(f"  profit factor: {m['pf']:.3f}", flush=True)
    print(f"  total R      : {m['total_r']:.1f}", flush=True)
    print(f"  exits        : {payload['exits']}", flush=True)
    if payload.get("filter_stats"):
        print(f"  filters      : {payload['filter_stats']}", flush=True)
    if payload.get("oos"):
        o = payload["oos"]
        print(
            f"  OOS split    : IS trades={o['is']['trades']} PF={o['is']['pf']:.3f} | "
            f"OOS trades={o['oos']['trades']} PF={o['oos']['pf']:.3f}",
            flush=True,
        )
    if payload.get("live_structure_csv"):
        print(f"  live table   : {payload['live_structure_csv']}", flush=True)
    if payload.get("funnel"):
        f = payload["funnel"]
        print(f"  funnel (B2)  : SWEEP={f.get('SWEEP', 0)}  "
              f"DISPLACE={f.get('DISPLACE', 0)}  "
              f"BOS={f.get('BOS', 0)}  ENTRY={f.get('ENTRY', 0)}", flush=True)
    print(f"\n----- Coverage Report -----", flush=True)
    print(f"  coverage_pct : {c['coverage_pct']}%", flush=True)
    print(f"  implemented  : {c['implemented']} / required {c['required']}", flush=True)
    print(f"  partial      : {c['partial']}  missing: {c['missing']}", flush=True)
    print(f"  verdict      : {c['verdict']}", flush=True)
    print(f"\n  artifacts    : {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
