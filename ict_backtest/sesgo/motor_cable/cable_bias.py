"""F2 — Cable del motor de sesgo al reloj."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from engine.bias.narrative import HtfBias, compute_htf_bias
from ict_backtest.sesgo.config import SesgoConfig
from ict_backtest.sesgo.motor_cable.warmup import WarmupTracker
from ict_backtest.sesgo.reloj.reloj import EventoReloj, VelaCerrada


@dataclass(frozen=True)
class SesgoVigente:
    bias: HtfBias
    updated_at: pd.Timestamp
    updated_by_d1: bool


class CableBias:
    """Puente entre reloj y motor de sesgo.

    - En cada cierre de D1, arma vistas cerradas D1/H4/H1 y llama al motor.
    - Guarda el sesgo vigente hasta el próximo cierre de D1.
    - Expone disponibilidad según warm-up.
    """

    def __init__(self, config: Optional[SesgoConfig] = None) -> None:
        self.config = config or SesgoConfig()
        self._d1_buffer: list[pd.Series] = []
        self._h4_buffer: list[pd.Series] = []
        self._h1_buffer: list[pd.Series] = []
        self.vigente: Optional[SesgoVigente] = None
        self.warmup = WarmupTracker(self.config)

    def _append(self, vela: VelaCerrada) -> None:
        if vela.timeframe == "D1":
            self._d1_buffer.append(_vela_to_series(vela))
        elif vela.timeframe == "H4":
            self._h4_buffer.append(_vela_to_series(vela))
        elif vela.timeframe == "H1":
            self._h1_buffer.append(_vela_to_series(vela))

    def _build_frames(self):
        d1 = pd.DataFrame(self._d1_buffer)
        h4 = pd.DataFrame(self._h4_buffer)
        h1 = pd.DataFrame(self._h1_buffer)
        for frame in (d1, h4, h1):
            if not frame.empty:
                frame.index = pd.to_datetime(frame["timestamp"])
                frame.index.name = None
        return d1, h4, h1

    def procesar_evento(self, evento: EventoReloj) -> Optional[SesgoVigente]:
        d1_updated = False

        for cierre in evento.tf_closures:
            self._append(cierre)
            self.warmup.record_closure(cierre.timeframe)
            if cierre.timeframe == "D1":
                d1_updated = True

        if d1_updated and self._d1_buffer:
            d1, h4, h1 = self._build_frames()
            bias = compute_htf_bias(
                d1=d1,
                h4=h4,
                h1=h1,
                swing_lookback=5,
            )
            self.vigente = SesgoVigente(
                bias=bias,
                updated_at=evento.m15_timestamp,
                updated_by_d1=True,
            )

        return self.vigente

    def sesgo_vigente(self) -> Optional[SesgoVigente]:
        return self.vigente

    def esta_disponible(self) -> bool:
        return self.warmup.state().available


def _vela_to_series(vela: VelaCerrada) -> pd.Series:
    return pd.Series(
        {
            "timestamp": vela.timestamp,
            "open": vela.open,
            "high": vela.high,
            "low": vela.low,
            "close": vela.close,
        }
    )
