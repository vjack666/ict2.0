"""Canonical causal ICT Fair Value Gap detector."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from engine.market_object import MarketObject, ObjectState, ObjectType, Role


@dataclass(frozen=True)
class _Candle:
    index: int
    time: Any
    high: float
    low: float


def _as_candles(rows: Iterable[Mapping[str, Any]]) -> list[_Candle]:
    candles: list[_Candle] = []
    for i, row in enumerate(rows):
        candles.append(
            _Candle(
                index=i,
                time=row.get("time", row.get("timestamp")),
                high=float(row["high"]),
                low=float(row["low"]),
            )
        )
    return candles


def detect_fvg(
    rows: Iterable[Mapping[str, Any]],
    timeframe: str = "H1",
    symbol: str = "",
) -> list[MarketObject]:
    """Detect 3-candle bullish/bearish FVGs using information through candle i.

    The gap is *not* tradable before the third candle closes. No row after i is
    inspected, which makes the detector safe for sequential backtests.
    """
    candles = _as_candles(rows)
    out: list[MarketObject] = []
    for i in range(2, len(candles)):
        first = candles[i - 2]
        third = candles[i]

        if third.low > first.high:
            out.append(
                MarketObject(
                    id=f"FVG_{timeframe}_{i}_BULL",
                    symbol=symbol,
                    type=ObjectType.FVG,
                    origin_tf=timeframe,
                    role=Role.REFINEMENT,
                    direction=1,
                    zone_high=third.low,
                    zone_low=first.high,
                    creation_time=third.time,
                    state=ObjectState.ACTIVE,
                    bar_index=i,
                    bar_time=third.time,
                    candidate_bar=i - 2,
                    candidate_time=first.time,
                    confirmation_bar=i,
                    confirmation_time=third.time,
                    tradable_bar=i,
                    tradable_time=third.time,
                    mitigation_level=first.high,
                    meta={"pattern": "3C_FVG", "side": "bullish", "middle_bar": i - 1},
                )
            )
        elif third.high < first.low:
            out.append(
                MarketObject(
                    id=f"FVG_{timeframe}_{i}_BEAR",
                    symbol=symbol,
                    type=ObjectType.FVG,
                    origin_tf=timeframe,
                    role=Role.REFINEMENT,
                    direction=-1,
                    zone_high=first.low,
                    zone_low=third.high,
                    creation_time=third.time,
                    state=ObjectState.ACTIVE,
                    bar_index=i,
                    bar_time=third.time,
                    candidate_bar=i - 2,
                    candidate_time=first.time,
                    confirmation_bar=i,
                    confirmation_time=third.time,
                    tradable_bar=i,
                    tradable_time=third.time,
                    mitigation_level=third.high,
                    meta={"pattern": "3C_FVG", "side": "bearish", "middle_bar": i - 1},
                )
            )
    return out
