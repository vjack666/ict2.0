"""LOCAL_ONLY historical replay exporter for the AI-outcome preregistration.

This entrypoint is deliberately separate from the existing operational visual
exporter.  Its only accepted inputs are the three versioned Dukascopy CSVs
(EURUSD D1/H4/H1); it never discovers or falls back to an operational feed.
The replay itself remains the canonical ``backtest.replay`` consumer of the
engine APIs.  The resulting artifact is observational and fail-closed for
training/promotion decisions.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.replay import ReplayConfig, run_visual_replay
from backtest.schema import validate_visual_backtest, write_visual_backtest
from engine.sequential_outcome import OutcomeConfig


DATASET_DIR = ROOT / "datasets" / "eurusd_dukascopy_20y"
SOURCE_FILES = ("EURUSD_D1.csv", "EURUSD_H4.csv", "EURUSD_H1.csv")
TIMEFRAMES = ("D1", "H4", "H1")
HISTORICAL_HORIZON_BARS = 6
REQUIRED_COLUMNS = ("time", "open", "high", "low", "close")


class HistoricalReplayError(ValueError):
    """Raised when the closed historical source boundary cannot be proven."""


def _source_boundary(dataset_dir: Path) -> dict[str, Path]:
    """Resolve exactly the three allowed CSVs and reject operational inputs."""

    root = Path(dataset_dir).resolve()
    if not root.is_dir():
        raise HistoricalReplayError(f"SOURCE_MISSING: dataset directory is absent: {root}")
    if any(part.casefold() == "raw" for part in root.parts):
        raise HistoricalReplayError(f"MT5_SOURCE_REJECTED: operational raw path: {root}")

    mt5_files = [
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".parquet", ".pq"}
    ]
    if mt5_files:
        raise HistoricalReplayError(
            "MT5_SOURCE_REJECTED: parquet input present under historical source: "
            + ", ".join(str(path) for path in mt5_files)
        )

    csv_names = {path.name for path in root.glob("*.csv")}
    expected = set(SOURCE_FILES)
    if csv_names != expected:
        missing = sorted(expected - csv_names)
        extra = sorted(csv_names - expected)
        raise HistoricalReplayError(
            f"SOURCE_BOUNDARY_INVALID: missing={missing} extra={extra}"
        )
    return {tf: root / filename for tf, filename in zip(TIMEFRAMES, SOURCE_FILES)}


def _read_csv(path: Path, timeframe: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read and strictly validate one source CSV without repairing rows."""

    raw = pd.read_csv(path)
    if tuple(raw.columns) != REQUIRED_COLUMNS:
        raise HistoricalReplayError(
            f"SCHEMA_INVALID: {path.name} columns={list(raw.columns)!r}"
        )
    if raw.empty:
        raise HistoricalReplayError(f"SOURCE_EMPTY: {path}")

    frame = raw.copy()
    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    if frame["time"].isna().any():
        raise HistoricalReplayError(f"TIMESTAMP_INVALID: {path.name}")
    if not frame["time"].is_monotonic_increasing or frame["time"].duplicated().any():
        raise HistoricalReplayError(f"TIMESTAMP_ORDER_INVALID: {path.name}")

    for column in REQUIRED_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    values = frame.loc[:, REQUIRED_COLUMNS[1:]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise HistoricalReplayError(f"NONFINITE_OHLC: {path.name}")
    high = frame["high"].to_numpy(float)
    low = frame["low"].to_numpy(float)
    open_ = frame["open"].to_numpy(float)
    close = frame["close"].to_numpy(float)
    if ((high < low) | (open_ < low) | (open_ > high) | (close < low) | (close > high)).any():
        raise HistoricalReplayError(f"OHLC_INVARIANT_INVALID: {path.name}")

    content = path.read_bytes()
    return frame.reset_index(drop=True), {
        "timeframe": timeframe,
        "path": str(path),
        "rows_before_filter": int(len(frame)),
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": int(len(content)),
        "timestamp_field": "time",
        "timezone_policy": "naive CSV timestamps interpreted as UTC",
        "row_repair": "none; invalid ordering/duplicates/OHLC fail closed",
    }


def _timestamp(value: Any, label: str) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def _apply_window(
    frame: pd.DataFrame,
    *,
    start: Any | None,
    end: Any | None,
    name: str,
) -> pd.DataFrame:
    if start is None and end is None:
        return frame
    start_ts = _timestamp(start, "start") if start is not None else None
    end_ts = _timestamp(end, "end") if end is not None else None
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise HistoricalReplayError("WINDOW_INVALID: start is after end")
    mask = pd.Series(True, index=frame.index)
    if start_ts is not None:
        mask &= frame["time"] >= start_ts
    if end_ts is not None:
        mask &= frame["time"] <= end_ts
    selected = frame.loc[mask].reset_index(drop=True)
    if selected.empty:
        raise HistoricalReplayError(f"SOURCE_EMPTY_AFTER_WINDOW: {name}")
    return selected


def _load_historical_frames(
    dataset_dir: Path,
    *,
    start: Any | None = None,
    end: Any | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, dict[str, Any]]]:
    paths = _source_boundary(dataset_dir)
    frames: dict[str, pd.DataFrame] = {}
    evidence: dict[str, dict[str, Any]] = {}
    for timeframe in TIMEFRAMES:
        frame, info = _read_csv(paths[timeframe], timeframe)
        selected = _apply_window(frame, start=start, end=end, name=timeframe)
        info["rows_after_filter"] = int(len(selected))
        info["window_start"] = selected["time"].iloc[0].isoformat()
        info["window_end"] = selected["time"].iloc[-1].isoformat()
        frames[timeframe] = selected
        evidence[timeframe] = info
    return frames, evidence


def _git_value(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    value = result.stdout.strip()
    return value or "UNKNOWN"


def _generator_evidence() -> dict[str, str]:
    status = _git_value("status", "--porcelain", "--untracked-files=all")
    return {
        "script": "scripts/lab/experiments/ai_outcome_historical_replay.py",
        "commit": _git_value("rev-parse", "HEAD"),
        "branch": _git_value("branch", "--show-current"),
        "worktree_state": "CLEAN" if status == "" else "DIRTY",
    }


def _replay_config(*, full_mtf: bool, horizon_bars: int) -> ReplayConfig:
    return ReplayConfig(
        symbol="EURUSD",
        timeframe="H1",
        timeframes=TIMEFRAMES,
        execution_tf="H1",
        htf_timeframe="H4",
        use_multitf_context=full_mtf,
        outcome=OutcomeConfig(horizon_bars=horizon_bars),
    )


def _prefix_signature(signal: Mapping[str, Any]) -> str:
    """Canonical causal signal view, excluding run-local object identifiers."""

    view = {
        "decision_time": signal.get("decision_time"),
        "direction": signal.get("direction"),
        "features_at_t": signal.get("features_at_t"),
    }
    return json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _verify_full_prefix(
    frames: dict[str, pd.DataFrame],
    full_payload: dict[str, Any],
    *,
    full_mtf: bool,
    horizon_bars: int,
) -> dict[str, Any]:
    """Prove that future bars do not rewrite earlier replay signals."""

    main = frames["H1"]
    full_signals = full_payload.get("signals")
    if not isinstance(full_signals, list):
        return {"prefix_matches_full": False, "status": "BLOCKED", "reason": "SIGNALS_MISSING"}
    cuts: list[dict[str, Any]] = []
    for percent in (10, 25, 50, 75, 90):
        cutoff_index = max(1, int(len(main) * percent / 100) - 1)
        cutoff = main.iloc[cutoff_index]["time"]
        prefix_frames = {
            tf: frame[frame["time"] <= cutoff].reset_index(drop=True)
            for tf, frame in frames.items()
        }
        if any(frame.empty for frame in prefix_frames.values()):
            cuts.append({"percent": percent, "status": "BLOCKED", "reason": "PREFIX_FRAME_EMPTY"})
            continue
        prefix = run_visual_replay(
            prefix_frames,
            _replay_config(full_mtf=full_mtf, horizon_bars=horizon_bars),
        ).to_dict()
        full_at_cut = [
            item for item in full_signals
            if isinstance(item, Mapping) and item.get("decision_time") is not None
            and item["decision_time"] <= cutoff.isoformat()
        ]
        prefix_signals = prefix.get("signals") or []
        left = [_prefix_signature(item) for item in full_at_cut if isinstance(item, Mapping)]
        right = [_prefix_signature(item) for item in prefix_signals if isinstance(item, Mapping)]
        match = left == right
        cuts.append({
            "percent": percent,
            "cutoff_time": cutoff.isoformat(),
            "full_signals": len(left),
            "prefix_signals": len(right),
            "status": "PASS" if match else "BLOCKED",
        })
    passed = bool(cuts) and all(item.get("status") == "PASS" for item in cuts)
    return {
        "prefix_matches_full": passed,
        "status": "PASS" if passed else "BLOCKED",
        "cuts": cuts,
        "comparison": "causal signal fields by decision_time; ordinal signal_index excluded",
    }


def build_historical_replay(
    *,
    dataset_dir: Path = DATASET_DIR,
    start: Any | None = None,
    end: Any | None = None,
    full_mtf: bool = True,
    horizon_bars: int = HISTORICAL_HORIZON_BARS,
    verify_prefix: bool = False,
) -> dict[str, Any]:
    """Build the observational H1 artifact from the closed Dukascopy source."""

    if isinstance(horizon_bars, bool) or not isinstance(horizon_bars, int) or horizon_bars < 1:
        raise HistoricalReplayError("HORIZON_INVALID: horizon_bars must be positive")
    frames, source_files = _load_historical_frames(dataset_dir, start=start, end=end)
    config = _replay_config(full_mtf=full_mtf, horizon_bars=horizon_bars)
    artifact = run_visual_replay(frames, config)
    payload = artifact.to_dict()
    generator = _generator_evidence()
    provenance = {
        "status": "BLOCKED",
        "provider": "Dukascopy",
        "dataset_id": "eurusd_dukascopy_20y",
        "venue": "spot/OTC",
        "symbol": "EURUSD",
        "instrument": "EURUSD spot bid",
        "contract_or_continuous_policy": "spot FX; no futures contract or rollover",
        "rollover_rule": "not applicable",
        "license_and_permitted_use": "UNKNOWN",
        "acquired_at_utc": None,
        "source_documentation_refs": [
            "datasets/eurusd_dukascopy_20y/README.md",
        ],
        "request_parameters": "not read from a sidecar; CSV-only input boundary",
        "volume_semantics": "UNAVAILABLE",
        "open_interest_semantics": "UNAVAILABLE",
        "files": source_files,
        "blocking_reasons": [
            "SOURCE_LICENSE_OR_PERMITTED_USE_UNKNOWN",
            "ACQUISITION_EXECUTION_LOG_NOT_ESTABLISHED_BY_CSV_BYTES",
            "GENERATOR_WORKTREE_NOT_CLEAN" if generator["worktree_state"] != "CLEAN" else None,
        ],
    }
    provenance["blocking_reasons"] = [
        reason for reason in provenance["blocking_reasons"] if reason is not None
    ]
    metadata = dict(payload.get("metadata") or {})
    metadata.update({
        "status": "BLOCKED",
        "causal": True,
        "can_trade": False,
        "promotion_authorized": False,
        "generator_commit": generator["commit"],
        "generator": generator,
        "provenance": provenance,
        "outcome": {
            "label_contract": f"label_end_{horizon_bars}",
            "horizon_bars": horizon_bars,
            "entry_bar_excluded_from_scan": True,
            "scan_starts_at_entry_plus_one": True,
        },
        "causality": {
            "decision_time_policy": "closed bars only; all MTF context timestamps <= H1 decision time",
            "structure_publication": "canonical engine event publication time",
            "trade_outcome": "engine.sequential_outcome.resolve_outcome scans only future H1 bars",
            "future_features_exported": False,
            "source_rows_repaired": False,
        },
        "source_timeframes": list(TIMEFRAMES),
        "full_mtf_context": bool(full_mtf),
        "full_prefix": (
            _verify_full_prefix(frames, payload, full_mtf=full_mtf, horizon_bars=horizon_bars)
            if verify_prefix
            else {"prefix_matches_full": False, "status": "NOT_RUN"}
        ),
        "funnel_episodes": {
            "status": "BLOCKED",
            "derived": False,
            "reason": (
                "The public replay result has rendered events and trades but does not expose "
                "the projection_at(T)/build_setups_at lineage and features_at_t required by "
                "Episodes/Funnel; no synthetic episodes or features were invented."
            ),
            "required_linkage": [
                "engine.setup_builder.build_setups_at",
                "MarketState.projection_at(T)",
                "features_at_t",
            ],
        },
    })
    payload.update({
        "status": "BLOCKED",
        "causal": True,
        "can_trade": False,
        "promotion_authorized": False,
        "generator_commit": generator["commit"],
        "provenance": provenance,
        "metadata": metadata,
    })
    validate_visual_backtest(payload)
    return payload


def export_historical_replay(
    output: Path,
    *,
    dataset_dir: Path = DATASET_DIR,
    start: Any | None = None,
    end: Any | None = None,
    full_mtf: bool = True,
    horizon_bars: int = HISTORICAL_HORIZON_BARS,
    verify_prefix: bool = False,
) -> dict[str, Any]:
    """Build and atomically write one observational JSON artifact."""

    payload = build_historical_replay(
        dataset_dir=dataset_dir, start=start, end=end,
        full_mtf=full_mtf, horizon_bars=horizon_bars, verify_prefix=verify_prefix,
    )
    write_visual_backtest(payload, Path(output))
    return payload


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", help="inclusive UTC window start")
    parser.add_argument("--end", help="inclusive UTC window end")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "backtest" / "visual_backtest.json",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use the causal H4 projection path without rebuilding the full MTF context per bar.",
    )
    parser.add_argument("--horizon-bars", type=int, default=HISTORICAL_HORIZON_BARS)
    parser.add_argument(
        "--verify-prefix",
        action="store_true",
        help="Run FULL/PREFIX replay comparisons at 10/25/50/75/90 percent cuts.",
    )
    args = parser.parse_args(argv)
    try:
        payload = export_historical_replay(
            args.output,
            start=args.start,
            end=args.end,
            full_mtf=not args.fast,
            horizon_bars=args.horizon_bars,
            verify_prefix=args.verify_prefix,
        )
    except (HistoricalReplayError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"[AI_OUTCOME_REPLAY][BLOCKED] {exc}", file=sys.stderr)
        return 2
    print(
        f"historical replay exported: {args.output} "
        f"candles={len(payload['candles'])} trades={len(payload['trades'])} "
        f"status={payload['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
