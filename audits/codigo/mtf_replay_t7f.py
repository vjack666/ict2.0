"""T7f: fixed 2006-2020 causal replay, executed in yearly local batches.

The runner is deliberately an integrity/population gate.  It never labels an
outcome, fits a model, derives SL/TP, or measures edge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from audits.codigo.mtf_replay_t7 import ROOT, _commit, _peak_working_set_mb, _window_projection, derive_h4
from audits.codigo.mtf_replay_t7b import _run
from backtest.mtf_replay import make_chunks, write_chunks
from backtest.schema import logical_checksum, validate_mtf_replay, write_mtf_replay


MANIFEST = ROOT / "datasets" / "eurusd_dukascopy_intraday_2006_2020_manifest.json"
DEFAULT_OUTPUT = ROOT / "reports" / "audits" / "mtf_replay" / "t7f_2006_2020"
RATIOS = (0.25, 0.50, 0.75, 0.90)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_manifest() -> list[dict[str, Any]]:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("T7F_MANIFEST_INVALID")
    for row in rows:
        path = ROOT / str(row["path"])
        if not path.is_file() or path.stat().st_size != int(row["bytes"]):
            raise ValueError(f"T7F_MANIFEST_FILE_MISSING_OR_SIZE: {path}")
        if _sha256(path) != row["sha256"]:
            raise ValueError(f"T7F_MANIFEST_HASH_MISMATCH: {path}")
    return sorted(rows, key=lambda row: str(row["path"]))


def _year_for(row: dict[str, Any]) -> int:
    return int(Path(str(row["path"])).parent.name)


def _dataset_hash(rows: Iterable[dict[str, Any]]) -> str:
    lines = [f"{row['path']}|{row['sha256']}|{row['bytes']}" for row in rows]
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def _load(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for item in rows:
        raw = pd.read_csv(ROOT / str(item["path"]))
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if set(raw.columns) != required:
            raise ValueError(f"T7F_SCHEMA: {item['path']}")
        opened = pd.to_datetime(raw["timestamp"], unit="ms", utc=True)
        invalid = (
            raw[["open", "high", "low", "close", "volume"]].isna().any(axis=1)
            | (raw["high"] < raw[["open", "close", "low"]].max(axis=1))
            | (raw["low"] > raw[["open", "close", "high"]].min(axis=1))
            | (raw["volume"] < 0)
        )
        if invalid.any() or opened.duplicated().any() or not opened.is_monotonic_increasing:
            raise ValueError(f"T7F_MECHANICAL_INTEGRITY: {item['path']}")
        frame = raw[["open", "high", "low", "close", "volume"]].copy()
        frame["time"] = opened + pd.Timedelta(minutes=15)
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True).sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if not result["time"].is_monotonic_increasing:
        raise ValueError("T7F_COMBINED_TIME_ORDER")
    return result


def _year_rows(manifest: list[dict[str, Any]], year: int) -> list[dict[str, Any]]:
    selected = [row for row in manifest if _year_for(row) == year]
    if len(selected) != 12:
        raise ValueError(f"T7F_EXPECTED_12_MONTHS: {year}")
    if year > 2006:
        warmup = [row for row in manifest if _year_for(row) == year - 1 and "-12-01-" in str(row["path"])]
        if len(warmup) != 1:
            raise ValueError(f"T7F_MISSING_WARMUP: {year}")
        selected = [*warmup, *selected]
    return sorted(selected, key=lambda row: str(row["path"]))


def _window(artifact: dict[str, Any], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, list[Any]]:
    return {
        key: [row for row in artifact.get(key, []) if start <= pd.Timestamp(row.get("observation_time", row.get("decision_time", start))) < end]
        for key in ("setups", "episodes", "trades", "rejections")
    }


def execute_year(year: int, manifest: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    sources = _year_rows(manifest, year)
    dataset_hash = _dataset_hash(sources)
    m15 = _load(sources)
    frames = {"M15": m15, "H4": derive_h4(m15)}
    start = pd.Timestamp(f"{year}-01-01T00:00:00Z")
    end = pd.Timestamp(f"{year + 1}-01-01T00:00:00Z")
    commit = _commit()
    first, population, elapsed, peak = _run(frames, dataset_hash, commit, measure=True)
    second, _, _, _ = _run(frames, dataset_hash, commit)
    validate_mtf_replay(first)
    checksum = logical_checksum(first)
    year_times = m15.loc[(m15["time"] >= start) & (m15["time"] < end), "time"]
    cuts: list[dict[str, Any]] = []
    for ratio in RATIOS:
        cutoff = year_times.iloc[max(0, int(len(year_times) * ratio) - 1)]
        prefix_frames = {tf: frame.loc[frame["time"] <= cutoff].copy() for tf, frame in frames.items()}
        prefix, _, _, _ = _run(prefix_frames, dataset_hash, commit)
        cuts.append({
            "ratio": ratio,
            "cutoff": cutoff.isoformat(),
            "replay_pass": logical_checksum(_window_projection(first, cutoff)) == logical_checksum(_window_projection(prefix, cutoff)),
        })
    subset = _window(first, start, end)
    complete = [row for row in subset["setups"] if row.get("confirmation") and row.get("trigger")]
    eligible = [row for row in complete if row.get("eligibility") == "ELIGIBLE"]
    target = output_dir / str(year)
    target.mkdir(parents=True, exist_ok=True)
    write_mtf_replay(first, target / f"mtf_replay_t7f_{year}.json")
    chunks = write_chunks(first, target / "viewer", 500)
    gates = {
        "determinism": checksum == logical_checksum(second),
        "full_prefix": all(item["replay_pass"] for item in cuts),
        "schema": True,
        "chunk_manifest": chunks["artifact_checksum"] == checksum,
    }
    report = {
        "run_id": "t7f", "year": year, "commit": commit, "dataset_hash": dataset_hash,
        "sources": sources, "producer": population["counts"], "producer_config": population["config"],
        "gates": gates, "full_prefix": cuts,
        "counts": {
            "setup_records": len(subset["setups"]), "complete_records": len(complete),
            "eligible_records": len(eligible), "episodes": len(subset["episodes"]),
            "trades": len(subset["trades"]), "rejections": len(subset["rejections"]),
        },
        "population_status": "COMPLETE_SETUP_POPULATION" if complete else "NO_COMPLETE_SETUP_POPULATION_H4_AUTHORITY_REPLAY",
        "checksum": checksum, "resources": {"elapsed_seconds_run_1": elapsed, "peak_working_set_mb_run_1": peak},
        "provenance": {"mechanical_integrity": "PASS", "formal_status": "BLOCKED_PROVENANCE", "mt5_used": False},
        "edge_measured": False, "ai_training_executed": False, "can_trade": False,
        "status": "PASS_TECHNICAL_BLOCKED_PROVENANCE" if all(gates.values()) else "FAIL",
    }
    (target / "t7f_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", default="2006-2020", help="comma list or inclusive range")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if "-" in args.years:
        first, last = (int(value) for value in args.years.split("-", 1))
        years = list(range(first, last + 1))
    else:
        years = [int(value) for value in args.years.split(",")]
    manifest = _read_manifest()
    reports = [execute_year(year, manifest, args.output_dir.resolve()) for year in years]
    summary = {
        "run_id": "t7f", "years": years, "reports": reports,
        "status": "PASS_TECHNICAL_BLOCKED_PROVENANCE" if all(item["status"] != "FAIL" for item in reports) else "FAIL",
        "edge_measured": False, "ai_training_executed": False, "can_trade": False,
    }
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "t7f_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
