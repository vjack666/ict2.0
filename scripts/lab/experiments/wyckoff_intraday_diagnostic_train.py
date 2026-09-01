"""Primer entrenamiento diagnóstico Wyckoff H1 -> M15 + ICT.

Construye un JSONL causal desde M15 histórico de Dukascopy, con contexto H1,
eventos Wyckoff en ambas capas y confirmaciones ICT en M15.  Reutiliza el
clasificador softmax determinista existente mediante su perfil de features
intradía; no crea otro registry, no usa MT5 y nunca concede autoridad de
trading. El resultado es DIAGNOSTIC_ONLY, no certificación científica.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_features import build_features
from engine.Wyckoff.adapter import build_wyckoff_snapshot
from runtime.ai_learning.diagnostic_training import (
    run_diagnostic_training,
    write_diagnostic_artifact,
)
from runtime.ai_learning.outcome_classifier import INTRADAY_FEATURE_NAMES


DEFAULT_DATA = ROOT / "datasets" / "eurusd_dukascopy_intraday_2006_2010" / "raw_monthly"
DEFAULT_H1 = ROOT / "datasets" / "eurusd_dukascopy_20y" / "EURUSD_H1.csv"
DEFAULT_JSONL = ROOT / "reports" / "audits" / "experiments" / "ai" / "wyckoff_intraday_2006_2010.jsonl"
DEFAULT_ARTIFACT = ROOT / "reports" / "audits" / "experiments" / "ai" / "wyckoff_intraday_2006_2010_train.json"
TARGET = "label_end_12"
HORIZON = 12  # M15 bars: 3 hours
LOOKBACK = 40


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _iso(value: pd.Timestamp) -> str:
    return value.tz_convert("UTC").isoformat()


def _load_m15(root: Path) -> pd.DataFrame:
    files = sorted(root.glob("*/eurusd-m15-bid-*.csv"))
    if not files:
        raise SystemExit(f"No hay M15 mensuales en {root}")
    frames = []
    for path in files:
        frame = pd.read_csv(path)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required.difference(frame.columns)
        if missing:
            raise SystemExit(f"{path}: faltan columnas {sorted(missing)}")
        frame = frame.rename(columns={"volume": "tick_volume"})
        frame["time"] = pd.to_datetime(frame.pop("timestamp"), unit="ms", utc=True)
        frames.append(frame[["time", "open", "high", "low", "close", "tick_volume"]])
    result = pd.concat(frames, ignore_index=True).sort_values("time").reset_index(drop=True)
    if result["time"].duplicated().any():
        raise SystemExit("M15 contiene timestamps duplicados; no se deduplican automáticamente")
    if not result["time"].is_monotonic_increasing:
        raise SystemExit("M15 no es monotónico")
    bad = (
        (result["high"] < result[["open", "close", "low"]].max(axis=1))
        | (result["low"] > result[["open", "close", "high"]].min(axis=1))
        | (result[["open", "high", "low", "close", "tick_volume"]].isna().any(axis=1))
        | (result["tick_volume"] < 0)
    )
    if bad.any():
        raise SystemExit(f"M15 contiene {int(bad.sum())} filas OHLC/volumen inválidas")
    return result


def _load_h1(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"time", "open", "high", "low", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise SystemExit(f"{path}: faltan columnas {sorted(missing)}")
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.sort_values("time").reset_index(drop=True)
    return frame[["time", "open", "high", "low", "close"]]


def _direction(row: pd.Series) -> int:
    for key in ("choch_dir", "bos_dir"):
        value = int(row.get(key, 0) or 0)
        if value:
            return value
    trend = str(row.get("trend", "")).upper()
    return 1 if trend == "BULLISH" else -1 if trend == "BEARISH" else 0


def _ict_payload(row: pd.Series) -> dict[str, bool]:
    return {
        "bos_bullish": int(row.get("bos_dir", 0) or 0) == 1,
        "bos_bearish": int(row.get("bos_dir", 0) or 0) == -1,
        "choch_bullish": int(row.get("choch_dir", 0) or 0) == 1,
        "choch_bearish": int(row.get("choch_dir", 0) or 0) == -1,
        "displacement_bullish": bool(row.get("displacement_bullish", False)),
        "displacement_bearish": bool(row.get("displacement_bearish", False)),
        "fvg_bullish": bool(row.get("fvg_bullish", False)),
        "fvg_bearish": bool(row.get("fvg_bearish", False)),
        "sweep_up": bool(row.get("liquidity_sweep_up", False)),
        "sweep_down": bool(row.get("liquidity_sweep_down", False)),
    }


def _phase_alignment(h1_trend: str, direction: int) -> str:
    if direction == 0 or h1_trend not in {"BULLISH", "BEARISH"}:
        return "NEUTRAL"
    return "ALIGNED" if (h1_trend == "BULLISH") == (direction == 1) else "AGAINST"


def _label(m15: pd.DataFrame, index: int, direction: int) -> str:
    current = float(m15.iloc[index]["close"])
    future = float(m15.iloc[index + HORIZON]["close"])
    prior = m15.iloc[max(0, index - 20):index]
    scale = float((prior["high"] - prior["low"]).median()) if len(prior) else 0.0
    scale = max(scale, 1e-9)
    signed_move = direction * (future - current)
    if signed_move >= scale:
        return "continuation"
    if signed_move <= -scale:
        return "reversal"
    return "failure"


def _wyckoff_layer(snapshot: Any, tf: str) -> dict[str, Any]:
    payload = snapshot.layers.get(tf, {}) if hasattr(snapshot, "layers") else {}
    return {
        "phase": str(payload.get("phase", "UNKNOWN")),
        "events": [
            {"event_type": str(event.get("event_type", "UNKNOWN"))}
            for event in payload.get("events", [])
            if isinstance(event, dict)
        ],
    }


def build_rows(m15: pd.DataFrame, h1: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    m15_features = build_features(m15.copy(), include_liquidity_zones=False)
    h1_features = build_features(h1.copy(), include_liquidity_zones=False)
    h1_times = h1_features["time"].astype("int64").to_numpy()
    rows: list[dict[str, Any]] = []
    for index in range(LOOKBACK, len(m15_features) - HORIZON):
        row = m15_features.iloc[index]
        direction = _direction(row)
        ict = _ict_payload(row)
        if direction == 0 or not any(ict.values()):
            continue
        decision_time = row["time"]
        h1_index = int(h1_times.searchsorted(decision_time.value, side="right") - 1)
        if h1_index < LOOKBACK:
            continue
        h1_window = h1_features.iloc[h1_index - LOOKBACK + 1:h1_index + 1].copy()
        m15_window = m15_features.iloc[index - LOOKBACK + 1:index + 1].copy()
        h1_trend = str(h1_features.iloc[h1_index].get("trend", "UNKNOWN")).upper()
        snapshot = build_wyckoff_snapshot(
            {"H1": h1_window, "M15": m15_window},
            decision_time,
            ict_direction=direction,
            authority_tf="H1",
            layers=("H1", "M15"),
        )
        h1_layer = _wyckoff_layer(snapshot, "H1")
        m15_layer = _wyckoff_layer(snapshot, "M15")
        sequence = ["STRUCTURE"]
        if ict["sweep_up"] or ict["sweep_down"]:
            sequence.append("SWEEP")
        if ict["displacement_bullish"] or ict["displacement_bearish"]:
            sequence.append("DISPLACEMENT")
        if ict["fvg_bullish"] or ict["fvg_bearish"]:
            sequence.append("FVG")
        event_time = _iso(decision_time)
        rows.append({
            "episode_id": f"WYCKOFF_INTRADAY_2006_2010_M15_{index:06d}",
            "event_time": event_time,
            "label_available_time": _iso(m15_features.iloc[index + HORIZON]["time"]),
            "direction": direction,
            "sequence_depth": len(sequence),
            "features_at_t": {
                "context_inputs": {
                    "sequence_direction": direction,
                    "context_bucket": _phase_alignment(h1_trend, direction),
                    "h1_alignment": _phase_alignment(h1_trend, direction),
                    "d1_bias": "UNKNOWN",
                    "h4_location": "UNKNOWN",
                },
                "sequence": sequence,
                "intraday": {
                    "ict_m15": ict,
                    "wyckoff": {"H1": h1_layer, "M15": m15_layer},
                },
            },
            TARGET: _label(m15_features, index, direction),
            "can_trade": False,
        })
    if not rows:
        raise SystemExit("No se generaron candidatos intradía con la configuración congelada")
    rows.sort(key=lambda item: (item["event_time"], item["episode_id"]))
    return rows, {
        "m15_rows": len(m15),
        "h1_rows": len(h1),
        "candidate_rows": len(rows),
        "date_min": rows[0]["event_time"],
        "date_max": rows[-1]["event_time"],
        "horizon_m15_bars": HORIZON,
        "horizon_description": "3 hours after decision_time",
        "label_rule": "signed close move versus prior 20-bar median range: >=1 range continuation, <=-1 range reversal, else failure",
        "feature_profile": "INTRADAY_FEATURE_NAMES",
        "can_trade": False,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    raw = b"\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() for row in rows) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--h1", type=Path, default=DEFAULT_H1)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()
    m15 = _load_m15(args.data_root)
    h1 = _load_h1(args.h1)
    start = pd.Timestamp("2006-01-01", tz="UTC")
    end = pd.Timestamp("2011-01-01", tz="UTC")
    m15 = m15.loc[(m15["time"] >= start) & (m15["time"] < end)].reset_index(drop=True)
    h1 = h1.loc[(h1["time"] >= start) & (h1["time"] < end)].reset_index(drop=True)
    rows, summary = build_rows(m15, h1)
    raw_hash = _write_jsonl(args.jsonl, rows)
    diagnostic = run_diagnostic_training(
        args.jsonl,
        target=TARGET,
        seed=20260831,
        code_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        feature_names=INTRADAY_FEATURE_NAMES,
    )
    diagnostic["intraday_summary"] = summary
    diagnostic["intraday_summary"]["jsonl_sha256"] = raw_hash
    write_diagnostic_artifact(diagnostic, args.artifact)
    print(json.dumps({
        "jsonl": _relative(args.jsonl),
        "artifact": _relative(args.artifact),
        "rows": len(rows),
        "classes": {label: sum(row[TARGET] == label for row in rows) for label in ("continuation", "reversal", "failure")},
        "status": diagnostic["status"],
        "fit_executed": diagnostic["fit_executed"],
        "metrics": diagnostic.get("metrics"),
        "can_trade": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
