"""Fase 1: panel causal de displacement (solo lectura, sin entrenamiento).

Materializa contrastes derivados de OHLC, separados en geometria, episodio y
outcome.  Las dos rutas historicas de detector se conservan como evidencia,
no se mezclan ni se declara una de ellas como verdad.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from detectors.displacement import DisplacementConfig, detect_displacement
from engine.detectors.displacement import (
    DisplacementConfig as EngineConfig,
    detect_displacement as detect_engine,
)


OUT = ROOT / "reports/ict_temporal_v1/helix/displacement_v1"
SOURCE = ROOT / "data/raw/EURUSD/EURUSD_M15.parquet"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def panel(frame: pd.DataFrame) -> pd.DataFrame:
    x = frame.sort_values("time").reset_index(drop=True).copy()
    # All fields below are available at the close of row i; no future row is used.
    rng = (x.high - x.low).clip(lower=0.0)
    body = (x.close - x.open).abs()
    ratio = body.div(rng.replace(0, np.nan))
    prior_mean = rng.shift(1).rolling(14, min_periods=14).mean()
    prior_high = x.high.shift(1).rolling(2, min_periods=2).max()
    prior_low = x.low.shift(1).rolling(2, min_periods=2).min()
    direction = np.select([x.close > x.open, x.close < x.open], ["UP", "DOWN"], "NONE")
    geometry = (ratio >= 0.60) & (body >= 1.5e-4)
    episode = geometry & (((x.close > prior_high) & (direction == "UP")) | ((x.close < prior_low) & (direction == "DOWN")))
    # Outcome is deliberately a separate, future-only audit field; never an input.
    future_high = x.high.shift(-1).rolling(4, min_periods=4).max().shift(-3)
    future_low = x.low.shift(-1).rolling(4, min_periods=4).min().shift(-3)
    outcome_up = future_high >= x.close + body
    outcome_down = future_low <= x.close - body
    eng = detect_engine(x, EngineConfig())
    legacy = detect_displacement(x, DisplacementConfig())
    eng_map = eng.set_index("time") if not eng.empty else pd.DataFrame(index=x.time)
    leg = legacy.set_index("time")
    engine_flag = x.time.map(eng_map.get("displacement_bullish", pd.Series(dtype=bool))).fillna(False).astype(bool) | x.time.map(eng_map.get("displacement_bearish", pd.Series(dtype=bool))).fillna(False).astype(bool)
    leg_map = legacy.set_index("time") if not legacy.empty and "time" in legacy else pd.DataFrame(index=x.time)
    range_flag = x.time.map(leg_map.get("displacement_bullish", pd.Series(dtype=bool))).fillna(False).astype(bool) | x.time.map(leg_map.get("displacement_bearish", pd.Series(dtype=bool))).fillna(False).astype(bool)
    # Both detectors are aligned by timestamp; neither gets future rows.
    return pd.DataFrame({
        "time": x.time.astype(str), "geometry_body_to_range": ratio,
        "geometry_direction": direction, "geometry_positive": geometry,
        "episode_breakout_positive": episode, "episode_available": prior_high.notna() & prior_low.notna(),
        "outcome_up_4x_body": outcome_up.where(future_high.notna()), "outcome_down_4x_body": outcome_down.where(future_low.notna()),
        "engine_detector": engine_flag, "range_detector": range_flag,
        "reconciliation": np.select([engine_flag & range_flag, engine_flag, range_flag], ["AGREE", "ENGINE_ONLY", "RANGE_ONLY"], "NEITHER"),
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=SOURCE)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(args.source)
    required = {"time", "open", "high", "low", "close"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    p = panel(frame)
    panel_path = args.out / "displacement_phase1_row_evidence.parquet"
    p.to_parquet(panel_path, index=False)
    counts = p.reconciliation.value_counts().to_dict()
    report = {
        "status": "PASS", "phase": "1", "training": False, "can_trade": False,
        "source": str(args.source), "source_sha256": sha256(args.source), "source_rows": len(frame),
        "panel_rows": len(p), "time_min": p.time.min(), "time_max": p.time.max(),
        "geometry_positive": int(p.geometry_positive.sum()), "episode_positive": int(p.episode_breakout_positive.sum()),
        "outcome_observable_rows": int(p.outcome_up_4x_body.notna().sum()),
        "reconciliation_counts": counts,
        "limitations": ["outcome is audit-only and future-derived", "detectors are distinct proxies", "no source data altered"],
    }
    (args.out / "coverage_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    manifest = {"manifest": "DISPLACEMENT_PHASE1_V1", "generator": str(Path(__file__)), "git_commit": commit,
                "python": platform.python_version(), "inputs": [{"path": str(args.source), "sha256": sha256(args.source), "rows": len(frame)}],
                "outputs": [{"path": str(panel_path), "sha256": sha256(panel_path), "rows": len(p)}, {"path": str(args.out / "coverage_report.json"), "sha256": sha256(args.out / "coverage_report.json")}],
                "contract": {"m15_closed_only": True, "full_prefix": True, "can_trade": False, "training": False}}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    (args.out / "coverage_report.md").write_text("# Displacement phase 1\n\n" + json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
