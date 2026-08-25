"""Schema and JSON serialization for the new visual-backtest artifact."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCHEMA_VERSION = "1.0"


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy values into deterministic JSON-compatible values."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (float, np.floating)):
        return None if not np.isfinite(float(value)) else float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray, pd.Series)):
        return [json_safe(v) for v in list(value)]
    if pd.isna(value):
        return None
    return str(value)


@dataclass
class VisualBacktest:
    """Complete artifact consumed by the visualizer."""

    symbol: str
    timeframe: str
    candles: list[dict[str, Any]]
    events: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candles": self.candles,
            "events": self.events,
            "trades": self.trades,
            "metadata": self.metadata,
        }
        return json_safe(payload)


def validate_visual_backtest(payload: dict[str, Any]) -> None:
    """Fail closed when an exporter emits an incomplete or non-causal artifact."""

    required = {"schema_version", "symbol", "timeframe", "candles", "events", "trades"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"visual_backtest missing keys: {sorted(missing)}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported visual_backtest schema: {payload['schema_version']}")

    candles = payload["candles"]
    if not isinstance(candles, list):
        raise ValueError("candles must be a list")
    for expected, candle in enumerate(candles):
        if candle.get("index") != expected:
            raise ValueError("candles must have contiguous zero-based indexes")

    event_ids: set[str] = set()
    for event in payload["events"]:
        event_id = str(event.get("id", ""))
        if not event_id or event_id in event_ids:
            raise ValueError(f"invalid or duplicate event id: {event_id!r}")
        event_ids.add(event_id)
        index = int(event["index"])
        confirmed = int(event["confirmed_index"])
        if not 0 <= index < len(candles) or not 0 <= confirmed < len(candles):
            raise ValueError(f"event outside candle range: {event_id}")
        if confirmed < index:
            raise ValueError(f"event confirmation precedes event index: {event_id}")
        parent_id = event.get("parent_id")
        if parent_id is not None and parent_id not in event_ids:
            raise ValueError(f"event parent must precede child: {event_id}")

    for trade in payload["trades"]:
        entry_index = int(trade["entry_index"])
        if not 0 <= entry_index < len(candles):
            raise ValueError("trade entry outside candle range")
        exit_index = trade.get("exit_index")
        if exit_index is not None and int(exit_index) < entry_index:
            raise ValueError("trade exit precedes entry")


def write_visual_backtest(payload: dict[str, Any], output: Path) -> None:
    """Write a validated artifact atomically."""

    import json

    validate_visual_backtest(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
