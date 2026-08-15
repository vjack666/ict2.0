"""v2 orchestrator — Plan → Orders → pure Simulator.

Modes:
  sequence     — SAME as production run_backtest sequence (H4→M15, R6 defaults)
  legacy_subset — alias of sequence (F0 packaging)

Live structure table: during sequence/legacy runs, BOS/CHOCH/FVG/SWEEP/OB
stream to CSV + console as onsets are found, then SIGNAL/TRADE rows.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from ict_backtest.costs import resolve_cost
from ict_backtest.data_feed import load_frames
from engine.market_structure import detect_market_structure
from ict_backtest.run_backtest import _metrics, _write_runner_progress, generate_sequence_signals
from ict_backtest.v2.coverage import build_coverage_report
from ict_backtest.v2.event_log import EventLog
from ict_backtest.v2.live_structure_table import (
    LiveStructureTable,
    emit_signal_row,
    emit_trade_row,
    stream_structure_from_ms,
)
from ict_backtest.v2.simulator import simulate_order
from ict_backtest.v2.strategy_legacy import explanation_for_trade, signals_to_plan


def _simulate_plan(
    plan,
    ltf_df,
    cost,
    event_log,
    explainer,
    *,
    live: LiveStructureTable | None = None,
    ltf: str = "M15",
):
    pnls: list[float] = []
    exits: dict[str, int] = {}
    explanations = []
    n = len(plan.orders)
    for i, order in enumerate(plan.orders, 1):
        result, meta = simulate_order(order, ltf_df, cost=cost, event_log=event_log)
        if result is None:
            reason = str(meta.get("exit_reason", "rejected"))
            exits[reason] = exits.get(reason, 0) + 1
            continue
        pnls.append(result.pnl_r)
        exits[result.exit_reason] = exits.get(result.exit_reason, 0) + 1
        explanations.append(explainer(plan, order, result.exit_reason))
        if live is not None:
            emit_trade_row(
                live,
                time=str(getattr(order, "signal_time", "")),
                tf=ltf,
                direction=int(order.direction),
                exit_reason=str(result.exit_reason),
                pnl_r=float(result.pnl_r),
            )
        if n:
            _write_runner_progress(
                current=f"simulate {i}/{n}",
                done=i,
                total=n,
                unit="trades",
            )
    return pnls, exits, explanations


def _write_artifacts(out: Path, payload, coverage, event_log, explanations) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "run_summary.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    coverage.save_json(out / "coverage_report.json")
    event_log.to_jsonl(out / "event_log.jsonl")
    with (out / "explanations.jsonl").open("w", encoding="utf-8") as f:
        for e in explanations:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")


def run_sequence_parity(
    symbol: str,
    *,
    htf: str = "H4",
    ltf: str = "M15",
    max_hold: int = 48,
    counter_trend: bool = False,
    require_displacement: bool = True,
    displace_gap: int = 6,
    bos_gap: int | None = None,
    fill_mode: str = "next_open",
    cost: dict[str, float] | None = None,
    no_cost: bool = False,
    out_dir: Path | str | None = None,
    frames: dict[str, pd.DataFrame] | None = None,
    live_table: bool = True,
    live_console: bool = False,
    enable_pd_index: bool = True,
) -> dict[str, Any]:
    """Same decision path as `ict_backtest/run_backtest.py --engine sequence`.

    R6 defaults: next_open fill, costs ON (unless no_cost), HTF closed-only
    inside sequence. Plus live structure CSV streaming.
    """
    if cost is None and not no_cost:
        cost = resolve_cost(symbol)
    if no_cost:
        cost = None

    out = Path(out_dir) if out_dir is not None else None
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)

    _write_runner_progress(
        current=f"[1/4] load frames {symbol}",
        done=0,
        total=4,
        unit="stages",
    )
    print(f"[v2/sequence] load {symbol} {htf}->{ltf} ...", flush=True)
    if frames is None:
        frames = load_frames(symbol, tuple(dict.fromkeys([htf, ltf, "D1"])))

    _write_runner_progress(
        current=f"[2/4] market_structure {symbol}",
        done=1,
        total=4,
        unit="stages",
    )
    print(f"[v2/sequence] market_structure ...", flush=True)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]

    event_log = EventLog()
    live_path = (out / "live_structure.csv") if out is not None else Path(
        "results"
    ) / "bt_v2" / symbol / "sequence" / "live_structure.csv"

    n_struct = 0
    with LiveStructureTable(
        live_path,
        # Default: CSV only + milestones. Row dump only if live_console=True.
        console=bool(live_console and live_table),
        console_every=1 if live_console else 0,
        milestone_every=250 if live_table else 0,
        event_log_append=event_log.append if live_table else None,
    ) as live:
        if live_table:
            # Stream LTF first (execution), then HTF — still sorted by time inside
            n_struct = stream_structure_from_ms(
                ms,
                live,
                tfs=[t for t in (ltf, htf, "D1") if t in ms],
            )

        _write_runner_progress(
            current=f"[3/4] sequence signals {symbol}",
            done=2,
            total=4,
            unit="stages",
        )
        print(f"[v2/sequence] generate_sequence_signals ...", flush=True)
        signals, funnel = generate_sequence_signals(
            symbol,
            htf,
            ltf,
            counter_trend=counter_trend,
            require_displacement=require_displacement,
            displace_gap=displace_gap,
            bos_gap=bos_gap,
            frames=frames,
            fill_mode=fill_mode,
            enable_pd_index=enable_pd_index,
            return_phase_seen=True,
        )
        print(f"[v2/sequence] signals: {len(signals)}", flush=True)

        for s in signals:
            if live_table:
                emit_signal_row(
                    live,
                    time=str(s.time),
                    tf=ltf,
                    direction=int(s.direction),
                    entry=float(s.entry),
                    sl=float(s.stop_loss),
                    tp=float(s.take_profit),
                    note="sequence",
                )

        plan = signals_to_plan(
            signals,
            symbol=symbol,
            model_id="sequence_parity",
            max_hold_bars=max_hold,
            htf=htf,
            ltf=ltf,
            event_log=event_log,
        )

        _write_runner_progress(
            current=f"[4/4] simulate {len(plan.orders)} orders",
            done=3,
            total=4,
            unit="stages",
        )
        print(f"[v2/sequence] simulate {len(plan.orders)} orders ...", flush=True)
        pnls, exits, explanations = _simulate_plan(
            plan,
            ltf_df,
            cost,
            event_log,
            explanation_for_trade,
            live=live if live_table else None,
            ltf=ltf,
        )

    metrics = _metrics(pnls)
    coverage = build_coverage_report(
        model_id=plan.model_id,
        coverage_mode="legacy_subset",  # same decision surface as production subset
    )
    payload: dict[str, Any] = {
        "symbol": symbol,
        "htf": htf,
        "ltf": ltf,
        "coverage_mode": "sequence_parity",
        "model_id": plan.model_id,
        "parity_with": "ict_backtest.run_backtest --engine sequence",
        "fill_mode": fill_mode,
        "costs": cost,
        "max_hold": max_hold,
        "n_orders": len(plan.orders),
        "n_structure_events": n_struct,
        "live_structure_csv": str(live_path),
        "metrics": metrics,
        "exits": exits,
        "coverage": coverage.to_dict(),
        "verdict": coverage.verdict,
        "n_events": len(event_log),
        "n_explanations": len(explanations),
        "funnel": funnel,
    }
    if out is not None:
        _write_artifacts(out, payload, coverage, event_log, explanations)
        # also copy pointer at stable name
        (out / "LIVE_TABLE.txt").write_text(
            f"Live structure table:\n  {live_path}\n"
            f"Events: structure={n_struct} + SIGNAL/TRADE rows in same CSV\n"
            f"Tail with: Get-Content {live_path} -Wait -Tail 20\n",
            encoding="utf-8",
        )
    _write_runner_progress(
        current=f"done {symbol} PF={metrics['pf']:.3f} n={metrics['trades']}",
        done=4,
        total=4,
        unit="stages",
    )
    return payload


# Back-compat name used by older CLI
def run_legacy_subset(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Alias → sequence_parity (same motor as production sequence)."""
    # Map older default max_hold=16 if not provided
    if "max_hold" not in kwargs:
        kwargs["max_hold"] = 16
    return run_sequence_parity(*args, **kwargs)



