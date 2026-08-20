"""Eventos Wyckoff causales sobre un prefijo cerrado."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .types import WyckoffEvent, WyckoffEventType


def _event(tf: str, index: int, row: pd.Series, event_type: WyckoffEventType, detail: dict[str, Any]) -> WyckoffEvent:
    event_time = row.get("time")
    source_ref = f"BAR_{tf}_{index}"
    return WyckoffEvent(
        event_id=f"WYCKOFF_{tf}_{index}_{event_type.value}",
        event_type=event_type,
        tf=tf,
        event_time=event_time,
        source_ref=source_ref,
        evidence_refs=(source_ref,),
        confirmation_status="OBSERVED",
        detail=detail,
    )


def detect_events(frame: pd.DataFrame, *, tf: str, lookback: int = 10) -> tuple[WyckoffEvent, ...]:
    if frame is None or len(frame) < 5:
        return ()
    window = frame.reset_index(drop=True)
    i = len(window) - 1
    row = window.iloc[-1]
    prior = window.iloc[max(0, i - lookback) : i]
    if len(prior) < 3:
        return ()
    support = float(prior["low"].min())
    resistance = float(prior["high"].max())
    high = float(row["high"])
    low = float(row["low"])
    close = float(row["close"])
    open_ = float(row["open"])
    candle_range = max(high - low, 1e-12)
    body_ratio = abs(close - open_) / candle_range
    events: list[WyckoffEvent] = []

    if low < support and close > support:
        events.append(_event(tf, i, row, WyckoffEventType.SPRING, {"support": support, "reclaim": True}))
    if high > resistance and close < resistance:
        events.append(_event(tf, i, row, WyckoffEventType.UPTHRUST, {"resistance": resistance, "reclaim": True}))
    if close > resistance and body_ratio >= 0.6:
        events.append(_event(tf, i, row, WyckoffEventType.SOS, {"resistance": resistance, "body_ratio": round(body_ratio, 6)}))
    if close < support and body_ratio >= 0.6:
        events.append(_event(tf, i, row, WyckoffEventType.SOW, {"support": support, "body_ratio": round(body_ratio, 6)}))

    if len(window) >= 8:
        recent = window.iloc[-8:-1]
        average_range = float((recent["high"] - recent["low"]).mean())
        volume_ratio = None
        if "tick_volume" in window.columns:
            prior_volume = pd.to_numeric(window["tick_volume"].iloc[:-1], errors="coerce").dropna()
            if len(prior_volume) > 1 and float(prior_volume.mean()) > 0:
                volume_ratio = float(row["tick_volume"]) / float(prior_volume.mean())
        if average_range > 0 and candle_range < average_range * 0.8 and close >= support and close <= resistance:
            prior_move = float(recent["close"].iloc[-1]) - float(recent["close"].iloc[0])
            if prior_move > 0 and (volume_ratio is None or volume_ratio < 0.7):
                events.append(_event(tf, i, row, WyckoffEventType.LPS, {"low_volume_test": volume_ratio is not None}))
            elif prior_move < 0 and (volume_ratio is None or volume_ratio < 0.7):
                events.append(_event(tf, i, row, WyckoffEventType.LPSY, {"low_volume_test": volume_ratio is not None}))

    return tuple(events)


__all__ = ["detect_events"]
