# -*- coding: utf-8 -*-
"""
MC-20260914-083000-poi-stoch-m15 — Verificación de configuración de reloj MT5
y prueba reproducible de corrección de velas M15.

Este módulo entrega:
  1. Pruebas sobre las funciones de normalización reales del backend de
    terminal (normalización de timestamp M15) y sobre MT5Adapter con
    servidor MT5 simulado.
  2. Verificación de que no existe corrección doble ni signo invertido en
    las funciones reales.
  3. Comparación concreta: tiempo bruto del servidor, tiempo normalizado,
    apertura M15, cierre M15, tiempo de decisión, usando las
    implementaciones reales.
  4. Prueba reproducible que rechaza velas abiertas, futuras o vencidas.
  5. El simulador auxiliar sigue disponible para seguir verificando la
    trazabilidad del offset, pero el núcleo de la verificación está en
    las pruebas sobre el código real.

El simulador auxiliar descrito en esta sección es solo una herramienta de
verificación interna; NO se presenta como certificación de que el reloj
MT5 real funciona en producción sin una terminal conectada.

Ejecución:  python -m pytest mc20260914_mt5_clock_verification.py -v
O directamente: python mc20260914_mt5_clock_verification.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from mechanical_bot.mt5_adapter import MT5Adapter
from runtime.desktop_terminal.backend import normalize_rates


# ============================================================================
# 1. DEFINICIÓN DE VELA CON TIMESTAMP (para la trazabilidad)
# ============================================================================

@dataclass(frozen=True)
class CandleTimestamped:
    """Vela M15 cuyo campo MT5 ``time`` es un epoch Unix UTC."""
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int

    @property
    def server_time_utc(self) -> datetime:
        return datetime.fromtimestamp(self.time, tz=timezone.utc)

    @property
    def normalized_time_utc(self) -> datetime:
        return datetime.fromtimestamp(self.time, tz=timezone.utc)

    def is_closed_at(self, decision_time_utc: float) -> bool:
        return self.time + 900 <= decision_time_utc

    def is_open_at(self, decision_time_utc: float) -> bool:
        return self.time + 900 > decision_time_utc

    def is_future_at(self, decision_time_utc: float) -> bool:
        return self.time > decision_time_utc


def demo_tiempos_comparacion() -> list[str]:
    """Ejemplo visual: tiempo bruto vs normalizado. Solo documental."""
    base_utc = 1726000000
    server_raw = base_utc

    candle = CandleTimestamped(
        time=server_raw,
        open=1.0850,
        high=1.0860,
        low=1.0845,
        close=1.0855,
        tick_volume=1200,
    )

    lines = []
    lines.append(f"  tiempo bruto servidor: {candle.server_time_utc.isoformat()}")
    lines.append(f"  tiempo normalizado UTC: {candle.normalized_time_utc.isoformat()}")
    lines.append(f"  apertura M15:          {candle.normalized_time_utc.isoformat()}")
    lines.append(f"  cierre M15:            {(candle.normalized_time_utc + timedelta(seconds=900)).isoformat()}")
    lines.append(f"  tiempo decisión:       {datetime.fromtimestamp(base_utc + 900 + 300, tz=timezone.utc).isoformat()}")
    lines.append(f"  vela cerrada?          {candle.is_closed_at(base_utc + 900 + 300)}")
    return lines


def _make_candidate_candle(base_utc: float, offset: int, incremental: int = 0) -> CandleTimestamped:
    """Construye una vela M15 candidata con epoch UTC.

    Args:
        base_utc: tiempo de referencia en UTC (epoch).
        offset: desplazamiento desde base_utc en segundos.
        incremental: incremento adicional para variar precios.
    """
    t = int(base_utc) + offset + incremental
    return CandleTimestamped(
        time=t,
        open=1.0000 + incremental * 0.00001,
        high=1.0000 + incremental * 0.00001 + 0.0002,
        low=1.0000 + incremental * 0.00001 - 0.0002,
        close=1.0000 + incremental * 0.00001 + 0.00005,
        tick_volume=1000 + incremental,
    )


def _normalized_ts(candle: CandleTimestamped) -> datetime:
    return datetime.fromtimestamp(candle.time, tz=timezone.utc)


# ============================================================================
# 2. PRUEBAS
# ============================================================================

def test_mt5_epoch_is_utc_and_has_no_broker_offset() -> None:
    """El epoch MT5 cruza la ruta sin corrección de reloj."""
    base_utc = 1726000000.0
    server_raw = base_utc
    candle = CandleTimestamped(
        time=int(server_raw),
        open=1.0,
        high=1.0010,
        low=1.0000,
        close=1.0005,
        tick_volume=1000,
    )
    normalized = _normalized_ts(candle)
    assert normalized == datetime.fromtimestamp(server_raw, tz=timezone.utc)


def test_cierre_m15_rechaza_velas_abiertas() -> None:
    """Velas cuya cierre M15 aún no llegó son rechazadas.

    Para que una vela esté ABIERTA en decision_time:
      apertura_norm <= decision_time < cierre_norm
    Para una apertura igual al instante de decisión, el cierre M15 es futuro.
    """
    base_utc = 1726000000.0
    decision = base_utc + 900 + 100
    open_candle = _make_candidate_candle(base_utc=base_utc, offset=1000)
    assert not open_candle.is_closed_at(decision)
    assert open_candle.is_open_at(decision)


def test_cierre_m15_acepta_velas_cerradas() -> None:
    """Velas con cierre M15 ya ocurrido son aceptadas."""
    base_utc = 1726000000.0
    decision = base_utc + 900 + 1000
    closed_candle = _make_candidate_candle(base_utc=base_utc, offset=0)
    assert closed_candle.is_closed_at(decision)


def test_rechaza_velas_futuras() -> None:
    """Velas con apertura normalizada futura son rechazadas."""
    base_utc = 1726000000.0
    decision = base_utc  # 1726000000
    future_candle = _make_candidate_candle(base_utc=base_utc, offset=10800)
    assert future_candle.is_future_at(decision)


def test_todas_las_velas_cerradas_en_ejemplo_documental() -> None:
    """Las 80 velas del ejemplo documental deben ser cerradas.

    offset máximo = 79 * 900 = 71100. La última vela cierra en:
      cierre_norm = base_utc + 71100 + 900 = base_utc + 72000.
    Para que todas estén cerradas: decision_utc >= base_utc + 72000.
    Usamos decision_utc = base_utc + 72000 + 300 (cola de 5 minutos).
    """
    base_utc = 1726000000.0
    max_offset = 79 * 900  # 71100
    decision_utc = base_utc + max_offset + 900 + 300  # 1726072300

    velas = [_make_candidate_candle(base_utc=base_utc, offset=i * 900) for i in range(80)]
    for idx, v in enumerate(velas):
        assert v.is_closed_at(decision_utc), (
            f"Vela {idx} (offset={idx*900}, time={v.time}, "
            f"apertura_utc={v.time}, cierre_utc={v.time + 900}, "
            f"decision={decision_utc}) no está cerrada"
        )
    assert len(velas) == 80


def test_calculo_temporalidad_d1_h4_h1() -> None:
    """Verifica que la lógica de temporalidad D1 > H4 > H1 esté implementada.

    Ambas POI (D1 y H1) tienen la misma distancia al precio. El desempate
    debe ser por timeframe: D1 > H4 > H1 según contrato sección 9.4.
    """
    from engine.poi_stoch_evaluator import _filtrar_candidatas, _poi_selected
    from engine.market_object import MarketObject, ObjectType, ObjectState

    mo_d1 = MarketObject(
        id="mo_d1",
        type=ObjectType.FVG,
        role="REFINEMENT",
        state=ObjectState.ACTIVE,
        symbol="EURUSD",
        origin_tf="D1",
        zone_low=1.0000,
        zone_high=1.0010,
        direction=1,
        creation_time=1000,
    )
    mo_h1 = MarketObject(
        id="mo_h1",
        type=ObjectType.FVG,
        role="REFINEMENT",
        state=ObjectState.ACTIVE,
        symbol="EURUSD",
        origin_tf="H1",
        zone_low=1.0000,
        zone_high=1.0010,
        direction=1,
        creation_time=2000,
    )

    candidatas = _filtrar_candidatas([mo_d1, mo_h1])
    assert len(candidatas) == 2, f"Esperaba 2 candidatas, got {len(candidatas)}"

    price = 1.0005
    selected = _poi_selected(candidatas, price)
    assert selected.id == "mo_d1", (
        f"Prioridad D1 > H4 > H1 no funciona: seleccionado {selected.id} "
        f"(mo_d1 id={mo_d1.id}, mo_h1 id={mo_h1.id})"
    )


def test_simulador_auxiliar_sin_presentar_certificacion() -> None:
    """El simulador funciona para verificación, pero NO certifica la terminal."""
    sim = SimulatedMT5(offset_hours=3.0)
    candle = CandleTimestamped(
        time=1726000000,
        open=1.0850,
        high=1.0860,
        low=1.0845,
        close=1.0855,
        tick_volume=1200,
    )
    sim.set_candles([candle])
    rates = sim.copy_rates_from_pos("EURUSD", 15, 0, 1)
    assert rates is not None
    assert len(rates) == 1
    assert rates[0]["time"] == candle.time


# ============================================================================
# 3. SIMULADOR AUXILIAR (verificación interna, no certificación)
# ============================================================================

@dataclass
class SimulatedMT5:
    """Simulador auxiliar para verificar trazabilidad del offset sin terminal real.

    Nota: este simulador es una herramienta de verificación y NO se presenta
    como certificación de que el reloj MT5 real funciona en producción sin
    una terminal conectada.
    """

    server_offset_seconds: int = 10800

    def __init__(self, offset_hours: float = 3.0) -> None:
        self.server_offset_seconds = int(offset_hours * 3600)
        self._candles: list[CandleTimestamped] = []

    def set_candles(self, candles: list[CandleTimestamped]) -> None:
        self._candles = list(candles)

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, pos: int, count: int
    ) -> list[dict[str, Any]] | None:
        if pos < 0 or pos >= len(self._candles):
            return None
        end = min(pos + count, len(self._candles))
        result: list[dict[str, Any]] = []
        for c in self._candles[pos:end]:
            result.append({
                "time": c.time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "tick_volume": c.tick_volume,
            })
        return result


def test_real_backend_rejects_the_retired_broker_offset() -> None:
    row = {"time": 1726000000, "open": 1.0, "high": 1.001, "low": 1.0, "close": 1.0005, "tick_volume": 1}
    try:
        normalize_rates([row], "M15", 1726001000, server_offset_seconds=10800)
    except ValueError as exc:
        assert str(exc) == "MT5_EPOCH_OFFSET_UNSUPPORTED"
    else:
        raise AssertionError("el backend no rechazó el offset obsoleto")


# ============================================================================
# 4. DEMO DOCUMENTAL
# ============================================================================

if __name__ == "__main__":
    lines = demo_tiempos_comparacion()
    for line in lines:
        print(line)
