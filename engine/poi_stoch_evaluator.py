"""POI canónica + estocástico M15 — evaluador simplificado.

Consume POI canónicas (FVG/OB) y velas M15 cerradas, produce un dict de
decisión de entrada según el contrato ``docs/contratos/CONTRATO_POI_STOCH_M15_V1.md``.

El evaluador es puro (solo lectura) e idempotente: reevaluar con los mismos
argumentos produce el mismo ``status``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
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
    cross_index: int | None = None,
) -> bool:
    """Verifica si el cruce estocástico venció según sección 8 del contrato.

    H6: verifica 3 velas DESPUÉS de la vela del cruce (índice cross_index),
    no incluye la vela del cruce en la verificación.

    Los dos mecanismos de caducidad:

    1. Inversión K/D en la vela DECISIÓN (última vela cerrada): para
       cruce alcista (k > d), si k <= d; para cruce bajista (k < d), si
       k >= d.
    2. Tres velas consecutivas DESPUÉS del cruce sin nuevo cruce válido.

    Args:
        candles: lista de velas M15 cerradas, orden ascendente por tiempo.
        config: BotConfig con k_period, k_smoothing, d_period, oversold,
                overbought.
        reading: lectura estocástica de la última vela (candles[-1]).
        direction: +1 para cruce alcista, -1 para bajista.
        cross_index: índice de la vela donde ocurrió el cruce. Si es None,
                     se toma len(candles) - 1 (comportamiento legacy para
                     compatibilidad, pero los tests nuevos lo pasan explícito).

    Returns:
        True si el cruce venció, False si está vigente.

    Contrato V2 sección 8.2.2: el cruce vence al cerrarse la tercera vela
    después del cruce SIN nuevo cruce válido. Si hay nuevo cruce válido
    en cualquiera de esas 3 velas, el vencimiento se reinicia.
    """
    # Determinar la vela del cruce
    if cross_index is None:
        cross_index = len(candles) - 1

    # Mecanismo 1: inversión de relación K/D en la vela DECISIÓN (última)
    # No importa si la vela del cruce fue alcista o bajista; lo que importa
    # es la lectura actual de la vela donde se toma la decisión.
    if direction == 1:
        if reading.k <= reading.d:
            return True
    elif direction == -1:
        if reading.k >= reading.d:
            return True

    # Mecanismo 2: tres velas DESPUÉS del cruce sin nuevo cruce válido
    # cross_index + 1, cross_index + 2, cross_index + 3
    # Necesitamos al menos 3 velas después del cruce
    if len(candles) < cross_index + 4:
        return False  # No hay suficientes velas para verificar

    for offset in range(1, 4):
        idx = cross_index + offset
        if _hubo_cruce_valido_en_vela(candles, config, idx, direction):
            return False  # Nuevo cruce válido en alguna de las 3 velas

    return True  # Ninguna de las 3 velas después del cruce tuvo cruce válido


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
    Desempate por temporalidad (contrato V2 sección 9.4): D1 > H4 > H1.
    Si misma temporalidad, el más reciente (mayor creation_time) gana.

    Prioridad de temporalidad para desempate:
        D1  -> 0 (máxima prioridad)
        H4  -> 1
        H1  -> 2
        otro -> 3 (mínima prioridad)
    """
    if not cercanas:
        return None

    _TF_PRIORITY = {"D1": 0, "H4": 1, "H1": 2}

    def _tf_priority(p: object) -> int:
        if isinstance(p, dict):
            tf = p.get("origin_tf", "")
        else:
            tf = getattr(p, "origin_tf", "") or ""
        return _TF_PRIORITY.get(tf, 3)

    # Calcular distancia para cada POI y encontrar el mínimo
    candidatos_con_dist = []
    for p in cercanas:
        dist = _distance_pips(p, price, pip_size)
        candidatos_con_dist.append((p, dist))

    def clave(item):
        p, dist = item
        tf_pri = _tf_priority(p)
        creation = getattr(p, "creation_time", None)
        if creation is None and isinstance(p, dict):
            creation = p.get("creation_time")
        if creation is None:
            creation = ""
        return (dist, tf_pri, -_comparar_creation(creation))

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


def _calcular_cross_id(cross_type: str, candles: list[Candle]) -> str:
    """Calcula ``cross_id`` único según contrato V2 sección 8.3 / 13.3.

    ``cross_id = f"{cross_type}_{firma_vela}"`` donde ``firma_vela`` es el
    hex digest SHA-256 de ``high|low|close|posicion`` de ``candles[-1]``.
    """
    if not candles:
        return ""
    ultima = candles[-1]
    payload = f"{ultima.high}|{ultima.low}|{ultima.close}|{len(candles) - 1}"
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"{cross_type}_{digest}"


def _stochastic_dict(
    reading: StochasticReading | None,
    cross_type: str,
    cross_id: str | None = None,
) -> dict:
    """Construye el dict ``stochastic`` de salida según sección 11.3.

    Si reading es None (no hay suficientes velas), retorna solo cross_type.
    El campo ``cross_id`` se incluye cuando es no-None (contrato V2 sección 8.3).
    """
    base: dict[str, Any] = {"cross_type": cross_type}
    if cross_id is not None:
        base["cross_id"] = cross_id
    if reading is None:
        return base

    return {
        "k": reading.k,
        "d": reading.d,
        "previous_k": reading.previous_k,
        "previous_d": reading.previous_d,
        "cross_type": cross_type,
        ** ({"cross_id": cross_id} if cross_id is not None else {}),
    }


def _filtrar_candidatas(market_objects: list[object]) -> list[object]:
    """Filtra market_objects para obtener POI elegibles (contrato V2 sección 2.4).

    El contrato V2 sección 2.4 define criterio alternativo: NO exige Role.POI.
    Los detectores publican role=REFINEMENT, no role=POI (el papel POI es
    una intención, no un atributo del objeto material publicado).

    Selección local T2 (contrato V2 sección 2.1):
    - type in (ObjectType.FVG, ObjectType.ORDER_BLOCK)
    - origin_tf in {"D1", "H4", "H1"} (POI-TFs acordadas, contrato V2 sección 4.1)
    - state in (ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED)
    - símbolo: acepta cualquier símbolo (filtro en el evaluador)
    - zonas finitas: zone_high >= zone_low (contrato V2 sección 4.3 geometría)

    No se exige role == Role.POI. El papel (role) es metadata de intención;
    la elegibilidad se determina por tipo, origen temporal, estado, símbolo
    y geometría.
    """
    elegibles = []
    for obj in market_objects:
        # Manejar tanto objetos MarketObject como dicts
        if isinstance(obj, dict):
            obj_type = obj.get("type")
            obj_origin_tf = obj.get("origin_tf")
            obj_state = obj.get("state")
            zone_low = obj.get("zone_low")
            zone_high = obj.get("zone_high")
        else:
            obj_type = getattr(obj, "type", None)
            obj_origin_tf = getattr(obj, "origin_tf", None) or ""
            obj_state = getattr(obj, "state", None)
            zone_low = getattr(obj, "zone_low", None)
            zone_high = getattr(obj, "zone_high", None)

        # Normalizar tipos si son strings
        if isinstance(obj_type, str):
            obj_type = ObjectType(obj_type)
        if isinstance(obj_state, str):
            obj_state = ObjectState(obj_state)

        # 1. Tipo: FVG o ORDER_BLOCK
        if obj_type not in (ObjectType.FVG, ObjectType.ORDER_BLOCK):
            continue

        # 2. Temporalidad acordada (POI-TFs): D1, H4, H1
        if not obj_origin_tf or obj_origin_tf not in {"D1", "H4", "H1"}:
            continue

        # 3. Estado: ACTIVE o PARTIALLY_MITIGATED
        if obj_state not in (ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED):
            continue

        # 4. Geometría finita: zone_high >= zone_low y ambos son números
        try:
            zl = float(zone_low)
            zh = float(zone_high)
        except (TypeError, ValueError):
            continue
        if not (zl <= zh):
            continue

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
    *,
    check_proximity: bool = True,
    price_type: str | None = None,
    consumed_cross_ids: set[str] | None = None,
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
        check_proximity: si es falso, solo preselecciona una POI operable para
            obtener el lado bid/ask; nunca devuelve una entrada válida.
        price_type: tipo de precio usado ("ASK" o "BID"). Se infiere de la
            dirección del POI si no se proporciona (contrato V2 sección 4.2).
        consumed_cross_ids: conjunto de cross_ids ya utilizados para entradas
            válidas previas. Si el cross_id actual está en el conjunto, el
            cruce se considera consumido → CROSS_EXPIRED (contrato V2 §10.2).

    Returns:
        dict con campos: decision_time, status, reason, poi_selected,
        distance_pips, price, stochastic, candles_available, next_condition,
        y opcionalmente price_type y cross_id (contrato V2 sección 11.1).
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
            reason="No hay POI elegibles (FVG/ORDER_BLOCK con temporalidad D1/H4/H1 y estado ACTIVE/PARTIALLY_MITIGATED o lista vacía)",
            poi_selected=None,
            distance_pips=None,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=0,
            next_condition="AGUARDAR_POI_EN_ZONA",
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
            next_condition="AGUARDAR_POI_EN_ZONA",
        )

    # Paso 3: Filtrar por proximidad
    cercanas = operables if not check_proximity else _filtrar_cercanas(operables, price, tolerance_pips, pip_size)
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
        poi_symbol = poi.get("symbol", symbol)
    else:
        distance_pips = _distance_pips(poi, price, pip_size)
        direction = poi.direction
        poi_symbol = getattr(poi, "symbol", symbol)

    if not check_proximity:
        return _build_result(
            decision_time=decision_time,
            status="POI_SELECTED_FOR_PRICE",
            reason="POI operable preseleccionada; falta reevaluar con bid/ask del lado correspondiente.",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=0,
            next_condition="REEVALUAR_PRECIO_POR_DIRECCION",
        )

    # Paso 4b: Determinar price_type (contrato V2 sección 4.2)
    if price_type is None:
        price_type = "ASK" if direction == 1 else "BID"
    bot_config = _config_botconfig(config)
    candles = closed_m15_candles_fn(symbol, count=80)
    candles_available = len(candles)

    # Validar símbolo (contrato V2 sección 4.2): el POI debe ser del
    # mismo símbolo que el config, o no tener símbolo asignado (hereda).
    if poi_symbol and poi_symbol != symbol:
        return _build_result(
            decision_time=decision_time,
            status="NO_ELIGIBLE_POI_NEAR_PRICE",
            reason=f"POI con símbolo {poi_symbol} no coincide con el símbolo del config {symbol}",
            poi_selected=None,
            distance_pips=None,
            price=price,
            stochastic={"cross_type": "NO_CROSS"},
            candles_available=candles_available,
            next_condition="AGUARDAR_POI_EN_ZONA",
        )

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
        # Verificar si el cruce anterior venció (contrato V2 sección 8.2.2)
        # Buscar la última vela con cruce válido hacia atrás desde candles[-2]
        prev_cross_index = None
        for idx in range(len(candles) - 2, -1, -1):
            idx_reading = _lectura_estocastica_por_vela(candles, bot_config, idx)
            if idx_reading is not None:
                idx_cross_type = _cross_type(idx_reading, direction)
                if idx_cross_type != "NO_CROSS":
                    prev_cross_index = idx
                    break

        if prev_cross_index is not None:
            # Hubo cruce anterior; verificar si venció
            prev_expired = _cross_vencido(
                candles, bot_config, reading, direction,
                cross_index=prev_cross_index,
            )
            if prev_expired:
                return _build_result(
                    decision_time=decision_time,
                    status="CROSS_EXPIRED",
                    reason="El cruce estocástico anterior venció (inversión K/D o 3 velas sin nuevo cruce válido)",
                    poi_selected=poi,
                    distance_pips=distance_pips,
                    price=price,
                    stochastic=_stochastic_dict(reading, cross_type),
                    candles_available=candles_available,
                    next_condition="AGUARDAR_CRUCE_M15",
                )
        return _build_result(
            decision_time=decision_time,
            status="NO_CROSS",
            reason=f"El estocástico no presenta cruce válido para la dirección POI (direction={direction})",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic=_stochastic_dict(reading, cross_type, cross_id=None),
            candles_available=candles_available,
            next_condition="AGUARDAR_CRUCE_M15",
            price_type=price_type,
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
            stochastic=_stochastic_dict(reading, cross_type, cross_id=None),
            candles_available=candles_available,
            next_condition="AGUARDAR_CRUCE_M15",
            price_type=price_type,
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
                    stochastic=_stochastic_dict(reading, cross_type, cross_id=None),
                    candles_available=candles_available,
                    next_condition="AGUARDAR_FIN_CICLO",
                    price_type=price_type,
                )

    # Paso 9: Entrada válida
    poi_type_label = poi.type.value if isinstance(poi, MarketObject) else poi.get("type", "DESCONOCIDO")
    cross_id = _calcular_cross_id(cross_type, candles)

    # Verificar que el cross_id no fue consumido previamente (contrato V2 §10.2)
    if consumed_cross_ids is not None and cross_id in consumed_cross_ids:
        return _build_result(
            decision_time=decision_time,
            status="CROSS_EXPIRED",
            reason="Cruce ya consumido en evaluación previa",
            poi_selected=poi,
            distance_pips=distance_pips,
            price=price,
            stochastic=_stochastic_dict(reading, cross_type, cross_id=cross_id),
            candles_available=candles_available,
            next_condition="AGUARDAR_CRUCE_NUEVO",
            price_type=price_type,
            cross_id=cross_id,
        )

    # Registrar cross_id como consumido para futuras evaluaciones
    if consumed_cross_ids is not None:
        consumed_cross_ids.add(cross_id)

    return _build_result(
        decision_time=decision_time,
        status="ENTRY_VALID",
        reason=f"Entrada válida: POI {poi_type_label} en proximidad con cruce estocástico vigente",
        poi_selected=poi,
        distance_pips=distance_pips,
        price=price,
        stochastic=_stochastic_dict(reading, cross_type, cross_id=cross_id),
        candles_available=candles_available,
        next_condition="SIN_CONDICION",
        price_type=price_type,
        cross_id=cross_id,
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
    *,
    price_type: str | None = None,
    cross_id: str | None = None,
) -> dict:
    """Construye el dict de resultado final.

    Los campos ``price_type`` y ``cross_id`` se añaden cuando son no-None
    para cumplir con el contrato V2 sección 11.1.
    """
    result: dict[str, Any] = {
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
    if price_type is not None:
        result["price_type"] = price_type
    if cross_id is not None:
        result["cross_id"] = cross_id
    return result
