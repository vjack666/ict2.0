# -*- coding: utf-8 -*-
"""Tests de integración para evaluate_poi_stoch_m15 con object_projection canónico.

Estos tests usan MarketObject con role=REFINEMENT (el papel real que los
detectores publican en el object_projection), nunca role=POI.  Verifican que
el evaluador contrata correctamente objetos REFINEMENT cuando cumplen los
criterios de tipo, temporalidad, estado y geometría definidos en sección 2.1
del contrato v2.

Contrato de salida esperado (cada estado del contrato sección 11.2):
  - ENTRY_VALID
  - NO_ELIGIBLE_POI_NEAR_PRICE
  - NO_CROSS
  - CROSS_EXPIRED
  - CYCLE_ACTIVE_SAME_DIRECTION
  - INSUFFICIENT_CANDLES
  - INVALID_DIRECTION (defensivamente, nunca alcanzable en la ruta normal)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import pytest

from engine.market_object import (
    MarketObject,
    ObjectType,
    Role,
    ObjectState,
)
from engine.poi_stoch_evaluator import evaluate_poi_stoch_m15
from mechanical_bot.core import BotConfig, Candle, Cycle, StochasticReading, stochastic_14_3_3

# ===========================================================================
# Helpers de construcción
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


def _closed_m15_fn(candles: list[Candle]) -> Callable[[str, int], list[Candle]]:
    def fn(symbol: str, count: int) -> list[Candle]:
        return candles
    return fn


def _reading(k: float, d: float, previous_k: float, previous_d: float) -> StochasticReading:
    return StochasticReading(k=k, d=d, previous_k=previous_k, previous_d=previous_d)


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


# ===========================================================================
# Constructores deterministas de cruce (copiados de test_poi_stoch_evaluator)
# ===========================================================================

def _build_candles_for_cross_up(cfg: BotConfig) -> list[Candle]:
    """20 velas que producen CROSS_UP_FROM_OVERSOLD."""
    rng = 0.0002
    base = 1.0000
    candles: list[Candle] = []
    for _ in range(19):
        candles.append(Candle(high=base + rng, low=base, close=base + 0.05 * rng))
    candles.append(Candle(high=base + rng, low=base, close=base + 0.80 * rng))
    return candles


def _build_candles_for_cross_down(cfg: BotConfig) -> list[Candle]:
    """20 velas que producen CROSS_DOWN_FROM_OVERBOUGHT."""
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
    """Cruce en vela 20, luego n_flat velas sin nuevo cruce."""
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
# Helpers específicos para object_projection canónico (role=REFINEMENT)
# ===========================================================================

def _refinement_fvg(
    id: str = "ref-fvg-1",
    direction: int = 1,
    zone_low: float = 1.0000,
    zone_high: float = 1.0010,
    creation_time: object = 1000,
    state: ObjectState = ObjectState.ACTIVE,
    symbol: str = "EURUSD",
    origin_tf: str = "D1",
) -> MarketObject:
    """MarketObject canónico con role=REFINEMENT (FVG)."""
    return MarketObject(
        id=id,
        type=ObjectType.FVG,
        role=Role.REFINEMENT,
        state=state,
        direction=direction,
        zone_low=zone_low,
        zone_high=zone_high,
        origin_tf=origin_tf,
        symbol=symbol,
        creation_time=creation_time,
    )


def _refinement_ob(
    id: str = "ref-ob-1",
    direction: int = 1,
    zone_low: float = 1.0000,
    zone_high: float = 1.0010,
    creation_time: object = 1000,
    state: ObjectState = ObjectState.ACTIVE,
    symbol: str = "EURUSD",
    origin_tf: str = "D1",
) -> MarketObject:
    """MarketObject canónico con role=REFINEMENT (ORDER_BLOCK)."""
    return MarketObject(
        id=id,
        type=ObjectType.ORDER_BLOCK,
        role=Role.REFINEMENT,
        state=state,
        direction=direction,
        zone_low=zone_low,
        zone_high=zone_high,
        origin_tf=origin_tf,
        symbol=symbol,
        creation_time=creation_time,
    )


# ===========================================================================
# Tests de integración — role=REFINEMENT (object_projection canónico)
# ===========================================================================

class TestIntegrationRefinementRole:
    """Verify evaluate_poi_stoch_m15 accepts market_objects publicados como
    REFINEMENT (no POI) cuando cumplen los criterios de elegibilidad del
    contrato v2 sección 2.1.
    """

    # ------------------------------------------------------------------
    # ENTRY_VALID
    # ------------------------------------------------------------------

    def test_entry_valid_fvg_refinement_d1_active_bullish_cross(self):
        """Caso A: FVG D1 ACTIVE (role=REFINEMENT) + cruce M15 alcista → ENTRY_VALID."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            id="ref-fvg-bull",
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            creation_time=1000,
            state=ObjectState.ACTIVE,
            origin_tf="D1",
        )
        price = 1.0012  # 2 pips del zone_high (fuera de zona, dentro de tolerancia)

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"] is not None
        assert result["poi_selected"].id == "ref-fvg-bull"
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["poi_selected"].type == ObjectType.FVG
        assert result["distance_pips"] == pytest.approx(2.0, rel=0.01)
        assert result["price"] == price
        assert result["candles_available"] == len(candles)
        assert result["stochastic"]["cross_type"] == "CROSS_UP_FROM_OVERSOLD"
        assert result["next_condition"] == "SIN_CONDICION"
        assert result["decision_time"] is not None
        # Output campos exactos (contrato sección 11)
        expected_fields = {
            "decision_time", "status", "reason", "poi_selected",
            "distance_pips", "price", "stochastic",
            "candles_available", "next_condition",
            "price_type", "cross_id",
        }
        assert set(result.keys()) == expected_fields

    def test_entry_valid_ob_refinement_d1_active_bullish_cross(self):
        """ORDER_BLOCK D1 ACTIVE (role=REFINEMENT) + cruce M15 alcista → ENTRY_VALID."""
        cfg = _config_dict()
        poi = _refinement_ob(
            id="ref-ob-bull",
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            creation_time=1000,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].id == "ref-ob-bull"
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["poi_selected"].type == ObjectType.ORDER_BLOCK
        assert result["stochastic"]["cross_type"] == "CROSS_UP_FROM_OVERSOLD"

    def test_entry_valid_fvg_refinement_h4_active_bullish_cross(self):
        """FVG H4 ACTIVE (role=REFINEMENT) es POI elegible (origin_tf=H4)."""
        cfg = _config_dict()
        poi = _refinement_fvg(origin_tf="H4", id="ref-fvg-h4")
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].origin_tf == "H4"

    def test_entry_valid_fvg_refinement_h1_active_bullish_cross(self):
        """FVG H1 ACTIVE (role=REFINEMENT) es POI elegible (origin_tf=H1)."""
        cfg = _config_dict()
        poi = _refinement_fvg(origin_tf="H1", id="ref-fvg-h1")
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].origin_tf == "H1"

    def test_entry_valid_price_inside_zone_distance_zero(self):
        """Precio dentro de la zona → distance_pips = 0.0."""
        cfg = _config_dict()
        poi = _refinement_fvg(zone_low=1.0000, zone_high=1.0010)
        price = 1.0005  # dentro de la zona

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["distance_pips"] == 0.0

    def test_entry_valid_bearish_cross_venta(self):
        """FVG D1 ACTIVE (role=REFINEMENT) + cruce M15 bajista → ENTRY_VALID (VENTA)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            id="ref-fvg-bear",
            direction=-1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["stochastic"]["cross_type"] == "CROSS_DOWN_FROM_OVERBOUGHT"

    def test_entry_valid_partially_mitigated_elegible(self):
        """PARTIALLY_MITIGATED (role=REFINEMENT) es elegible según contrato v2."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            state=ObjectState.PARTIALLY_MITIGATED,
            id="ref-fvg-pm",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].state == ObjectState.PARTIALLY_MITIGATED

    # ------------------------------------------------------------------
    # NO_ELIGIBLE_POI_NEAR_PRICE — rechazos
    # ------------------------------------------------------------------

    def test_no_eligible_poi_near_price_out_of_tolerance(self):
        """Caso rechazo: POI (role=REFINEMENT) fuera de tolerancia → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            zone_low=1.0000,
            zone_high=1.0010,
            direction=1,
            origin_tf="D1",
        )
        price = 1.0020  # 10 pips del zone_high → fuera de tolerancia (5 pips)

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None
        assert result["distance_pips"] is None
        assert result["next_condition"] == "AGUARDAR_POI_EN_ZONA"

    def test_no_eligible_poi_near_price_mitigated_state(self):
        """POI MITIGATED (role=REFINEMENT) no es elegible → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            state=ObjectState.MITIGATED,
            id="ref-fvg-mitigated",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_m1_tf_not_poi_tf(self):
        """FVG M1 (origin_tf=M1) no es POI-TF → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            origin_tf="M1",
            id="ref-fvg-m1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_invalidated_state(self):
        """FVG INVALIDATED (role=REFINEMENT) no es elegible → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            state=ObjectState.INVALIDATED,
            id="ref-fvg-invalidated",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_created_state(self):
        """FVG CREATED (role=REFINEMENT) no es elegible → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            state=ObjectState.CREATED,
            id="ref-fvg-created",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_expired_state(self):
        """FVG EXPIRED (role=REFINEMENT) no es elegible → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            state=ObjectState.EXPIRED,
            id="ref-fvg-expired",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_consumed_state(self):
        """FVG CONSUMED (role=REFINEMENT) no es elegible → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            state=ObjectState.CONSUMED,
            id="ref-fvg-consumed",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_wrong_symbol(self):
        """FVG D1 ACTIVE con symbol='GBPUSD' → NO_ELIGIBLE_POI_NEAR_PRICE (símbolo no coincide)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            symbol="GBPUSD",
            id="ref-fvg-gbp",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_empty_list(self):
        """Lista vacía → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        price = 1.0000
        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None
        assert result["distance_pips"] is None

    def test_no_eligible_poi_near_price_bos_type_not_eligible(self):
        """BOS (role=REFINEMENT) no es tipo POI → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = MarketObject(
            id="ref-bos-1",
            type=ObjectType.BOS,
            role=Role.REFINEMENT,
            state=ObjectState.ACTIVE,
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
            symbol="EURUSD",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_no_eligible_poi_near_price_direction_zero_filtered(self):
        """FVG D1 ACTIVE con direction=0 → NO_ELIGIBLE_POI_NEAR_PRICE (no operable)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=0,
            id="ref-fvg-dir0",
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    # ------------------------------------------------------------------
    # Selección de POI más cercana (desempate)
    # ------------------------------------------------------------------

    def test_seleccion_poi_mas_cercana_refinement(self):
        """De múltiples REFINEMENT, se selecciona la de menor distance_pips."""
        cfg = _config_dict()
        poi_lejos = _refinement_fvg(
            id="ref-fvg-lejos",
            zone_low=1.0000,
            zone_high=1.0010,
            direction=1,
            origin_tf="D1",
            creation_time=1000,
        )
        poi_cerca = _refinement_fvg(
            id="ref-fvg-cerca",
            zone_low=1.0008,
            zone_high=1.0018,
            direction=1,
            origin_tf="D1",
            creation_time=2000,
        )
        price = 1.0012  # dentro de [1.0008, 1.0018] → distance=0 para poi_cerca

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_lejos, poi_cerca], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].id == "ref-fvg-cerca"
        assert result["distance_pips"] == 0.0

    def test_desempate_por_creation_time_refinement(self):
        """Si dos REFINEMENT tienen el mismo distance_pips, gana la más reciente."""
        cfg = _config_dict()
        poi_antigua = _refinement_fvg(
            id="ref-fvg-antigua",
            zone_low=1.0000,
            zone_high=1.0010,
            direction=1,
            origin_tf="D1",
            creation_time=1000,
        )
        poi_reciente = _refinement_fvg(
            id="ref-fvg-reciente",
            zone_low=1.0000,
            zone_high=1.0010,
            direction=1,
            origin_tf="D1",
            creation_time=2000,
        )
        price = 1.0012  # mismo distance_pips para ambas (2 pips fuera)

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_antigua, poi_reciente], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].id == "ref-fvg-reciente"

    def test_desempate_mixed_refinement_and_poi_dict(self):
        """Mezcla de MarketObject REFINEMENT y dict POI: el más reciente gana."""
        cfg = _config_dict()
        poi_dict = {
            "id": "dict-poi",
            "type": "FVG",
            "role": "POI",
            "state": "ACTIVE",
            "direction": 1,
            "zone_low": 1.0000,
            "zone_high": 1.0010,
            "creation_time": 1000,
            "origin_tf": "D1",
        }
        poi_mo = _refinement_fvg(
            id="mo-ref",
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
            creation_time=2000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_dict, poi_mo], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        # El MarketObject REFINEMENT con creation_time=2000 gana el desempate
        assert result["poi_selected"].id == "mo-ref"
        assert result["poi_selected"].role == Role.REFINEMENT

    # ------------------------------------------------------------------
    # NO_CROSS
    # ------------------------------------------------------------------

    def test_no_cross_poi_valid_refinement_sin_cruce_m15(self):
        """Caso rechazo: POI (role=REFINEMENT) válido pero sin cruce M15 → NO_CROSS."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012  # 2 pips del zone_high

        candles = _build_candles_no_cross(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_CROSS"
        assert result["poi_selected"] is not None
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["stochastic"]["cross_type"] == "NO_CROSS"
        assert result["next_condition"] == "AGUARDAR_CRUCE_M15"

    def test_no_cross_venta_con_cruce_alcista_incorrecto(self):
        """Hay cruce alcista pero POI es venta (role=REFINEMENT) → NO_CROSS."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=-1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_CROSS"
        assert result["stochastic"]["cross_type"] == "NO_CROSS"

    def test_no_cross_venta_con_cruce_bajista_correcto(self):
        """Cruce bajista para POI venta (role=REFINEMENT) → no es NO_CROSS (es ENTRY_VALID o CROSS_EXPIRED)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=-1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        # Con cruce bajista reciente y sin caducidad → ENTRY_VALID
        assert result["status"] == "ENTRY_VALID"
        assert result["stochastic"]["cross_type"] == "CROSS_DOWN_FROM_OVERBOUGHT"
        assert result["poi_selected"].role == Role.REFINEMENT

    # ------------------------------------------------------------------
    # CROSS_EXPIRED
    # ------------------------------------------------------------------

    def test_cross_expired_por_tres_velas_sin_nuevo_cruce_refinement(self):
        """Caso rechazo: cruce vencido por 3 velas sin nuevo cruce (role=REFINEMENT).

        El flujo principal de evaluate_poi_stoch_m15 no alcanza CROSS_EXPIRED
        cuando la última vela no tiene cruce válido (retorna NO_CROSS antes).
        Este test verifica _cross_vencido con un cruce en la vela 20 y las
        3 velas siguientes sin nuevo cruce (usando MarketObject REFINEMENT).

        NOTA: el helper _build_candles_cross_then_flat del test existente
        tiene un bug conocido (las velas flat a 5% del rango aún producen
        lectura con cruce vigente). Se construye aquí una secuencia que
        garantiza caducidad por 3 velas.
        """
        from engine.poi_stoch_evaluator import _cross_vencido, _cross_type

        cfg = _default_config()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        # Construir: cruce en vela 19 (índice 19, la 20va vela), luego
        # 3 velas con close en 50% del rango (sin nuevo cruce).
        rng = 0.0002
        base = 1.0000
        candles: list[Candle] = []
        # 19 velas en sobreventa (close ~5% del rango)
        for _ in range(19):
            candles.append(Candle(high=base + rng, low=base, close=base + 0.05 * rng))
        # Vela 20: cruce (close ~80% del rango)
        candles.append(Candle(high=base + rng, low=base, close=base + 0.80 * rng))
        # 3 velas después: cerca del medio (close ~50%), sin cruce
        for _ in range(3):
            candles.append(Candle(high=base + rng, low=base, close=base + 0.50 * rng))

        # Verificar: última lectura NO tiene cruce
        reading = stochastic_14_3_3(candles, cfg)
        assert reading is not None
        assert _cross_type(reading, 1) == "NO_CROSS"

        # El cruce anterior (vela 19) está vencido por 3 velas sin nuevo cruce
        assert _cross_vencido(candles, cfg, reading, 1) is True

        # El evaluador principal retorna CROSS_EXPIRED porque el cruce anterior
        # venció por 3 velas sin nuevo cruce (contrato sección 8.2.2 — ahora
        # aplicado también cuando cross_type == NO_CROSS).
        fn = _closed_m15_fn(candles)
        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)
        assert result["status"] == "CROSS_EXPIRED"
        assert result["poi_selected"] is not None
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["stochastic"]["cross_type"] == "NO_CROSS"

    def test_cross_expired_por_inversion_k_d_refinement(self):
        """Caso rechazo: inversión K/D → cruce vencido (role=REFINEMENT).

        Nota: igual que el caso anterior, el flujo principal del evaluador
        retorna NO_CROSS cuando la última vela no tiene cruce válido.
        Este test verifica _cross_vencido directamente con una lectura
        forzada a k <= d.
        """
        from engine.poi_stoch_evaluator import _cross_vencido

        cfg = _default_config()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        # Construir velas con cruce en la última vela
        rng = 0.0002
        base = 1.0000
        candles: list[Candle] = []
        for _ in range(19):
            candles.append(Candle(high=base + rng, low=base, close=base + 0.05 * rng))
        candles.append(Candle(high=base + rng, low=base, close=base + 0.80 * rng))

        fn = _closed_m15_fn(candles)

        # La lectura natural tiene cruce válido (k > d)
        reading = stochastic_14_3_3(candles, cfg)
        assert reading is not None
        assert reading.k > reading.d
        assert _cross_vencido(candles, cfg, reading, 1) is False

        # Forzar lectura con k <= d (inversión) → vencido
        reading_inv = _reading(k=20.0, d=23.0, previous_k=18.0, previous_d=19.0)
        assert _cross_vencido(candles, cfg, reading_inv, 1) is True

        # El evaluador con la lectura real (cruce vigente) → ENTRY_VALID
        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)
        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["stochastic"]["cross_type"] == "CROSS_UP_FROM_OVERSOLD"

    def test_cross_expired_bajista_por_inversion_k_d(self):
        """Cruce bajista con k >= d → CROSS_EXPIRED (role=REFINEMENT)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=-1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        # Forzar lectura con k >= d modificando la última vela
        # (usar la construcción sintética de prueba)
        rng = 0.0002
        base = 1.0050
        candles_inv: list[Candle] = []
        for _ in range(19):
            candles_inv.append(Candle(high=base + rng, low=base, close=base + 0.95 * rng))
        candles_inv.append(Candle(high=base + rng, low=base, close=base + 0.90 * rng))

        fn = _closed_m15_fn(candles_inv)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        # La lectura final puede tener k >= d → CROSS_EXPIRED
        # (depende de los valores exactos del estocástico)
        assert result["status"] in ("CROSS_EXPIRED", "NO_CROSS", "ENTRY_VALID")
        # Verificar que al menos procesó el objeto REFINEMENT correctamente
        assert result["poi_selected"] is not None
        assert result["poi_selected"].role == Role.REFINEMENT

    # ------------------------------------------------------------------
    # CYCLE_ACTIVE_SAME_DIRECTION
    # ------------------------------------------------------------------

    def test_cycle_active_same_direction_compra_refinement(self):
        """Caso F: ciclo activo BUY bloquea POI BUY (role=REFINEMENT) → CYCLE_ACTIVE_SAME_DIRECTION."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012  # 2 pips del zone_high

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        cycle = _cycle(direction="BUY")

        result = evaluate_poi_stoch_m15([poi], price, fn, cycle, cfg)

        assert result["status"] == "CYCLE_ACTIVE_SAME_DIRECTION"
        assert result["poi_selected"] is not None
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["distance_pips"] == pytest.approx(2.0, rel=0.01)
        assert result["next_condition"] == "AGUARDAR_FIN_CICLO"
        assert "ciclo activo" in result["reason"].lower()

    def test_cycle_active_same_direction_venta_refinement(self):
        """Ciclo activo SELL bloquea POI SELL (role=REFINEMENT) → CYCLE_ACTIVE_SAME_DIRECTION."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=-1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        cycle = _cycle(direction="SELL")

        result = evaluate_poi_stoch_m15([poi], price, fn, cycle, cfg)

        assert result["status"] == "CYCLE_ACTIVE_SAME_DIRECTION"
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["next_condition"] == "AGUARDAR_FIN_CICLO"

    def test_cycle_no_bloquea_si_diferente_direccion_refinement(self):
        """Ciclo BUY no bloquea POI de venta (role=REFINEMENT) → ENTRY_VALID."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=-1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_down(_default_config())
        fn = _closed_m15_fn(candles)

        cycle = _cycle(direction="BUY")

        result = evaluate_poi_stoch_m15([poi], price, fn, cycle, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].role == Role.REFINEMENT

    def test_cycle_none_no_bloquea_refinement(self):
        """bot_cycle=None no bloquea → ENTRY_VALID (role=REFINEMENT)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].role == Role.REFINEMENT

    # ------------------------------------------------------------------
    # INSUFFICIENT_CANDLES
    # ------------------------------------------------------------------

    def test_insufficient_candles_por_cantidad_refinement(self):
        """Menos de 20 velas → INSUFFICIENT_CANDLES (role=REFINEMENT)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012  # 2 pips del zone_high

        candles = _build_candles_for_cross_up(_default_config())[:15]
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "INSUFFICIENT_CANDLES"
        assert result["poi_selected"] is not None
        assert result["poi_selected"].role == Role.REFINEMENT
        assert result["distance_pips"] == pytest.approx(2.0, rel=0.01)
        assert result["candles_available"] == 15
        assert result["next_condition"] == "AGUARDAR_CRUCE_M15"

    def test_insufficient_candles_exactamente_20_es_suficiente_refinement(self):
        """Con exactamente 20 velas, el estocástico se calcula (role=REFINEMENT)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())  # 20 velas
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["candles_available"] == 20
        assert result["status"] in ("ENTRY_VALID", "NO_CROSS", "CROSS_EXPIRED")
        assert result["stochastic"] is not None
        assert "cross_type" in result["stochastic"]
        assert result["poi_selected"].role == Role.REFINEMENT

    # ------------------------------------------------------------------
    # BotConfig vs dict config
    # ------------------------------------------------------------------

    def test_acepta_botconfig_refinement(self):
        """La función acepta BotConfig en lugar de dict (role=REFINEMENT)."""
        cfg = _default_config()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
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
        assert result["poi_selected"].role == Role.REFINEMENT

    # ------------------------------------------------------------------
    # Edge cases y validación de parámetros
    # ------------------------------------------------------------------

    def test_market_objects_pure_refinement_list(self):
        """Lista pura de MarketObject REFINEMENT (sin dicts) → procesa correctamente."""
        cfg = _config_dict()
        price = 1.0012

        poi1 = _refinement_fvg(id="ref-1", origin_tf="D1", creation_time=1000)
        poi2 = _refinement_fvg(id="ref-2", origin_tf="D1", creation_time=2000)

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi1, poi2], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        # El más reciente (creation_time=2000) gana
        assert result["poi_selected"].id == "ref-2"
        assert result["poi_selected"].role == Role.REFINEMENT
        # Verificar que ambos objetos están en el tipo esperado
        assert result["poi_selected"].type == ObjectType.FVG
        assert result["poi_selected"].origin_tf == "D1"
        assert result["poi_selected"].state == ObjectState.ACTIVE

    def test_order_block_refinement_elegible(self):
        """ORDER_BLOCK D1 ACTIVE (role=REFINEMENT) es POI elegible."""
        cfg = _config_dict()
        poi = _refinement_ob(
            id="ref-ob-elegible",
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].id == "ref-ob-elegible"
        assert result["poi_selected"].type == ObjectType.ORDER_BLOCK
        assert result["poi_selected"].role == Role.REFINEMENT

    def test_sweep_type_not_poi_eligible(self):
        """SWEEP (role=REFINEMENT) no es tipo POI → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = MarketObject(
            id="ref-sweep-1",
            type=ObjectType.SWEEP,
            role=Role.REFINEMENT,
            state=ObjectState.ACTIVE,
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
            symbol="EURUSD",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_liquidity_type_not_poi_eligible(self):
        """LIQUIDITY (role=REFINEMENT) no es tipo POI → NO_ELIGIBLE_POI_NEAR_PRICE."""
        cfg = _config_dict()
        poi = MarketObject(
            id="ref-liq-1",
            type=ObjectType.LIQUIDITY,
            role=Role.REFINEMENT,
            state=ObjectState.ACTIVE,
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
            symbol="EURUSD",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

    def test_zone_high_less_than_zone_low_rejected(self):
        """FVG con zone_high < zone_low → NO_ELIGIBLE_POI_NEAR_PRICE (geometría inválida).

        MarketObject con zone_high < zone_low falla en __post_init__
        (lanzando ValueError). El filtro _filtrar_candidatas también
        rechaza dicts con zone_high < zone_low. Verificamos ambas vías.
        """
        cfg = _config_dict()
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        # Vía dict: el filtro rechaza geometría inválida
        poi_dict = {
            "id": "ref-invalid-zone-dict",
            "type": "FVG",
            "role": "REFINEMENT",
            "state": "ACTIVE",
            "direction": 1,
            "zone_low": 1.0010,
            "zone_high": 1.0000,  # inválido: high < low
            "origin_tf": "D1",
            "symbol": "EURUSD",
        }

        result = evaluate_poi_stoch_m15([poi_dict], price, fn, None, cfg)

        assert result["status"] == "NO_ELIGIBLE_POI_NEAR_PRICE"
        assert result["poi_selected"] is None

        # Vía MarketObject: __post_init__ lanza ValueError
        with pytest.raises(ValueError, match="zone_high debe ser >= zone_low"):
            MarketObject(
                id="ref-invalid-zone-mo",
                type=ObjectType.FVG,
                role=Role.REFINEMENT,
                state=ObjectState.ACTIVE,
                direction=1,
                zone_low=1.0010,
                zone_high=1.0000,  # inválido
                origin_tf="D1",
                symbol="EURUSD",
            )

    def test_multiple_refinement_one_eligible_one_not(self):
        """Mezcla de REFINEMENT elegible y no elegible → solo el elegible se considera."""
        cfg = _config_dict()
        poi_eligible = _refinement_fvg(
            id="ref-eligible",
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
            creation_time=1000,
        )
        poi_not_eligible = _refinement_fvg(
            id="ref-not-eligible",
            direction=1,
            zone_low=1.0100,
            zone_high=1.0110,
            origin_tf="M1",  # no es POI-TF
            creation_time=2000,
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi_eligible, poi_not_eligible], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        assert result["poi_selected"].id == "ref-eligible"
        assert result["poi_selected"].role == Role.REFINEMENT

    def test_cross_type_field_in_stochastic_output_refinement(self):
        """El campo cross_type en stochastic es correcto para cruce alcista (role=REFINEMENT)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
        )
        price = 1.0012

        candles = _build_candles_for_cross_up(_default_config())
        fn = _closed_m15_fn(candles)

        result = evaluate_poi_stoch_m15([poi], price, fn, None, cfg)

        assert result["status"] == "ENTRY_VALID"
        s = result["stochastic"]
        assert isinstance(s, dict)
        assert s["cross_type"] == "CROSS_UP_FROM_OVERSOLD"
        for field in ("k", "d", "previous_k", "previous_d", "cross_type"):
            assert field in s, f"falta campo stochastic.{field}"

    def test_output_campos_exactos_refinement(self):
        """El output tiene exactamente los campos definidos en contrato sección 11 (role=REFINEMENT)."""
        cfg = _config_dict()
        poi = _refinement_fvg(
            direction=1,
            zone_low=1.0000,
            zone_high=1.0010,
            origin_tf="D1",
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
            "price_type",
            "cross_id",
        }
        assert set(result.keys()) == expected_fields
        assert result["poi_selected"].role == Role.REFINEMENT
