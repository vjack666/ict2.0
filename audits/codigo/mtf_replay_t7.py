"""T7: one-month real-data acceptance for MTF Replay Orchestrator v1.

This runner is frozen by EXP_MTF_REPLAY_T7_2025_01_PREREGISTRATION.md. It does
not optimize, train, calculate edge, create execution levels, use MT5, download,
or repair source rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import tracemalloc
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.mtf_replay import INTRADAY_H4_M15, MTFReplayOrchestrator, ReplayConfig, make_chunks, write_chunks
from backtest.schema import logical_checksum, validate_mtf_replay, write_mtf_replay
from engine.ltf_canonical_feed import build_canonical_objects
from engine.market_state import MarketState


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "datasets" / "eurusd_dukascopy_intraday_2021_2025" / "raw_monthly"
SOURCES = (
    DATA_ROOT / "2024" / "eurusd-m15-bid-2024-12-01-2025-01-01.csv",
    DATA_ROOT / "2025" / "eurusd-m15-bid-2025-01-01-2025-02-01.csv",
)
WINDOW_START = pd.Timestamp("2025-01-01T00:00:00Z")
WINDOW_END = pd.Timestamp("2025-02-01T00:00:00Z")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_source() -> tuple[pd.DataFrame, list[dict[str, Any]], str]:
    frames: list[pd.DataFrame] = []
    manifest: list[dict[str, Any]] = []
    for path in SOURCES:
        raw = pd.read_csv(path)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if set(raw.columns) != required:
            raise ValueError(f"unexpected columns in {path.name}: {list(raw.columns)}")
        opened = pd.to_datetime(raw["timestamp"], unit="ms", utc=True)
        invalid = (
            raw[["open", "high", "low", "close", "volume"]].isna().any(axis=1)
            | (raw["high"] < raw[["open", "close", "low"]].max(axis=1))
            | (raw["low"] > raw[["open", "close", "high"]].min(axis=1))
            | (raw["volume"] < 0)
        )
        if invalid.any() or opened.duplicated().any() or not opened.is_monotonic_increasing:
            raise ValueError(f"mechanical validation failed for {path.name}")
        frame = raw[["open", "high", "low", "close", "volume"]].copy()
        frame["time"] = opened + pd.Timedelta(minutes=15)
        frames.append(frame)
        manifest.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
            "rows": len(raw),
            "open_time_min": opened.min().isoformat(),
            "open_time_max": opened.max().isoformat(),
            "gaps_gt_15m": int((opened.diff() > pd.Timedelta(minutes=15)).sum()),
        })
    combined = pd.concat(frames, ignore_index=True).sort_values("time").reset_index(drop=True)
    if combined["time"].duplicated().any() or not combined["time"].is_monotonic_increasing:
        raise ValueError("combined M15 source is not unique and monotonic")
    encoded = "\n".join(
        f'{row["path"]}|{row["sha256"]}|{row["bytes"]}|{row["rows"]}' for row in manifest
    ).encode()
    return combined, manifest, hashlib.sha256(encoded).hexdigest()


def derive_h4(m15: pd.DataFrame) -> pd.DataFrame:
    opened = m15.assign(open_time=m15["time"] - pd.Timedelta(minutes=15)).set_index("open_time")
    h4 = opened.resample("4h", origin="epoch", closed="left", label="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"), count=("close", "size"),
    )
    h4 = h4[h4["count"] > 0].reset_index()
    h4["time"] = h4.pop("open_time") + pd.Timedelta(hours=4)
    return h4[["time", "open", "high", "low", "close", "volume", "count"]]


def build_state(frames: dict[str, pd.DataFrame]) -> tuple[MarketState, dict[str, int]]:
    assembled = build_canonical_objects(
        frames, frames["M15"]["time"].max(), timeframes=("H4", "M15"), symbol="EURUSD"
    )
    state = MarketState()
    for obj in assembled["objects"]:
        state.ingest(deepcopy(obj))
    counts = {tf: len(items) for tf, items in assembled["objects_by_tf"].items()}
    counts["relations_same_tf"] = len(assembled["relations"])
    return state, counts


def _window_projection(artifact: dict[str, Any], cutoff: pd.Timestamp) -> dict[str, Any]:
    def visible(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if pd.Timestamp(row["observation_time"]) <= cutoff]
    return {
        "timeline": visible(artifact["timeline"]),
        "state_deltas": visible(artifact["state_deltas"]),
        "setups": visible(artifact["setups"]),
        "episodes": visible(artifact["episodes"]),
        "invalidations": visible(artifact["invalidations"]),
        "trades": visible(artifact["trades"]),
        "rejections": visible(artifact["rejections"]),
    }


def run_once(frames: dict[str, pd.DataFrame], dataset_hash: str, commit: str) -> tuple[dict[str, Any], float, float, dict[str, int]]:
    state, object_counts = build_state(frames)
    config = ReplayConfig(
        symbol="EURUSD", profile=INTRADAY_H4_M15, checkpoint_every=250,
        chunk_size=500, dataset_hash=dataset_hash, code_commit=commit,
    )
    tracemalloc.start()
    started = time.perf_counter()
    artifact = MTFReplayOrchestrator(config, state).run(frames)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    validate_mtf_replay(artifact)
    return artifact, elapsed, peak / (1024 * 1024), object_counts


def execute(output_dir: Path) -> dict[str, Any]:
    m15, manifest, dataset_hash = load_source()
    h4 = derive_h4(m15)
    frames = {"H4": h4, "M15": m15}
    commit = _commit()
    first, elapsed, peak_mb, object_counts = run_once(frames, dataset_hash, commit)
    second, _, _, _ = run_once(frames, dataset_hash, commit)
    checksum = logical_checksum(first)
    deterministic = checksum == logical_checksum(second)

    cuts: list[dict[str, Any]] = []
    january_times = m15.loc[(m15["time"] >= WINDOW_START) & (m15["time"] < WINDOW_END), "time"]
    for ratio in (0.25, 0.50, 0.75, 0.90):
        cutoff = january_times.iloc[max(0, int(len(january_times) * ratio) - 1)]
        prefix_frames = {tf: frame.loc[frame["time"] <= cutoff].copy() for tf, frame in frames.items()}
        prefix, _, _, _ = run_once(prefix_frames, dataset_hash, commit)
        full_view = _window_projection(first, cutoff)
        prefix_view = _window_projection(prefix, cutoff)
        cuts.append({
            "ratio": ratio, "cutoff": cutoff.isoformat(),
            "pass": logical_checksum(full_view) == logical_checksum(prefix_view),
            "full_counts": {key: len(value) for key, value in full_view.items()},
            "prefix_counts": {key: len(value) for key, value in prefix_view.items()},
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    write_mtf_replay(first, output_dir / "mtf_replay_t7_2025_01.json")
    manifest_500 = write_chunks(first, output_dir / "viewer", 500)
    manifest_257 = make_chunks(first, 257)
    jan_timeline = [row for row in first["timeline"] if WINDOW_START <= pd.Timestamp(row["observation_time"]) < WINDOW_END]
    report = {
        "status": "PASS_TECHNICAL_BLOCKED_PROVENANCE" if deterministic and all(c["pass"] for c in cuts) else "FAIL",
        "objective": "T7 real one-month technical replay; no edge, optimization, AI, MT5, or orders",
        "window": {"start": WINDOW_START.isoformat(), "end": WINDOW_END.isoformat(), "warmup": "2024-12"},
        "profile": INTRADAY_H4_M15.to_dict(),
        "commit": commit,
        "dataset_hash": dataset_hash,
        "source_manifest": manifest,
        "provenance": {
            "mechanical_integrity": "PASS",
            "formal_status": "BLOCKED_PROVENANCE",
            "license_permitted_use": "UNKNOWN",
            "acquired_at_utc": None,
            "mt5_used": False,
            "raw_source_modified": False,
        },
        "counts": {
            "m15_total_with_warmup": len(m15), "h4_total_with_warmup": len(h4),
            "january_close_batches": len(jan_timeline), **object_counts,
            "setups": len(first["setups"]), "episodes": len(first["episodes"]),
            "trades": len(first["trades"]), "rejections": len(first["rejections"]),
        },
        "population_note": "NO_COMPLETE_SETUP_POPULATION" if not first["setups"] else "COMPLETE_SETUP_POPULATION_PRESENT",
        "determinism": {"pass": deterministic, "run_1_checksum": checksum, "run_2_checksum": logical_checksum(second)},
        "chunk_invariance": {
            "pass": manifest_500["artifact_checksum"] == manifest_257["artifact_checksum"] == checksum,
            "chunk_500_count": len(manifest_500["chunks"]), "chunk_257_count": len(manifest_257["chunks"]),
        },
        "full_prefix": cuts,
        "resources": {"elapsed_seconds_run_1": elapsed, "tracemalloc_peak_mb_run_1": peak_mb},
        "artifact": "mtf_replay_t7_2025_01.json",
        "viewer_manifest": "viewer/manifest.json",
        "edge_measured": False, "optimization_executed": False, "ai_training_executed": False,
        "can_trade": False, "promotion_authorized": False,
    }
    (output_dir / "t7_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports" / "audits" / "mtf_replay" / "t7_2025_01")
    args = parser.parse_args()
    report = execute(args.output_dir.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

