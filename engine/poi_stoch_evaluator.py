"""POI canónica + estocástico M15 — evaluador simplificado.

Consume POI canónicas (FVG/OB) y velas M15 cerradas, produce un dict de
decisión de entrada según el contrato ``docs/contratos/CONTRATO_POI_STOCH_M15_V1.md``.

El evaluador es puro (solo lectura) e idempotente: reevaluar con los mismos
argumentos produce el mismo ``status``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from mechanical_bot.core import BotConfig, Candle, StochasticReading, stochastic_14_3_3
from engine.market_object import MarketObject, ObjectType, Role, ObjectState


def _config_botconfig(config: object) -> BotConfig:
    """Convierte un config genérico en un ``BotConfig`` compatible con
    ``stochastic_14_3_3`` (que exige ese tipo en su firma).

    El contrato del evaluador pide que ``config`` contenga los atributos
    symbol, k_period, k_smoothing, d_period, oversold, overbought,
    pip_size, tolerance_pips.  Los coerciona a ``BotConfig`` sin modificar
    ``core.py``.
    """
    return BotConfig(
        symbol=getattr(config, "symbol", "EURUSD"),
        k_period=getattr(config, "k_period", 14),
        k_smoothing=getattr(config, "k_smoothing", 3),
        d_period=getattr(config, "d_period", 3),
        oversold=getattr(config, "oversold", 20.0),
        overbought=getattr(config, "overbought", 80.0),
        pip_size=getattr(config, "pip_size", 0.0001),
        tolerance_pips=getattr(config, "tolerance_pips", 5.0),
    )


def _ensurar_esperado(candles: list[Candle], indice: int) -> Candle:
    """Devuelve la vela en ``indice`` o raise si no existe."""
    if indice >= len(candles) or indice < 0:
        raise IndexError(f"vela {indice} fuera de rango (total {len(candles)})")
    return candles[indice]


def _lectura_estocastica_por_vela(
    candles: list[Candle],
    config: BotConfig,
    indice_vela: int,
) -> StochasticReading | None:
    """Calcula un ``StochasticReading`` usando únicamente las velas hasta
    e incluyendo ``candles[indice_vela]`` (la vela más reciente cerrada
    es ``indice_vela``).

    Esto permite inspeccionar los valores de k/d en cada vela individual
    para la verificación de caducidad por ventana de 3 velas.
    """
    if indice_vela < 0:
        return None
    sub_candles = candles[: indice_vela + 1]
    if len(sub_candles) < 20:  # required_candles mínimo = k_period + k_smoothing + d_period
        return None
    return stochastic_14_3_3(sub_candles, config)


def _hubo_cruce_valido_en_vela(
    candles: list[Candle],
    config: BotConfig,
    indice_vela: int,
    direction: int,
) -> bool:
    """Devuelve True si en la vela ``indice_vela`` (cerrada) se produjo un
    cruce válido del tipo requerido para ``direction``.

    Para direction=+1 (COMPRA): cruce alcista desde sobreventa (20.0).
    Para direction=-1 (VENTA): cruce bajista desde sobrecompra (80.0).
    """
    lectura = _lectura_estocastica_por_vela(candles, config, indice_vela)
    if lectura is None:
        return False

    if direction == 1:
        return lectura.crossed_up_from_oversold(20.0)
    if direction == -1:
        return lectura.crossed_down_from_overbought(80.0)
    return False


def _cross_type(reading: StochasticReading, direction: int) -> str:
    """Aplica las reglas de sección 6.1/6.2 del contrato sobre el
    ``StochasticReading`` y retorna el ``cross_type`` enumerado.

    El cruce debe ser coherente con la dirección de la POI: un cruce
    alcista no es válido para una POI bajista, y viceversa.
    """
    if direction == 1:
        if reading.crossed_up_from_oversold(20.0):
            return "CROSS_UP_FROM_OVERSOLD"
        return "NO_CROSS"
    if direction == -1:
        if reading.crossed_down_from_overbought(80.0):
            return "CROSS_DOWN_FROM_OVERBOUGHT"
        return "NO_CROSS"
    return "NO_CROSS"


def _cross_vencido(
    candles: list[Candle],
    config: BotConfig,
    reading: StochasticReading,
    direction: int,
) -> bool:
    """Verifica si el cruce estocástico venció según sección 8 del contrato.

    Los dos mecanismos de caducidad:

    1. Inversión K/D: para cruce alcista (k > d), si k <= d; para cruce
       bajista (k < d), si k >= d.
    2. Tres velas consecutivas sin nuevo cruce válido: se recorren las
       últimas 3 velas (candles[-3], candles[-2], candles[-1]) y si en
       ninguna de ellas hubo cruce válido del tipo requerido, el cruce
       anterior vence.

    Si no hay suficientes velas históricas para verificar (menos de 3
    velas además de la del cruce), no se puede probar la caducidad y
    se considera que el cruce está vigente (retorna False).
    """
    # Mecanismo 1: inversión de relación K/D en la vela actual
    if direction == 1:
        if reading.k <= reading.d:
            return True
    elif direction == -1:
        if reading.k >= reading.d:
            return True

    # Mecanismo 2: tres velas consecutivas sin nuevo cruce válido
    # Necesitamos al menos 3 velas adicionales para la verificación
    if len(candles) < 4:
        return False

    # Verificar las últimas 3 velas (candles[-3], candles[-2], candles[-1])
    # Si en ninguna hubo cruce válido, el cruce anterior vence.
    ultimas_indices = [len(candles) - 3, len(candles) - 2, len(candles) - 1]
    for idx in ultimas_indices:
        if _hubo_cruce_valido_en_vela(candles, config, idx, direction):
            return False  # Hay un nuevo cruce válido, no vencido

    return True  # Ninguna de las 3 velas tenía cruce válido


def _distance_pips(p: MarketObject | dict, price: float, pip_size: float = 0.0001) -> float:
    """Calcula la distancia en pips entre el precio actual y la POI.

    Si el precio está dentro de la zona [zone_low, zone_high], la distancia
    es 0.0. De lo contrario, es la mínima distancia a los bordes dividida
    por el pip_size.
    """
    if isinstance(p, dict):
        zone_low = p["zone_low"]
        zone_high = p["zone_high"]
    else:
        zone_low = p.zone_low
        zone_high = p.zone_high

    if zone_low <= price <= zone_high:
        return 0.0

    dist_low = abs(price - zone_low)
    dist_high = abs(price - zone_high)
    return min(dist_low, dist_high) / pip_size


def _direction_string(direction: int) -> str:
    """Convierte direction entero (+1/-1) a string ("BUY"/"SELL")."""
    if direction == 1:
        return "BUY"
    if direction == -1:
        return "SELL"
    return "UNKNOWN"


def _poi_selected(cercanas: list[object], price: float, pip_size: float = 0.0001) -> MarketObject | dict[str, Any] | None:
    """Selecciona la POI más cercana al precio según sección 9 del contrato.

    Criterio principal: menor distance_pips.
    Desempate: creation_time más reciente (mayor valor).
    """
    if not cercanas:
        return None

    # Calcular distancia para cada POI y encontrar el mínimo
    candidatos_con_dist = []
    for p in cercanas:
        dist = _distance_pips(p, price, pip_size)
        candidatos_con_dist.append((p, dist))

    # Ordenar por distancia (ascendente), luego por creation_time (descendente)
    def clave(item):
        p, dist = item
        if isinstance(p, dict):
            creation = p.get("creation_time")
            if creation is None:
                creation = ""
            # Normalizar a comparable: si es string ISO, usar directamente
            return (dist, -_comparar_creation(creation))
        else:
            creation = p.creation_time
            if creation is None:
                creation = ""
            return (dist, -_comparar_creation(creation))

    candidatos_con_dist.sort(key=clave)
    return candidatos_con_dist[0][0]


def _comparar_creation(creation) -> float:
    """Convierte creation_time a un valor comparable para desempate.

    Intenta convertir a timestamp numérico; si no es posible, usa 0.
    """
    if creation is None or creation == "":
        return 0.0
    if isinstance(creation, (int, float)):
        return float(creation)
    if isinstance(creation, str):
        try:
            dt = datetime.fromisoformat(creation.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0
    try:
        return float(creation)
    except (TypeError, ValueError):
        return 0.0


def _stochastic_dict(
    reading: StochasticReading | None,
    cross_type: str,
) -> dict:
    """Construye el dict ``stochastic`` de salida según sección 11.3.

    Si reading es None (no hay suficientes velas), retorna solo cross_type.
    """
    if reading is None:
        return {"cross_type": cross_type}

    return {
        "k": reading.k,
        "d": reading.d,
        "previous_k": reading.previous_k,
        "previous_d": reading.previous_d,
        "cross_type": cross_type,
    }


def _filtrar_candidatas(market_objects: list[object]) -> list[object]:
    """Filtra market_objects para obtener POI elegibles (sección 2).

    Condiciones:
    - type in (ObjectType.FVG, ObjectType.ORDER_BLOCK)
    - role == Role.POI
    - state in (ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED)
    """
    elegibles = []
    for obj in market_objects:
        # Manejar tanto objetos MarketObject como dicts
        if isinstance(obj, dict):
            obj_type = obj.get("type")
            obj_role = obj.get("role")
            obj_state = obj.get("state")
        else:
            obj_type = obj.type
            obj_role = obj.role
            obj_state = obj.state

        # Normalizar a enum si es string
        if isinstance(obj_type, str):
            obj_type = ObjectType(obj_type)
        if isinstance(obj_role, str):
            obj_role = Role(obj_role)
        if isinstance(obj_state, str):
            obj_state = ObjectState(obj_state)

        if obj_type in (ObjectType.FVG, ObjectType.ORDER_BLOCK) and \
           obj_role == Role.POI and \
           obj_state in (ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED):
            elegibles.append(obj)

    return elegibles


def _filtrar_operables(candidatas: list[object]) -> list[object]:
    """Filtra POI con dirección operable (+1 o -1), descarta direction=0."""
    operables = []
    for p in candidatas:
        if isinstance(p, dict):
            direction = p.get("direction", 0)
        else:
            direction = p.direction
        if direction in (1, -1):
            operables.append(p)
    return operables


def _filtrar_cercanas(operables: list[object], price: float, tolerance_pips: float, pip_size: float = 0.0001) -> list[object]:
    """Filtra POI que están en proximidad al precio (sección 4)."""
    cercanas = []
    for p in operables:
        dist = _distance_pips(p, price, pip_size)
        if dist <= tolerance_pips:
            cercanas.append(p)
    return cercanas


def evaluate_poi_stoch_m15(
    market_objects: list,
    price: float,
    closed_m15_candles_fn: Callable,
    bot_cycle: object | None,
    config: object,
) -> dict:
    """Evaluador POI + estocástico M15.

    Args:
        market_objects: lista de MarketObject (o dicts con campos equivalentes).
        price: precio actual (float).
        closed_m15_candles_fn: función que devuelve list[Candle] al ser llamada.
        bot_cycle: Cycle o None para verificar ciclo activo.
        config: objeto de configuración con atributos:
            symbol, k_period, k_smoothing, d_period, oversold, overbought,
            pip_size, tolerance_pips.

    Returns:
        dict con campos: decision_time, status, reason, poi_selected,
        distance_pips, price, stochastic, candles_available, next_condition.
    """
    # Obtener parámetros de config
    symbol = getattr(config, "symbol", "EURUSD")
    pip_size = getattr(config, "pip_size", 0.0001)
    tolerance_pips = getattr(config, "tolerance_pips", 5.0)

    decision_time = datetime.now(timezone.utc)

    # Paso 1: Obtener POI candidatas
    candidatas = _filtrar_candidatas(market_objects)
    if not candidatas:
        return _build_result(
            decision_time=decision_time,
            status="NO_ELIGIBLE_POI_NEAR_PRICE",
            reason="No hay POI elegibles (FVG/ORDER_BLOCK con rol POI y estado ACTIVE/PARTIALLY_MITIGATED)",
            poi_selected=None,
            distance_pips=None,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=0,
            next_condition="SIN_CONDICION",
        )

    # Paso 2: Filtrar por dirección operable
    operables = _filtrar_operables(candidatas)
    if not operables:
        return _build_result(
            decision_time=decision_time,
            status="NO_ELIGIBLE_POI_NEAR_PRICE",
            reason="No hay POI con dirección operable (+1 o -1)",
            poi_selected=None,
            distance_pips=None,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=0,
            next_condition="SIN_CONDICION",
        )

    # Paso 3: Filtrar por proximidad
    cercanas = _filtrar_cercanas(operables, price, tolerance_pips, pip_size)
    if not cercanas:
        return _build_result(
            decision_time=decision_time,
            status="NO_ELIGIBLE_POI_NEAR_PRICE",
            reason="No hay POI elegible en proximidad (dentro de la zona o dentro de 5 pips)",
            poi_selected=None,
            distance_pips=None,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=0,
            next_condition="AGUARDAR_POI_EN_ZONA",
        )

    # Paso 4: Seleccionar POI más cercana
    poi = _poi_selected(cercanas, price, pip_size)
    assert poi is not None, "poi_selected no debería ser None cuando hay cercanas"
    if isinstance(poi, dict):
        distance_pips = _distance_pips(poi, price, pip_size)
        direction = poi.get("direction", 0)
    else:
        distance_pips = _distance_pips(poi, price, pip_size)
        direction = poi.direction

    # Validar direction (debe ser +1 o -1, ya que filtramos operables)
    if direction not in (1, -1):
        return _build_result(
            decision_time=decision_time,
            status="INVALID_DIRECTION",
            reason=f"La POI seleccionada tiene direction={direction}, no operable",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=0,
            next_condition="SIN_CONDICION",
        )

    bot_config = _config_botconfig(config)

    # Paso 5: Obtener velas M15 y calcular estocástico
    candles = closed_m15_candles_fn(symbol, count=80)
    candles_available = len(candles)

    if candles_available < 20:
        return _build_result(
            decision_time=decision_time,
            status="INSUFFICIENT_CANDLES",
            reason=f"Se requieren al menos 20 velas M15; disponibles {candles_available}",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=candles_available,
            next_condition="AGUARDAR_CRUCE_M15",
        )

    reading = stochastic_14_3_3(candles, bot_config)
    if reading is None:
        return _build_result(
            decision_time=decision_time,
            status="INSUFFICIENT_CANDLES",
            reason="stochastic_14_3_3 no pudo calcularse con las velas disponibles",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=candles_available,
            next_condition="AGUARDAR_CRUCE_M15",
        )

    # Paso 6: Evaluar cruce
    cross_type = _cross_type(reading, direction)

    if cross_type == "NO_CROSS":
        return _build_result(
            decision_time=decision_time,
            status="NO_CROSS",
            reason=f"El estocástico no presenta cruce válido para la dirección POI (direction={direction})",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic=_stochastic_dict(reading, cross_type),
            candles_available=candles_available,
            next_condition="AGUARDAR_CRUCE_M15",
        )

    # Paso 7: Verificar caducidad del cruce
    if _cross_vencido(candles, bot_config, reading, direction):
        return _build_result(
            decision_time=decision_time,
            status="CROSS_EXPIRED",
            reason="El cruce estocástico venció (inversión K/D o 3 velas sin nuevo cruce válido)",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic=_stochastic_dict(reading, cross_type),
            candles_available=candles_available,
            next_condition="AGUARDAR_CRUCE_M15",
        )

    # Paso 8: Verificar ciclo activo
    if bot_cycle is not None:
        cycle_direction = getattr(bot_cycle, "direction", None)
        if cycle_direction is not None:
            direction_str = _direction_string(direction)
            if cycle_direction.upper() == direction_str.upper():
                return _build_result(
                    decision_time=decision_time,
                    status="CYCLE_ACTIVE_SAME_DIRECTION",
                    reason="Existe un ciclo activo en la misma dirección",
                    poi_selected=poi,
                    distance_pips=distance_pips,
                    price=price,
                    stochastic=_stochastic_dict(reading, cross_type),
                    candles_available=candles_available,
                    next_condition="AGUARDAR_FIN_CICLO",
                )

    # Paso 9: Entrada válida
    poi_type_label = poi.type.value if isinstance(poi, MarketObject) else poi.get("type", "DESCONOCIDO")
    return _build_result(
        decision_time=decision_time,
        status="ENTRY_VALID",
        reason=f"Entrada válida: POI {poi_type_label} en proximidad con cruce estocástico vigente",
        poi_selected=poi,
        distance_pips=distance_pips,
        price=price,
        stochastic=_stochastic_dict(reading, cross_type),
        candles_available=candles_available,
        next_condition="SIN_CONDICION",
    )


def _build_result(
    decision_time: datetime,
    status: str,
    reason: str,
    poi_selected: object | None,
    distance_pips: float | None,
    price: float,
    stochastic: dict,
    candles_available: int,
    next_condition: str,
) -> dict:
    """Construye el dict de resultado final."""
    return {
        "decision_time": decision_time,
        "status": status,
        "reason": reason,
        "poi_selected": poi_selected,
        "distance_pips": distance_pips,
        "price": price,
        "stochastic": stochastic,
        "candles_available": candles_available,
        "next_condition": next_condition,
    }
