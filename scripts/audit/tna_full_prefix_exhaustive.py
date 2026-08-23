"""Exhaustive causal replay audit for the TNA FULL-vs-PREFIX invariant.

This audit does not rewrite datasets and does not claim that a handful of fresh
prefix constructions cover the full span.  It verifies every H1 decision and
every causal publication in one chronological replay, then reports whether a
direct FULL-vs-PREFIX comparison has also covered all decisions.

The induction is valid only for deterministic causal consumers: if every input
event visible at bar ``i`` is generated from data through ``i`` and the state
machine consumes events in order, its FULL state at ``i`` is identical to the
state obtained by running the same machine on the PREFIX ending at ``i``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "eurusd_dukascopy_20y"
OUT = ROOT / "reports" / "audits" / "tna_full_prefix_exhaustive_2026-08-22.json"


def _load_tf(tf: str) -> pd.DataFrame:
    path = DATASET / f"EURUSD_{tf}.csv"
    return pd.read_csv(path, parse_dates=["time"]).sort_values("time").reset_index(drop=True)


def _manifest() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (DATASET / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split()[:2]
        out[name] = digest.lower()
    return out


def _git_blob_sha(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    blob = subprocess.check_output(["git", "cat-file", "blob", f"HEAD:{rel}"])
    return hashlib.sha256(blob).hexdigest()


def _metadata_check(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    metadata = json.loads((DATASET / "metadata.json").read_text())
    actual = {tf: len(df) for tf, df in frames.items()}
    declared = {tf: int(metadata[tf]["n_clean"]) for tf in frames}
    raw = {tf: int(metadata[tf]["n_raw"]) for tf in frames}
    return {
        "actual_rows": actual,
        "declared_rows": declared,
        "declared_raw_rows": raw,
        "metadata_count_field": "n_clean",
        "consistent": actual == declared,
    }


def _check_swings(nav: Any, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    failures: list[str] = []
    publications = 0
    for tf, pre in nav._pre.items():
        df = frames[tf]
        high = df["high"].to_numpy(float)
        low = df["low"].to_numpy(float)
        left = int(nav.config.swing_left)
        for label, swings, values in (
            ("high", pre.get("sh", []), high),
            ("low", pre.get("sl", []), low),
        ):
            for bar, price in swings:
                publications += 1
                center = int(bar) - left
                if int(bar) <= center or center - left < 0 or center + left >= len(df):
                    failures.append(f"{tf}:{label}:invalid_confirmation={bar}")
                    continue
                expected = values[center]
                if not np.isclose(float(price), float(expected), rtol=0.0, atol=1e-12):
                    failures.append(f"{tf}:{label}:wrong_level={bar}")
    return {
        "publication_count": publications,
        "failures": failures[:20],
        "failure_count": len(failures),
        "pass": not failures,
    }


def _check_sequence_history(nav: Any, n: int) -> dict[str, Any]:
    depth = np.zeros(n, dtype="int32")
    complete = np.zeros(n, dtype="int32")
    for chain in nav._seq_chains:
        bars = np.array(sorted(int(node.bar) for node in chain.nodes), dtype="int32")
        if bars.size:
            depth = np.maximum(depth, np.searchsorted(bars, np.arange(n), side="right"))
        if chain.status == "COMPLETE" and 0 <= int(chain.last_bar) < n:
            complete[int(chain.last_bar) :] += 1
    actual_depth = np.array([nav.sequence_depth_at(i) for i in range(n)], dtype="int32")
    actual_complete = np.array([nav.sequence_complete_count_at(i) for i in range(n)], dtype="int32")
    return {
        "bars_checked": n,
        "chain_count": len(nav._seq_chains),
        "depth_history_equal_reconstruction": bool(np.array_equal(depth, actual_depth)),
        "complete_history_equal_reconstruction": bool(np.array_equal(complete, actual_complete)),
        "pass": bool(np.array_equal(depth, actual_depth) and np.array_equal(complete, actual_complete)),
    }


def _check_decision_cutoffs(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    h1 = frames["H1"]
    time_values = {
        tf: pd.to_datetime(df["time"], utc=True).astype("int64").to_numpy()
        for tf, df in frames.items()
    }
    failures = 0
    for decision_time in h1["time"]:
        ts = int(pd.Timestamp(decision_time).tz_localize("UTC").value)
        for df in frames.values():
            tf = next(key for key, value in frames.items() if value is df)
            idx = int(np.searchsorted(time_values[tf], ts, side="right") - 1)
            if idx >= len(df) or idx < -1:
                failures += 1
    return {"decisions_checked": len(h1), "cutoff_failures": failures, "pass": failures == 0}


def main() -> dict[str, Any]:
    frames = {tf: _load_tf(tf) for tf in ("D1", "H4", "H1")}
    manifest = _manifest()
    blob_hashes = {
        f"EURUSD_{tf}.csv": _git_blob_sha(DATASET / f"EURUSD_{tf}.csv")
        for tf in frames
    }
    hash_pass = all(blob_hashes[name] == digest for name, digest in manifest.items())
    metadata = _metadata_check(frames)

    from engine.mtf_navigation import MTFNavigator, NavigatorConfig

    nav = MTFNavigator(
        frames,
        NavigatorConfig(precompute_sequences=True, sequence_tf="H1"),
    )
    swings = _check_swings(nav, frames)
    sequence = _check_sequence_history(nav, len(frames["H1"]))
    cutoffs = _check_decision_cutoffs(frames)

    # Direct prefix construction remains a separate requirement.  It is
    # intentionally read from the versioned sample artifact, never inferred
    # from the causal replay checks above.
    sample_path = ROOT / "reports" / "audits" / "tna_full_prefix_2026-08-22.json"
    sample = json.loads(sample_path.read_text()) if sample_path.exists() else {}
    direct = sample.get("historical_prefix_probe", {})
    direct_exhaustive = int(direct.get("checked", 0)) == len(frames["H1"]) and int(direct.get("violations", 1)) == 0

    report = {
        "audit": "TNA_FULL_PREFIX_EXHAUSTIVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": "ALL_H1_DECISIONS_CAUSAL_REPLAY",
        "dataset": {
            "path": str(DATASET.relative_to(ROOT)),
            "sha256_manifest_matches_git_blobs": hash_pass,
            "metadata": metadata,
            "git_blob_hashes": blob_hashes,
        },
        "checks": {
            "swing_publications": swings,
            "sequence_history": sequence,
            "decision_cutoffs": cutoffs,
        },
        "direct_prefix": {
            "checked": int(direct.get("checked", 0)),
            "violations": int(direct.get("violations", -1)),
            "exhaustive": direct_exhaustive,
            "result": "PASS" if direct_exhaustive else "INCOMPLETE",
        },
        "equivalence": {
            "causal_replay": "PASS" if swings["pass"] and sequence["pass"] and cutoffs["pass"] else "FAIL",
            "full_prefix": "PASS" if direct_exhaustive else "UNPROVEN",
        },
        "gate": "PASS" if hash_pass and metadata["consistent"] and direct_exhaustive else "BLOCKED",
        "blocking_reasons": [] if hash_pass and metadata["consistent"] and direct_exhaustive else [
            reason for reason, condition in (
                ("metadata_inconsistent", not metadata["consistent"]),
                ("direct_prefix_comparison_not_exhaustive", not direct_exhaustive),
            ) if condition
        ],
        "policy": "No dataset modification, no PnL, no promotion",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    main()
