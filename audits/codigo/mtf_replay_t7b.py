"""T7b monthly replay with canonical complete historical setup population."""
from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

from audits.codigo.mtf_replay_t7 import (
    ROOT, WINDOW_END, WINDOW_START, _commit, _peak_working_set_mb,
    _window_projection, derive_h4, load_source,
)
from backtest.mtf_replay import INTRADAY_H4_M15, MTFReplayOrchestrator, ReplayConfig, make_chunks, write_chunks
from backtest.schema import logical_checksum, validate_mtf_replay, write_mtf_replay
from engine.historical_event_objects import build_historical_event_objects
from engine.market_object import ObjectType
from engine.market_state import MarketState


def _state_and_context(frames: dict[str, pd.DataFrame]):
    population = build_historical_event_objects(frames)
    state = MarketState()
    for obj in population["objects"]:
        state.ingest(deepcopy(obj))
    bos = sorted(
        (obj for obj in population["objects"] if obj.type is ObjectType.BOS),
        key=lambda obj: (pd.Timestamp(obj.tradable_time), obj.id),
    )

    def context(now):
        visible = [obj for obj in bos if pd.Timestamp(obj.tradable_time) <= now]
        if not visible:
            return None
        latest = visible[-1]
        return {
            "htf_bias": "bullish" if latest.direction > 0 else "bearish",
            "direction": latest.direction,
            "aligned": True,
        }

    return state, context, population


def _run(frames, dataset_hash, commit, *, measure=False):
    state, context, population = _state_and_context(frames)
    config = ReplayConfig(
        symbol="EURUSD", profile=INTRADAY_H4_M15, checkpoint_every=250,
        chunk_size=500, dataset_hash=dataset_hash, code_commit=commit,
    )
    started = time.perf_counter()
    artifact = MTFReplayOrchestrator(config, state, context_provider=context).run(frames)
    elapsed = time.perf_counter() - started
    validate_mtf_replay(artifact)
    return artifact, population, elapsed, _peak_working_set_mb() if measure else None


def execute(output_dir: Path) -> dict[str, Any]:
    m15, source_manifest, dataset_hash = load_source()
    frames = {"M15": m15, "H4": derive_h4(m15)}
    commit = _commit()
    first, population, elapsed, peak_mb = _run(frames, dataset_hash, commit, measure=True)
    second, _, _, _ = _run(frames, dataset_hash, commit)
    checksum = logical_checksum(first)

    cuts = []
    january = m15.loc[(m15["time"] >= WINDOW_START) & (m15["time"] < WINDOW_END), "time"]
    for ratio in (0.25, 0.50, 0.75, 0.90):
        cutoff = january.iloc[max(0, int(len(january) * ratio) - 1)]
        prefix_frames = {tf: frame.loc[frame["time"] <= cutoff].copy() for tf, frame in frames.items()}
        prefix, prefix_population, _, _ = _run(prefix_frames, dataset_hash, commit)
        cuts.append({
            "ratio": ratio, "cutoff": cutoff.isoformat(),
            "replay_pass": logical_checksum(_window_projection(first, cutoff)) == logical_checksum(_window_projection(prefix, cutoff)),
            "producer_counts": prefix_population["counts"],
        })

    january_setups = [row for row in first["setups"] if WINDOW_START <= pd.Timestamp(row["observation_time"]) < WINDOW_END]
    complete = [row for row in january_setups if row.get("confirmation") and row.get("trigger")]
    eligible = [row for row in complete if row.get("eligibility") == "ELIGIBLE"]
    january_episodes = [row for row in first["episodes"] if WINDOW_START <= pd.Timestamp(row["observation_time"]) < WINDOW_END]
    january_disp = [
        obj for obj in population["objects"]
        if obj.type is ObjectType.DISPLACEMENT and WINDOW_START <= pd.Timestamp(obj.tradable_time) < WINDOW_END
    ]
    no_pretrigger = all(
        pd.Timestamp(row["observation_time"]) >= pd.Timestamp(row["trigger"]["tradable_time"])
        for row in complete
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_mtf_replay(first, output_dir / "mtf_replay_t7b_2025_01.json")
    manifest = write_chunks(first, output_dir / "viewer", 500)
    gates = {
        "producer_population": bool(population["counts"]["bos_h4_linked"] and population["counts"]["displacement_m15_linked"]),
        "january_displacement": bool(january_disp),
        "complete_setups": bool(complete),
        "eligible_setups": bool(eligible),
        "episodes": bool(january_episodes),
        "no_pretrigger_setup": no_pretrigger,
        "determinism": checksum == logical_checksum(second),
        "full_prefix": all(item["replay_pass"] for item in cuts),
        "chunk_manifest": manifest["artifact_checksum"] == checksum,
    }
    report = {
        "status": "PASS_TECHNICAL_BLOCKED_PROVENANCE" if all(gates.values()) else "FAIL",
        "commit": commit, "dataset_hash": dataset_hash, "source_manifest": source_manifest,
        "profile": INTRADAY_H4_M15.to_dict(), "producer": population["counts"],
        "producer_config": population["config"], "gates": gates, "full_prefix": cuts,
        "counts": {
            "january_setup_records": len(january_setups), "january_complete_records": len(complete),
            "january_eligible_records": len(eligible), "january_episodes": len(january_episodes),
            "january_displacement_objects": len(january_disp), "trades": len(first["trades"]),
        },
        "checksum": checksum,
        "resources": {"elapsed_seconds_run_1": elapsed, "peak_working_set_mb_run_1": peak_mb},
        "provenance": {"mechanical_integrity": "PASS", "formal_status": "BLOCKED_PROVENANCE", "mt5_used": False},
        "edge_measured": False, "optimization_executed": False, "ai_training_executed": False,
        "can_trade": False, "promotion_authorized": False,
    }
    (output_dir / "t7b_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "audits" / "mtf_replay" / "t7b_2025_01")
    args = parser.parse_args()
    report = execute(args.output_dir.resolve())
    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
