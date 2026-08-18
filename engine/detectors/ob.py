"""Canonical ICT Order Block detector."""
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
    def body_ratio(self) -> float:
        r = self.high - self.low
        return 0.0 if r <= 0 else abs(self.close - self.open) / r
    @property
    def bullish(self) -> bool: return self.close > self.open
    @property
    def bearish(self) -> bool: return self.close < self.open

def _as_candles(rows: Iterable[Mapping[str, Any]]) -> list[_Candle]:
    return [_Candle(i, r.get("time", r.get("timestamp")), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])) for i, r in enumerate(rows)]

def detect_order_blocks(rows: Iterable[Mapping[str, Any]], timeframe: str = "H1", symbol: str = "", min_body_ratio: float = 0.60) -> list[MarketObject]:
    """Detect OB only after the opposite footprint candle has a closed follow-through."""
    if not 0.0 <= min_body_ratio <= 1.0:
        raise ValueError("min_body_ratio debe estar entre 0 y 1")
    candles = _as_candles(rows)
    out: list[MarketObject] = []
    for i in range(1, len(candles)):
        fp, ft = candles[i - 1], candles[i]
        common = dict(symbol=symbol, type=ObjectType.ORDER_BLOCK, origin_tf=timeframe, role=Role.REFINEMENT,
                      zone_high=fp.high, zone_low=fp.low, creation_time=fp.time, state=ObjectState.ACTIVE,
                      bar_index=i, bar_time=ft.time, candidate_bar=i-1, candidate_time=fp.time,
                      confirmation_bar=i, confirmation_time=ft.time, tradable_bar=i, tradable_time=ft.time,
                      quality_score=min(1.0, fp.body_ratio), meta={"pattern":"OB_FOOTPRINT_FOLLOWTHROUGH","source_candle":i-1,"followthrough":i,"body_ratio":fp.body_ratio})
        if fp.bearish and fp.body_ratio >= min_body_ratio and ft.bullish and ft.close > fp.high:
            out.append(MarketObject(id=f"OB_{timeframe}_{i}_BULL", direction=1, **common))
        elif fp.bullish and fp.body_ratio >= min_body_ratio and ft.bearish and ft.close < fp.low:
            out.append(MarketObject(id=f"OB_{timeframe}_{i}_BEAR", direction=-1, **common))
    return out
