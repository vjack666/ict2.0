"""F1 — Reloj vela a vela (corazón del backtest del sesgo)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from ict_backtest.sesgo.config import SesgoConfig


@dataclass(frozen=True)
class VelaCerrada:
    timeframe: str
    timestamp: pd.Timestamp
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class EventoReloj:
    m15_index: int
    m15_timestamp: pd.Timestamp
    tf_closures: list[VelaCerrada]


class RelojSesgo:
    """Iterador vela a vela sobre M15 que detecta cierres HTF.

    No contiene lógica de trading ni de sesgo.
    """

    def __init__(self, df: pd.DataFrame, config: SesgoConfig | None = None) -> None:
        if not isinstance(df.index, pd.DatetimeIndex):
            raise TypeError("df must have a DatetimeIndex")

        self.df = df.sort_index()
        self.config = config or SesgoConfig()
        self._last_bucket: dict[str, int | None] = {tf: None for tf in self.config.aggregation}
        self._buffers: dict[str, list[pd.Series]] = {tf: [] for tf in self.config.aggregation}

    @staticmethod
    def _bucket(ts: pd.Timestamp, timeframe: str) -> int:
        if timeframe == "H1":
            return ts.floor("1h").value
        if timeframe == "H4":
            return ts.floor("4h").value
        if timeframe == "D1":
            return ts.floor("1D").value
        raise ValueError(f"unsupported timeframe: {timeframe}")

    @staticmethod
    def _aggregate(rows: list[pd.Series], timeframe: str) -> VelaCerrada:
        if not rows:
            raise ValueError("cannot aggregate empty bucket")

        ts = rows[-1].name
        if not isinstance(ts, pd.Timestamp):
            raise TypeError("row index must be Timestamp")

        return VelaCerrada(
            timeframe=timeframe,
            timestamp=ts,
            open=float(rows[0]["open"]),
            high=float(max(float(row["high"]) for row in rows)),
            low=float(min(float(row["low"]) for row in rows)),
            close=float(rows[-1]["close"]),
        )

    def _flush(self, timeframe: str) -> VelaCerrada:
        vela = self._aggregate(self._buffers[timeframe], timeframe)
        self._buffers[timeframe] = []
        return vela

    def iter_eventos(self) -> Iterable[EventoReloj]:
        for idx, row in self.df.iterrows():
            if not isinstance(idx, pd.Timestamp):
                continue

            closures: list[VelaCerrada] = []

            for tf in self.config.aggregation:
                bucket = self._bucket(idx, tf)

                if self._last_bucket[tf] is None:
                    self._last_bucket[tf] = bucket
                    self._buffers[tf].append(row)
                    continue

                if bucket != self._last_bucket[tf]:
                    closures.append(self._flush(tf))
                    self._last_bucket[tf] = bucket

                self._buffers[tf].append(row)

            yield EventoReloj(
                m15_index=int(idx.value),
                m15_timestamp=idx,
                tf_closures=closures,
            )

    def run(self) -> list[EventoReloj]:
        return list(self.iter_eventos())
