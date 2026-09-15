# -*- coding: utf-8 -*-
"""Tests para el evaluador POI + estocástico M15.

Cada estado de salida del contrato (sección 11.2) tiene al menos un test con
datos sintéticos. No requiere MT5 ni datos reales: se inyecta
closed_m15_candles_fn con listas de Candle sintéticas.

Los tests acceden a las funciones internas (prefijadas con ``_``) para
verificar la lógica de caducidad y detección de cruce por vela, tal como
exige el contrato en la sección 8 (necesidad de StochasticReading por vela).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Sequence

import pytest

from engine.poi_stoch_evaluator import (
    _cross_type,
    _cross_vencido,
    _distance_pips,
    _hubo_cruce_valido_en_vela,
    _lectura_estocastica_por_vela,
    _poi_selected,
    _stochastic_dict,
    evaluate_poi_stoch_m15,
)
from mechanical_bot.core import (
    BotConfig,
    Candle,
    Cycle,
    StochasticReading,
    stochastic_14_3_3,
)

# ===========================================================================
# Helpers de construcción de datos sintéticos
# ===========================================================================

def _candle(high: float, low: float, close: float) -> Candle:
    return Candle(high=high, low=low, close=close)


def _default_config() -> BotConfig:
    return BotConfig(
        symbol="EURUSD",
        k_period=14,
        k_smoothing=3,
        d_period=3,
        oversold=20.0,
        overbought=80.0,
        pip_size=0.0001,
        tolerance_pips=5.0,
    )


def _config_dict() -> dict:
    return {
        "symbol": "EURUSD",
        "k_period": 14,
        "k_smoothing": 3,
        "d_period": 3,
        "oversold": 20.0,
        "overbought": 80.0,
        "pip_size": 0.0001,
        "tolerance_pips": 5.0,
    }


def _make_candles_ranging_middle(n: int, base: float = 1.0000,
                                  range_val: float = 0.0002,
                                  close_fraction: float = 0.50) -> list[Candle]:
    candles: list[Candle] = []
    for _ in range(n):
        candles.append(Candle(
            high=base + range_val,
            low=base,
            close=base + close_fraction * range_val,
        ))
    return candles


def _make_candles_low_close(n: int, base: float = 1.0000,
                             range_val: float = 0.0002) -> list[Candle]:
    return _make_candles_ranging_middle(n, base, range_val, 0.05)


def _make_candles_high_close(n: int, base: float = 1.0000,
                              range_val: float = 0.0002) -> list[Candle]:
    return _make_candles_ranging_middle(n, base, range_val, 0.80)


def _make_candles_rising(n: int, base: float = 1.0000,
                          increment: float = 0.00002) -> list[Candle]:
    candles: list[Candle] = []
    for i in range(n):
        c = base + i * increment
        candles.append(Candle(high=c + 0.0001, low=c - 0.0001, close=c))
    return candles


def _poi_dict(
    id: str = "poi-1",
    type: str = "FVG",
    role: str = "POI",
    state: str = "ACTIVE",
    direction: int = 1,
    zone_low: float = 1.0000,
    zone_high: float = 1.0010,
    creation_time: object = 1000,
) -> dict:
    return {
        "id": id,
        "type": type,
        "role": role,
        "state": state,
        "direction": direction,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "creation_time": creation_time,
    }


def _cycle(direction: str = "BUY", initial_price: float = 1.0000,
           balance_at_start: float = 1000.0,
           signal_time: datetime | None = None) -> Cycle:
    if signal_time is None:
        signal_time = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    return Cycle(
        direction=direction,
        initial_price=initial_price,
        balance_at_start=balance_at_start,
        signal_time=signal_time,
    )


def _closed_m15_fn(candles: list[Candle]) -> Callable[[str, int], list[Candle]]:
    def fn(symbol: str, count: int) -> list[Candle]:
        return candles
    return fn


def _reading(k: float, d: float, previous_k: float, previous_d: float) -> StochasticReading:
    return StochasticReading(k=k, d=d, previous_k=previous_k, previous_d=previous_d)


# ===========================================================================
# Constructores deterministas de cruce
# ===========================================================================

def _build_candles_for_cross_up(cfg: BotConfig) -> list[Candle]:
    """20 velas que producen CROSS_UP_FROM_OVERSOLD.

    19 velas: close en 5% del rango → raw_k ≈ 5
    1 vela (última): close en 80% del rango → raw_k ≈ 80
    Resultado: k≈30, d≈13.33, previous_k=5, previous_d=5
    """
    rng = 0.0002
    base = 1.0000
    candles: list[Candle] = []
    for _ in range(19):
        candles.append(Candle(high=base + rng, low=base, close=base + 0.05 * rng))
    candles.append(Candle(high=base + rng, low=base, close=base + 0.80 * rng))
    return candles


def _build_candles_for_cross_down(cfg: BotConfig) -> list[Candle]:
    """20 velas que producen CROSS_DOWN_FROM_OVERBOUGHT.

    19 velas: close en 95% del rango → raw_k ≈ 95
    1 vela (última): close en 20% del rango → raw_k ≈ 20
    Resultado: k≈35, d≈68.33, previous_k=95, previous_d=95
    """
    rng = 0.0002
    base = 1.0050
    candles: list[Candle] = []
    for _ in range(19):
        candles.append(Candle(high=base + rng, low=base, close=base + 0.95 * rng))
    candles.append(Candle(high=base + rng, low=base, close=base + 0.20 * rng))
    return candles


def _build_candles_no_cross(cfg: BotConfig) -> list[Candle]:
    """80 velas sin cruce (cierre en 50% del rango)."""
    rng = 0.0002
    base = 1.0000
    candles: list[Candle] = []
    for _ in range(80):
        candles.append(Candle(high=base + rng, low=base, close=base + 0.50 * rng))
    return candles


def _build_candles_cross_then_flat(cfg: BotConfig, n_flat: int = 10) -> list[Candle]:
    """Cruce en vela 20, luego n_flat velas sin nuevo cruce.

    Útil para probar caducidad por 3 velas sin nuevo cruce.
    """
    rng = 0.0002
    base = 1.0000
    candles: list[Candle] = []
    for _ in range(19):
        candles.append(Candle(high=base + rng, low=base, close=base + 0.05 * rng))
    base2 = base + 20 * 0.00001
    candles.append(Candle(high=base2 + rng, low=base2, close=base2 + 0.80 * rng))
    for i in range(n_flat):
        b = base2 + (21 + i) * 0.00001
        candles.append(Candle(high=b + rng, low=b, close=b + 0.05 * rng))
    return candles


# ===========================================================================
# Tests de distance_pips (contrato sección 13.1)
# ===========================================================================

class TestDistancePips:
    def test_dentro_de_la_zona_devuelve_cero(self):
        poi = _poi_dict(zone_low=1.0000, zone_high=1.0010)
        assert _distance_pips(poi, 1.0005, 0.0001) == 0.0
        assert _distance_pips(poi, 1.0000, 0.0001) == 0.0
        assert _distance_pips(poi, 1.0010, 0.0001) == 0.0

    def test_fuera_de_la_zona_por_encima(self):
        poi = _poi_dict(zone_low=1.0000, zone_high=1.0010)
        assert _distance_pips(poi, 1.0015, 0.0001) == pytest.approx(5.0, rel=1e-9)

    def test_fuera_de_la_zona_por_abajo(self):
        poi = _poi_dict(zone_low=1.0000, zone_high=1.0010)
        assert _distance_pips(poi, 0.9995, 0.0001) == pytest.approx(5.0, rel=1e-9)

    def test_minima_distancia_al_lado_cercano(self):
        poi = _poi_dict(zone_low=1.0000, zone_high=1.0010)
        assert _distance_pips(poi, 1.0013, 0.0001) == pytest.approx(3.0, rel=1e-9)

    def test_pip_size_distinto(self):
        poi = _poi_dict(zone_low=1.0000, zone_high=1.0010)
        assert _distance_pips(poi, 1.0015, 0.00001) == pytest.approx(50.0, rel=1e-9)

    def test_acepta_marketobject(self):
        from engine.market_object import MarketObject, ObjectType, Role, ObjectState
        mo = MarketObject(
            id="mo-1",
            type=ObjectType.FVG,
            role=Role.POI,
            state=ObjectState.ACTIVE,
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        assert _distance_pips(mo, 1.0015, 0.0001) == pytest.approx(5.0, rel=1e-9)


# ===========================================================================
# Tests de _cross_type (contrato sección 6 / 13.2)
# ===========================================================================

class TestCrossType:
    def test_cross_up_from_oversold(self):
        r = _reading(k=25.0, d=22.0, previous_k=18.0, previous_d=19.0)
        assert _cross_type(r, 1) == "CROSS_UP_FROM_OVERSOLD"

    def test_cross_down_from_overbought(self):
        r = _reading(k=75.0, d=78.0, previous_k=85.0, previous_d=83.0)
        assert _cross_type(r, -1) == "CROSS_DOWN_FROM_OVERBOUGHT"

    def test_no_cross_compra_sin_cruce(self):
        r = _reading(k=50.0, d=52.0, previous_k=48.0, previous_d=50.0)
        assert _cross_type(r, 1) == "NO_CROSS"

    def test_no_cross_venta_sin_cruce(self):
        r = _reading(k=50.0, d=52.0, previous_k=48.0, previous_d=50.0)
        assert _cross_type(r, -1) == "NO_CROSS"

    def test_no_cross_direction_cero(self):
        r = _reading(k=25.0, d=22.0, previous_k=18.0, previous_d=19.0)
        assert _cross_type(r, 0) == "NO_CROSS"

    def test_cross_compra_incorrecto_para_venta(self):
        r = _reading(k=25.0, d=22.0, previous_k=18.0, previous_d=19.0)
        assert _cross_type(r, -1) == "NO_CROSS"

    def test_cross_venta_incorrecto_para_compra(self):
        r = _reading(k=75.0, d=78.0, previous_k=85.0, previous_d=83.0)
        assert _cross_type(r, 1) == "NO_CROSS"

    def test_borde_20_0_k_igual_al_umbral(self):
        r = _reading(k=25.0, d=22.0, previous_k=20.0, previous_d=20.0)
        assert _cross_type(r, 1) == "CROSS_UP_FROM_OVERSOLD"

    def test_borde_80_0_k_igual_al_umbral(self):
        r = _reading(k=75.0, d=78.0, previous_k=80.0, previous_d=80.0)
        assert _cross_type(r, -1) == "CROSS_DOWN_FROM_OVERBOUGHT"


# ===========================================================================
# Tests de stochastic_14_3_3 con datos sintéticos derivados analíticamente
# ===========================================================================

class TestStochasticSynthetic:
    def test_construir_cruce_alcista_determinista(self):
        cfg = _default_config()
        candles = _build_candles_for_cross_up(cfg)
        reading = stochastic_14_3_3(candles, cfg)
        assert reading is not None
        assert reading.k > reading.d
        assert reading.crossed_up_from_oversold(20.0) is True

    def test_construir_cruce_bajista_determinista(self):
        cfg = _default_config()
        candles = _build_candles_for_cross_down(cfg)
        reading = stochastic_14_3_3(candles, cfg)
        assert reading is not None
        assert reading.k < reading.d
        assert reading.crossed_down_from_overbought(80.0) is True

    def test_insuficientes_candles_devuelve_none(self):
        cfg = _default_config()
        candles = _make_candles_low_close(19)
        assert stochastic_14_3_3(candles, cfg) is None

    def test_exactamente_20_candles_devuelve_lectura(self):
        cfg = _default_config()
        candles = _make_candles_low_close(20)
        assert stochastic_14_3_3(candles, cfg) is not None


# ===========================================================================
# Tests de las funciones auxiliares de caducidad (contrato sección 8)
# ===========================================================================

class TestCrossFinding:
    def test_hubo_cruce_valido_en_ultima_vela_alcista(self):
        """El último cruce válido está en la vela 20 (la más reciente)."""
        cfg = _default_config()
        candles = _build_candles_for_cross_up(cfg)
        idx_last = len(candles) - 1
        assert _hubo_cruce_valido_en_vela(candles, cfg, idx_last, 1) is True

    def test_no_hubo_cruce_en_historial_flat(self):
        """No hay cruce en un historial sin cruce."""
        cfg = _default_config()
        candles = _build_candles_no_cross(cfg)
        # Verificar varias velas intermedias
        for idx in [len(candles) - 1, len(candles) - 2, len(candles) - 3]:
            assert _hubo_cruce_valido_en_vela(candles, cfg, idx, 1) is False

    def test_lectura_por_vela_cantidad_minima(self):
        """_lectura_estocastica_por_vela devuelve None si hay < 20 velas."""
        cfg = _default_config()
        candles = _make_candles_low_close(19)
        assert _lectura_estocastica_por_vela(candles, cfg, len(candles) - 1) is None

    def test_lectura_por_vela_con_suficientes_velas(self):
        """Con 20 velas, la lectura por vela se calcula."""
        cfg = _default_config()
        candles = _make_candles_low_close(20)
        lectura = _lectura_estocastica_por_vela(candles, cfg, len(candles) - 1)
        assert lectura is not None

    def test_cruce_vencido_por_3_velas(self):
        """Cruce en vela 20, luego 10 velas flat → vencido por tiempo."""
        cfg = _default_config()
        candles = _build_candles_cross_then_flat(cfg, n_flat=10)
        reading = stochastic_14_3_3(candles, cfg)
        assert reading is not None
        # La lectura final no tiene cruce (flat)
        assert _cross_type(reading, 1) == "NO_CROSS"
        # Pero el cruce anterior está vencido
        assert _cross_vencido(candles, cfg, reading, 1) is True

    def test_cruce_no_vencido_si_hay_nuevo_en_3_velas(self):
        """Cruce + nuevo cruce en las próximas 3 velas → no vence."""
        cfg = _default_config()
        base = _build_candles_for_cross_up(cfg)
        rng = 0.0002
        start = 1.0000 + 20 * 0.00001
        for i in range(3):
            base.append(Candle(high=start + rng, low=start, close=start + 0.80 * rng))
            start += 0.00001

        reading = stochastic_14_3_3(base, cfg)
        assert reading is not None
        # Hay nuevo cruce en las últimas 3 velas
        for idx in [-1, -2, -3]:
            assert _hubo_cruce_valido_en_vela(base, cfg, idx, 1) is True
        assert _cross_vencido(base, cfg, reading, 1) is False

    def test_no_vence_sin_suficientes_velas_despues_cruce(self):
        """Cruce en última vela → no hay suficientes velas después para vencer."""
        cfg = _default_config()
        candles = _build_candles_for_cross_up(cfg)
        reading = stochastic_14_3_3(candles, cfg)
        assert reading is not None
        assert _cross_vencido(candles, cfg, reading, 1) is False

    def test_cruce_vencido_por_inversion_k_d(self):
        """Cruce vigente pero con k <= d → vencido por inversión."""
        cfg = _default_config()
        candles = _build_candles_for_cross_up(cfg)
        reading_inv = _reading(k=20.0, d=23.0, previous_k=18.0, previous_d=19.0)
        assert _cross_vencido(candles, cfg, reading_inv, 1) is True

    def test_vencido_por_inversion_k_d_bajista(self):
        """Cruce bajista con k >= d → vencido."""
        cfg = _default_config()
        candles = _build_candles_for_cross_down(cfg)
        reading_inv = _reading(k=82.0, d=79.0, previous_k=85.0, previous_d=83.0)
        assert _cross_vencido(candles, cfg, reading_inv, -1) is True

    def test_no_vence_sin_suficientes_velas_para_3(self):
        cfg = _default_config()
        candles = _make_candles_low_close(3)
        reading = _reading(k=25.0, d=22.0, previous_k=18.0, previous_d=19.0)
        assert _cross_vencido(candles, cfg, reading, 1) is False


# ===========================================================================
# Tests del evaluador principal — cada estado de salida
# ===========================================================================

class TestEvaluatePoiStochM15:
    """Tests para cada estado de salida definido en contrato sección 11.2."""

    def test_entry_valid_compra(self):
        """Caso A del contrato: entrada válida COMPRA."""
        cfg = _config_dict()
        poi = _poi_dict(
            id="fvga-1",
            type="FVG",
            role="POI",
            state="ACTIVE",
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012  # 2 pips del zone_high (fuera de zona, dentro de tolerancia)

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"] is not None
        assert result["poi_selected"]["id"] == "fvga-1"
        assert result["distance_pips"] == pytest.approx(2.0, rel=0.01)
        assert result["price"] == price
        assert result["candles_available"] == len(candles)
        assert result["stochastic"]["cross_type"] == "CROSS_UP_FROM_OVERSOLD"
        assert result["next_condition"] == "SIN_CONDICION"
        assert result["decision_time"] is not None

    def test_no_eligible_poi_near_price_vacio(self):
        """Lista de market_objects vacía → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        price = 1.0000
        candles = _make_candles_low_close(80)
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None
        assert result["distance_pips"] is None
        assert result["next_condition"] == "AGUARDAR_POI_EN_ZONA"

    def test_no_eligible_poi_near_price_sin_candidatas(self):
        """POI con estado/role/tipo no elegible → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        price = 1.0000
        candles = _make_candles_low_close(80)
        fn = _closed_m15_fn(candles)

        poi_mitigated = _poi_dict(state="MITIGATED")
        poi_refinement = _poi_dict(role="REFINEMENT")
        poi_bos = _poi_dict(type="BOS")

        result = evaluate_poi_stoch_m15(
            [poi_mitigated, poi_refinement, poi_bos],
            price,
            fn,
            None,
            cfg,
        )

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"

    def test_no_eligible_poi_near_price_sin_operables(self):
        """POI con direction=0 → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        price = 1.0000
        candles = _make_candles_low_close(80)
        fn = _closed_m15_fn(candles)

        poi_dir0 = _poi_dict(direction=0, state="ACTIVE", type="FVG")
        poi_dir0_2 = _poi_dict(direction=0, state="ACTIVE", type="ORDER_BLOCK")

        result = evaluate_poi_stoch_m15([poi_dir0, poi_dir0_2], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"

    def test_no_eligible_poi_near_price_lejos_del_precio(self):
        """POI operable pero fuera del margen de tolerancia."""
        cfg = _config_dict()
        poi = _poi_dict(
            zone_low=1.0000,
            zone_high=1.0010,
            direction=1,
            state="ACTIVE",
            type="FVG",
        )
        price = 1.0020  # 10 pips del zone_high → fuera de tolerancia
        candles = _make_candles_low_close(80)
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None
        assert result["distance_pips"] is None

    def test_preselection_resolves_price_side_without_creating_entry(self):
        cfg = _config_dict()
        poi = _poi_dict(zone_low=1.0000, zone_high=1.0010, direction=1, state="ACTIVE", type="FVG")
        result = evaluate_poi_stoch_m15([poi], 0.0, _closed_m15_fn([]), None, cfg, check_proximity=False)
        assert result["status"] == "POI_SELECTED_FOR_PRICE"
        assert result["poi_selected"]["id"] == poi["id"]
        assert result["next_condition"] == "REEVALUAR_PRECIO_POR_DIRECCION"

    def test_insufficient_candles_por_cantidad(self):
        """Menos de 20 velas → INSUFFICIENT_CANDLES."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012  # 2 pips del zone_high

        candles = _make_candles_low_close(15)
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "INSUFFICIENT_CANDLES"
        assert result["poi_selected"] is not None
        assert result["distance_pips"] == pytest.approx(2.0, rel=0.01)
        assert result["candles_available"] == 15
        assert result["next_condition"] == "AGUARDAR_CRUCE_M15"

    def test_no_cross_compra_sin_cruce(self):
        """Estocástico sin cruce para dirección COMPRA → NO_CROSS."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012  # 2 pips del zone_high

        candles = _build_candles_no_cross(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_CROSS"
        assert result["poi_selected"] is not None
        assert result["stochastic"]["cross_type"] == "NO_CROSS"
        assert result["next_condition"] == "AGUARDAR_CRUCE_M15"

    def test_no_cross_venta_con_cruce_incorrecto(self):
        """Hay cruce alcista pero POI es venta → NO_CROSS."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=-1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_CROSS"
        assert result["stochastic"]["cross_type"] == "NO_CROSS"

    def test_cross_expired_por_cruce_anterior_vencido(self):
        """Cruce anterior vencido (3 velas sin nuevo cruce) → CROSS_EXPIRED.

        Construye historial con cruce en vela 20 y 10 velas flat después.
        La lectura final no tiene cruce, pero el cruce anterior está vencido.
        """
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_cross_then_flat(_default_config(), n_flat=10)
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "CROSS_EXPIRED"
        assert result["poi_selected"] is not None
        assert result["next_condition"] == "AGUARDAR_CRUCE_M15"
        assert "venció" in result["reason"].lower()

    def test_cross_expired_por_inversion_k_d(self):
        """Inversión K/D en la vela actual → CROSS_EXPIRED."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        # Construir velas que produzcan lectura con k <= d
        rng = 0.0002
        base = 1.0000
        candles: list[Candle] = []
        for _ in range(19):
            candles.append(Candle(high=base + rng, low=base, close=base + 0.05 * rng))
        # Última vela: close tal que k <= d (cruce invertido)
        candles.append(Candle(high=base + rng, low=base, close=base + 0.10 * rng))

        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "CROSS_EXPIRED"
        assert result["poi_selected"] is not None

    def test_cycle_active_same_direction(self):
        """Caso F del contrato: ciclo activo bloquea entrada."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012  # 2 pips del zone_high

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        cycle = _cycle(direction="BUY")

        result = evaluate_poi_stoch_m15([poi], price, fn, cycle, cfg)

        assert result["status"] == "CYCLE_ACTIVE_SAME_DIRECTION"
        assert result["poi_selected"] is not None
        assert result["distance_pips"] == pytest.approx(2.0, rel=0.01)
        assert result["next_condition"] == "AGUARDAR_FIN_CICLO"
        assert "ciclo activo" in result["reason"].lower()

    def test_cycle_active_same_direction_venta(self):
        """Ciclo activo en dirección VENTA bloquea POI de venta."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=-1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        cycle = _cycle(direction="SELL")

        result = evaluate_poi_stoch_m15([poi], price, fn, cycle, cfg)

        assert result["status"] == "CYCLE_ACTIVE_SAME_DIRECTION"
        assert result["next_condition"] == "AGUARDAR_FIN_CICLO"

    def test_cycle_no_bloquea_si_diferente_direccion(self):
        """Ciclo BUY no bloquea POI de venta → ENTRY_VALID."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=-1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        cycle = _cycle(direction="BUY")

        result = evaluate_poi_stoch_m15([poi], price, fn, cycle, cfg)

        assert result["status"] == "ENTRY_VALID"

    def test_invalid_direction_nunca_alcanzable(self):
        """direction=0 es filtrado por paso 2 → NO_ELIGIBLE_POI_NEAR_PRICE.

        El estado INVALID_DIRECTION es teóricamente alcanzable solo si
        la función _poi_selected pudiera retornar un objeto con direction=0
        después del filtro de operables, lo cual no debería ocurrir.
        """
        cfg = _config_dict()
        poi = _poi_dict(
            direction=0, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012
        candles = _make_candles_low_close(80)
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"

    def test_seleccion_poi_mas_cercana(self):
        """De múltiples POI cercanas, se selecciona la de menor distance_pips."""
        cfg = _config_dict()
        poi_lejos = _poi_dict(
            id="poi-lejos",
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        poi_cerca = _poi_dict(
            id="poi-cerca",
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0008, zone_high=1.0018,
            creation_time=2000,
        )
        price = 1.0012  # dentro de [1.0008, 1.0018] → distance=0 para poi_cerca

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_lejos, poi_cerca], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"]["id"] == "poi-cerca"
        assert result["distance_pips"] == 0.0

    def test_desempate_por_creation_time(self):
        """Si dos POI tienen el mismo distance_pips, gana la más reciente."""
        cfg = _config_dict()
        poi_antigua = _poi_dict(
            id="poi-antigua",
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        poi_reciente = _poi_dict(
            id="poi-reciente",
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=2000,
        )
        price = 1.0012  # mismo distance_pips para ambas (2 pips fuera)

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_antigua, poi_reciente], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"]["id"] == "poi-reciente"

    def test_dentro_de_la_zona_distance_cero(self):
        """POI dentro de la zona → distance_pips = 0.0."""
        cfg = _config_dict()
        poi = _poi_dict(
            zone_low=1.0000, zone_high=1.0010,
            direction=1, state="ACTIVE", type="FVG",
            creation_time=1000,
        )
        price = 1.0005  # dentro de la zona

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["distance_pips"] == 0.0

    def test_acepta_botconfig(self):
        """La función acepta BotConfig en lugar de dict."""
        cfg = _default_config()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(cfg)
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] in ("ENTRY_VALID", "NO_CROSS", "CROSS_EXPIRED")
        for field in (
            "decision_time", "status", "reason", "poi_selected",
            "distance_pips", "price", "stochastic",
            "candles_available", "next_condition",
        ):
            assert field in result, f"falta campo {field}"

    def test_caso_b_bajista_sin_poi_en_proximidad(self):
        """Caso B del contrato: estocástico presenta cruce bajista pero no
        hay POI en proximidad."""
        cfg = _config_dict()
        price = 1.0000

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        poi_lejos = _poi_dict(
            zone_low=1.0100, zone_high=1.0110,
            direction=-1, state="ACTIVE", type="FVG",
            creation_time=1000,
        )

        result = evaluate_poi_stoch_m15([poi_lejos], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"

    def test_poi_mitigated_descartada(self):
        """Caso C del contrato: POI con state=MITIGATED no es elegible."""
        cfg = _config_dict()
        poi_mitigated = _poi_dict(
            state="MITIGATED", direction=1,
            type="FVG", zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_mitigated], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"

    def test_doble_poi_desempate(self):
        """Caso D del contrato: doble POI en proximidad, desempate por
        creation_time."""
        cfg = _config_dict()
        fvg_a = _poi_dict(
            id="fvg-a",
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        fvg_b = _poi_dict(
            id="fvg-b",
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=2000,
        )

        price = 1.0012  # 2 pips fuera de ambas zonas

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([fvg_a, fvg_b], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"]["id"] == "fvg-b"

    def test_output_campos_exactos(self):
        """El output tiene exactamente los campos definidos en contrato sección 11."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012
        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        expected_fields = {
            "decision_time",
            "status",
            "reason",
            "poi_selected",
            "distance_pips",
            "price",
            "stochastic",
            "candles_available",
            "next_condition",
        }
        assert set(result.keys()) == expected_fields

    def test_stochastic_dict_structure(self):
        """El dict stochastic tiene los campos de sección 11.3."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012
        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        s = result["stochastic"]
        assert isinstance(s, dict)
        for field in ("k", "d", "previous_k", "previous_d", "cross_type"):
            assert field in s, f"falta campo stochastic.{field}"

    def test_candles_available_refleja_lo_devuelto_por_fn(self):
        """candles_available coincide con len(candles) devuelto por la fn."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles_50 = _make_candles_low_close(50)
        fn = _closed_m15_fn(candles_50)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["candles_available"] == 50

    def test_market_objects_con_objetos_mixed(self):
        """market_objects puede contener dicts y MarketObject mezclados."""
        from engine.market_object import MarketObject, ObjectType, Role, ObjectState

        cfg = _config_dict()
        price = 1.0012

        poi_dict = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )

        mo = MarketObject(
            id="mo-1",
            type=ObjectType.FVG,
            role=Role.POI,
            state=ObjectState.ACTIVE,
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
            creation_time=2000,
        )

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_dict, mo], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        # La POI más reciente (creation_time=2000) debería ganar el desempate
        assert result["poi_selected"].id == "mo-1"

    def test_candles_menos_de_20_devuelve_insufficient(self):
        """Si closed_m15_candles_fn devuelve < 20 velas, es INSUFFICIENT."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        def fn_few(symbol: str, count: int) -> list[Candle]:
            return _make_candles_low_close(19)

        result = evaluate_poi_stoch_m15([poi], price, fn_few, None, cfg)

        assert result["status"] == "INSUFFICIENT_CANDLES"
        assert result["candles_available"] == 19

    def test_candles_exactamente_20_es_suficiente(self):
        """Con exactamente 20 velas, el estocástico se calcula."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        def fn_20(symbol: str, count: int) -> list[Candle]:
            return _build_candles_for_cross_up(_default_config())

        result = evaluate_poi_stoch_m15([poi], price, fn_20, None, cfg)

        assert result["candles_available"] == 20
        assert result["status"] in ("ENTRY_VALID", "NO_CROSS", "CROSS_EXPIRED")
        assert result["stochastic"] is not None
        assert "cross_type" in result["stochastic"]

    def test_order_block_elegible(self):
        """ORDER_BLOCK con rol POI y estado ACTIVE es POI elegible."""
        cfg = _config_dict()
        poi = _poi_dict(
            type="ORDER_BLOCK",
            direction=1, state="ACTIVE", role="POI",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"]["type"] == "ORDER_BLOCK"

    def test_sopotamical_cycle_block_only_same_direction(self):
        """Ciclo en dirección opuesta no bloquea."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        # Cycle en dirección opuesta (SELL) no debe bloquear POI BUY
        cycle_opposite = _cycle(direction="SELL")

        result = evaluate_poi_stoch_m15([poi], price, fn, cycle_opposite, cfg)

        assert result["status"] == "ENTRY_VALID"


# ===========================================================================
# Tests de edge cases y validación de parámetros
# ===========================================================================

class TestEdgeCases:
    def test_market_objects_con_objetos_mixed(self):
        """market_objects puede contener dicts y MarketObject mezclados."""
        from engine.market_object import MarketObject, ObjectType, Role, ObjectState

        cfg = _config_dict()
        price = 1.0012

        poi_dict = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )

        mo = MarketObject(
            id="mo-1",
            type=ObjectType.FVG,
            role=Role.POI,
            state=ObjectState.ACTIVE,
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
            creation_time=2000,
        )

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_dict, mo], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        # La POI más reciente (creation_time=2000) debería ganar el desempate
        assert result["poi_selected"].id == "mo-1"

    def test_candles_menos_de_20_devuelve_insufficient(self):
        """Si closed_m15_candles_fn devuelve < 20 velas, es INSUFFICIENT."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        def fn_few(symbol: str, count: int) -> list[Candle]:
            return _make_candles_low_close(19)

        result = evaluate_poi_stoch_m15([poi], price, fn_few, None, cfg)

        assert result["status"] == "INSUFFICIENT_CANDLES"
        assert result["candles_available"] == 19

    def test_candles_exactamente_20_es_suficiente(self):
        """Con exactamente 20 velas, el estocástico se calcula."""
        cfg = _config_dict()
        poi = _poi_dict(
            direction=1, state="ACTIVE", type="FVG",
            zone_low=1.0000, zone_high=1.0010,
            creation_time=1000,
        )
        price = 1.0012

        def fn_20(symbol: str, count: int) -> list[Candle]:
            return _build_candles_for_cross_up(_default_config())

        result = evaluate_poi_stoch_m15([poi], price, fn_20, None, cfg)

        assert result["candles_available"] == 20
        assert result["status"] in ("ENTRY_VALID", "NO_CROSS", "CROSS_EXPIRED")
        assert result["stochastic"] is not None
        assert "cross_type" in result["stochastic"]


# ===========================================================================
# Tests de stochastic_dict
# ===========================================================================

class TestStochasticDict:
    def test_con lectura_completa(self):
        reading = _reading(k=25.0, d=22.0, previous_k=18.0, previous_d=19.0)
        d = _stochastic_dict(reading, "CROSS_UP_FROM_OVERSOLD")
        assert d == {
            "k": 25.0,
            "d": 22.0,
            "previous_k": 18.0,
            "previous_d": 19.0,
            "cross_type": "CROSS_UP_FROM_OVERSOLD",
        }

    def test_con lectura_none(self):
        d = _stochastic_dict(None, "NO_CROSS")
        assert d == {"cross_type": "NO_CROSS"}
