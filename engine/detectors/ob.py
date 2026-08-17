"""Canonical ICT Order Block detector from the project thesis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from engine.market_object import MarketObject, ObjectState, ObjectType, Role


@dataclass(frozen=True)
class _Candle:
    index: int
    time: Any
    open: float
    high: float
    low: float
    close: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        return 0.0 if self.range <= 0 else self.body / self.range

    @property
    def bullish(self) -> bool:
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        return self.close < self.open


def _as_candles(rows: Iterable[Mapping[str, Any]]) -> list[_Candle]:
    return [
        _Candle(
            index=i,
            time=row.get("time", row.get("timestamp")),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
        )
        for i, row in enumerate(rows)
    ]


def detect_order_blocks(
    rows: Iterable[Mapping[str, Any]],
    timeframe: str = "H1",
    symbol: str = "",
    min_body_ratio: float = 0.60,
) -> list[MarketObject]:
    """Detect OBs using the thesis' two-candle footprint + follow-through rule.

    Bullish OB: bearish footprint candle followed by a closed bullish
    follow-through whose close breaks the footprint high.
    Bearish OB: bullish footprint candle followed by a closed bearish
    follow-through whose close breaks the footprint low.

    A signal is tradable only at the follow-through close, never on the
    footprint candle itself. No row after the follow-through is inspected.
    """
    if not 0.0 <= min_body_ratio <= 1.0:
        raise ValueError("min_body_ratio debe estar entre 0 y 1")

    candles = _as_candles(rows)
    out: list[MarketObject] = []
    for i in range(1, len(candles)):
        footprint = candles[i - 1]
        followthrough = candles[i]

        if footprint.bearish and footprint.body_ratio >= min_body_ratio and followthrough.bullish and followthrough.close > footprint.high:
            out.append(
                MarketObject(
                    id=f"OB_{timeframe}_{i}_BULL",
                    symbol=symbol,
                    type=ObjectType.ORDER_BLOCK,
                    origin_tf=timeframe,
                    role=Role.REFINEMENT,
                    direction=1,
                    zone_high=footprint.high,
                    zone_low=footprint.low,
                    creation_time=footprint.time,
                    state=ObjectState.ACTIVE,
                    bar_index=i,
                    bar_time=followthrough.time,
                    candidate_bar=i - 1,
                    candidate_time=footprint.time,
                    confirmation_bar=i,
                    confirmation_time=followthrough.time,
                    tradable_bar=i,
                    tradable_time=followthrough.time,
                    quality_score=min(1.0, footprint.body_ratio),
                    meta={
                        "pattern": "OB_FOOTPRINT_FOLLOWTHROUGH",
                        "side": "bullish",
                        "source_candle": i - 1,
                        "followthrough": i,
                        "body_ratio": footprint.body_ratio,
                    },
                )
            )
        elif footprint.bullish and footprint.body_ratio >= min_body_ratio and followthrough.bearish and followthrough.close < footprint.low:
            out.append(
                MarketObject(
                    id=f"OB_{timeframe}_{i}_BEAR",
                    symbol=symbol,
                    type=ObjectType.ORDER_BLOCK,
                    origin_tf=timeframe,
                    role=Role.REFINEMENT,
                    direction=-1,
                    zone_high=footprint.high,
                    zone_low=footprint.low,
                    creation_time=footprint.time,
                    state=ObjectState.ACTIVE,
                    bar_index=i,
                    bar_time=followthrough.time,
                    candidate_bar=i - 1,
                    candidate_time=footprint.time,
                    confirmation_bar=i,
                    confirmation_time=followthrough.time,
                    tradable_bar=i,
                    tradable_time=followthrough.time,
                    quality_score=min(1.0, footprint.body_ratio),
                    meta={
                        "pattern": "OB_FOOTPRINT_FOLLOWTHROUGH",
                        "side": "bearish",
                        "source_candle": i - 1,
                        "followthrough": i,
                        "body_ratio": footprint.body_ratio,
                    },
                )
            )
    return out
