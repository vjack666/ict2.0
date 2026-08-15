"""F5 (parcial) — Medición de demostración del sesgo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.medicion.types import SesgoRow


@dataclass(frozen=True)
class AlignmentStat:
    category: str
    total: int
    aligned: int
    pct: float


def _direction(delta: float) -> str:
    if delta > 0:
        return "BULLISH"
    if delta < 0:
        return "BEARISH"
    return "NEUTRAL"


def _category(bias) -> str:
    if bias is None:
        return "NO_DISPONIBLE"
    if bias.aligned:
        return "ALIGNED"
    return "PARCIAL"


def build_demo_report(rows: list[SesgoRow], k: int, symbol: str) -> dict:
    stats: dict[str, dict[str, int]] = {}

    for row in rows:
        cat = _category(row.vigente.bias if row.vigente else None)
        bucket = stats.setdefault(cat, {"total": 0, "aligned": 0})
        bucket["total"] += 1

        if row.future_delta is not None and row.vigente is not None:
            expected = row.vigente.bias.direction
            actual = _direction(row.future_delta)
            if expected == actual:
                bucket["aligned"] += 1

    summary = []
    for category in ("ALIGNED", "PARCIAL", "NO_DISPONIBLE"):
        bucket = stats.get(category, {"total": 0, "aligned": 0})
        pct = bucket["aligned"] / bucket["total"] * 100 if bucket["total"] else 0.0
        summary.append(
            AlignmentStat(
                category=category,
                total=bucket["total"],
                aligned=bucket["aligned"],
                pct=pct,
            )
        )

    return {
        "symbol": symbol,
        "k": k,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "summary": [
            {
                "category": s.category,
                "total": s.total,
                "aligned": s.aligned,
                "pct": round(s.pct, 2),
            }
            for s in summary
        ],
    }


def save_demo_report(report: dict, results_root: Path | None = None) -> Path:
    results_root = results_root or Path(__file__).resolve().parents[2] / "results" / "sesgo"
    results_root.mkdir(parents=True, exist_ok=True)
    path = results_root / f"reporte_sesgo_{datetime.utcnow():%Y-%m-%d}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
