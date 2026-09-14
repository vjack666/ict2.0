# CONTRATO_POI_STOCH_M15_V1.md

**Archivo:** `docs/contratos/CONTRATO_POI_STOCH_M15_V1.md`
**Versión:** 1.0
**Fecha:** 2026-09-14
**Autor:** D6 Research
**Misión:** MC-20260914-083000-poi-stoch-m15
**Propósito:** Especificación congelada de la estrategia POI canónica (FVG + OB) + estocástico M15. Los parámetros se fijan antes de evaluar resultados históricos.

---

## 1. Fuentes canónicas

| Entidad | Archivo de origen | Responsabilidad |
|---------|-------------------|-----------------|
| `MarketObject`, `ObjectType`, `Role`, `ObjectState` | `engine/market_object.py` | Definición de objetos, tipos, roles y estados. Incluye la tabla de transiciones `_ALLOWED_TRANSITIONS` y el conjunto `_TERMINAL_STATES = {INVALIDATED, EXPIRED, CONSUMED}`. |
| `detect_fvg`, campos `fvg_top`/`fvg_bottom`/`fvg_fill_status`/`fvg_anchored_htf` | `engine/fvg_poi.py` | Detección geométrica de FVG y filtro de anclaje HTF. |
| `detect_order_blocks`, campos `ob_top`/`ob_bottom`/`ob_status`/`ob_anchored_htf` | `engine/order_block.py` | Detección geométrica de OB y filtro de anclaje HTF. |
| Transiciones `ACTIVE → MITIGATED → INVALIDATED`, estados elegibles | `engine/lifecycle.py` | Autoridad canónica de transición de estado; función `evaluate()` con PIT estricto, precedencia `INVALIDATED > MITIGATED`, `PARTIALLY_MITIGATED` como estado no-terminal intermedio. |
| `stochastic_14_3_3(candles, config)` → `StochasticReading` | `mechanical_bot/core.py` | Cálculo de estocástico 14,3,3 sobre secuencia cerrada. Devuelve `StochasticReading(k, d, previous_k, previous_d)` con métodos `crossed_up_from_oversold(threshold)` y `crossed_down_from_overbought(threshold)`. |
| `closed_m15_candles(symbol, count=80)` → `list[Candle]` | `mechanical_bot/mt5_adapter.py` | Obtención de velas M15 cerradas. `Candle` tiene `high`, `low`, `close` sin timestamp. |

---

## 2. POI elegibles

### 2.1 Criterios de selección

Un `MarketObject` es POI elegible **si y solo si** se cumplen **todas** las siguientes condiciones:

| Condición | Valor requerido |
|-----------|-----------------|
| `obj.type` | `ObjectType.FVG` **o** `ObjectType.ORDER_BLOCK` |
| `obj.role` | `Role.POI` |
| `obj.state` | `ObjectState.ACTIVE` **o** `ObjectState.PARTIALLY_MITIGATED` |

### 2.2 Estados excluidos

Un objeto en **cualquiera** de los siguientes estados **NO** es POI elegible:

| Estado | Valor |
|--------|-------|
| `ObjectState.CREATED` | Objeto recién creado, aún no evaluado por el lifecycle. |
| `ObjectState.MITIGATED` | Zona completamente recorrida (no es terminal pero no es elegible para entrada). |
| `ObjectState.INVALIDATED` | Terminal: estructura rota confirmada. |
| `ObjectState.EXPIRED` | Terminal (deshabilitado en v1, no se emite). |
| `ObjectState.CONSUMED` | Terminal (deshabilitado en v1, no se emite). |

### 2.3 Simetría de zona

| Tipo | `zone_high` | `zone_low` | Dirección implícita |
|------|-------------|------------|---------------------|
| FVG alcista (bullish) | `fvg_top` = `low[i]` | `fvg_bottom` = `high[i-2]` | `+1` |
| FVG bajista (bearish) | `fvg_top` = `low[i-2]` | `fvg_bottom` = `high[i]` | `-1` |
| OB alcista (bullish) | `ob_top` = `high` de la vela source | `ob_bottom` = `low` de la vela source | `+1` |
| OB bajista (bearish) | `ob_top` = `high` de la vela source | `ob_bottom` = `low` de la vela source | `-1` |

Zona = intervalo cerrado `[zone_low, zone_high]`.

---

## 3. Dirección

| `obj.direction` | Acción a evaluar |
|-----------------|------------------|
| `+1` | COMPRA (BUY) |
| `-1` | VENTA (SELL) |

`direction = 0` no es POI operable; se descarta.

---

## 4. Proximidad

### 4.1 Parámetros fijos

| Parámetro | Valor |
|-----------|-------|
| `pip_size` (EURUSD) | `0.0001` |
| `tolerance_pips` | `5` |
| `tolerance_price` | `tolerance_pips × pip_size = 0.0005` |

### 4.2 Condición de proximidad

Sea `price` el precio actual (bid para VENTA, ask para COMPRA, o el precio de referencia del snapshot) y sean `zone_low`, `zone_high` los límites de la POI.

El precio está **cerca** de la POI si y solo si:

```
price ∈ [zone_low, zone_high]  (dentro de la zona)
```

**O**

```
distance_pips ≤ tolerance_pips  (dentro del margen de tolerancia)
```

donde:

```
if price ∈ [zone_low, zone_high]:
    distance_pips = 0.0
else:
    distance_pips = min(|price - zone_low|, |price - zone_high|) / pip_size
```

### 4.3 POI no proximity

Si ninguna POI elegible cumple la condición de proximidad, el evaluador devuelve `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

---

## 5. Estocástico M15

### 5.1 Parámetros fijos

| Parámetro | Valor |
|-----------|-------|
| `k_period` | `14` |
| `k_smoothing` | `3` |
| `d_period` | `3` |
| `config.symbol` | Símbolo del mercado (ej. `"EURUSD"`) |
| `required_candles` | `k_period + k_smoothing + d_period = 14 + 3 + 3 = 20` |

### 5.2 Obtención de datos

```
candles = closed_m15_candles(symbol, count=80)
```

- Devuelve `list[Candle]` donde `Candle = Candle(high, low, close)`. **Sin timestamp**.
- `count=80` es el máximo solicitado; el servicio puede devolver menos si hay histórico insuficiente.
- Si la longitud devuelta es `< required_candles` (20), el estocástico no se calcula.

### 5.3 Cálculo

```
reading = stochastic_14_3_3(candles, config)
```

Si `reading is None`: `status = "INSUFFICIENT_CANDLES"`.

`StochasticReading` contiene:

| Campo | Descripción |
|-------|-------------|
| `k` | Valor actual de %K suavizado |
| `d` | Valor actual de %D suavizado |
| `previous_k` | Valor de %K en la vela cerrada anterior |
| `previous_d` | Valor de %D en la vela cerrada anterior |

---

## 6. Reglas exactas de cruce 20/80

Las reglas coinciden exactamente con los métodos de `StochasticReading`:

### 6.1 Cruce alcista (COMPRA / BUY)

```
previous_k <= 20.0
AND previous_d <= 20.0
AND previous_k <= previous_d
AND k > d
```

Coincide con: `reading.crossed_up_from_oversold(20.0) == True`

### 6.2 Cruce bajista (VENTA / SELL)

```
previous_k >= 80.0
AND previous_d >= 80.0
AND previous_k >= previous_d
AND k < d
```

Coincide con: `reading.crossed_down_from_overbought(80.0) == True`

### 6.3 `cross_type` enumerado

| Valor | Significado |
|-------|-------------|
| `"CROSS_UP_FROM_OVERSOLD"` | Cumple reglas COMPRA (sección 6.1) |
| `"CROSS_DOWN_FROM_OVERBOUGHT"` | Cumple reglas VENTA (sección 6.2) |
| `"NO_CROSS"` | No cumple ninguna regla de cruce |

### 6.4 Coincidencia de dirección

El cruce debe ser **coherente con la dirección de la POI**:

| POI direction | Cruce requerido |
|---------------|-----------------|
| `+1` (COMPRA) | `CROSS_UP_FROM_OVERSOLD` |
| `-1` (VENTA) | `CROSS_DOWN_FROM_OVERBOUGHT` |

Si el cruce es del tipo incorrecto para la dirección de la POI, se considera `cross_type = "NO_CROSS"` para ese POI.

---

## 7. Coincidencia temporal

### 7.1 Vela de referencia

El cruce estocástico debe ocurrir **en la vela M15 cerrada más reciente** disponible en `candles`.

La vela más reciente es `candles[-1]` (último elemento de la lista devuelta por `closed_m15_candles`).

El estocástico se calcula sobre el historial completo disponible; `reading.k` y `reading.d` representan los valores después del cierre de `candles[-1]`. `previous_k` y `previous_d` representan los valores después del cierre de `candles[-2]`.

### 7.2 Condición de cruce vigente

El cruce es **vigente** si y solo si:

1. `cross_type` indica un cruce válido (sección 6.1 o 6.2).
2. Los valores `k` y `d` actuales corresponden a la vela más reciente cerrada (`candles[-1]`).
3. El cruce no ha vencido (ver sección 8).

---

## 8. Caducidad del cruce

### 8.1 Condiciones de vencimiento

Un cruce estocástico **VENCE** (deja de ser válido para generar entrada) cuando ocurre **cualquiera** de los siguientes eventos:

#### 8.1.1 Inversión de la relación K/D

```
k y d se invierten respecto a la condición de cruce
```

Para un cruce alcista vigente (k > d desde el cruce):
```
k <= d  →  el cruce vence
```

Para un cruce bajista vigente (k < d desde el cruce):
```
k >= d  →  el cruce vence
```

#### 8.1.2 Nueva vela sin nuevo cruce válido

Si se abre una **nueva vela M15** sin que se produzca un **nuevo cruce válido** durante **3 velas consecutivas**, el cruce anterior VENCE.

```
velas_sin_cruce >= 3  →  el cruce vence
```

Donde `velas_sin_cruce` cuenta las velas M15 consecutivas desde la vela del cruce (excluyendo la vela del cruce) hasta la vela actual, sin incluir ningún nuevo cruce válido del tipo correcto.

### 8.2 Implementación práctica

El evaluador no tiene acceso a velas futuras. La caducidad se evalúa sobre el historial disponible:

- Si los últimos 3 valores de `k, d` disponibles (desde `candles[-3]` hasta `candles[-1]`) no contienen ningún nuevo cruce válido del tipo correcto, el cruce anterior está vencido.
- Si `cross_type` es válido y los valores de la vela más reciente (`candles[-1]`) todavía cumplen la condición de cruce, el cruce está vigente.

---

## 9. Resolución de POI superpuestas

Cuando hay **múltiples POI elegibles** que cumplen la condición de proximidad (sección 4):

### 9.1 Criterio principal: menor distancia

```
poi_selected = argmin_{p ∈ elegibles_cercanas} distance_pips(p)
```

Seleccionar la POI con el menor `distance_pips` (más cercana al precio actual).

### 9.2 Criterio de desempate: mayor antigüedad por creation_time

Si dos o más POI tienen el mismo `distance_pips` (empate):

```
poi_selected = argmax_{p ∈ empate} creation_time(p)
```

Seleccionar la POI con el `creation_time` más reciente (mayor valor temporal).

`creation_time` es el campo del `MarketObject` que registra cuándo se creó el objeto (vía detector). Es comparable directamente.

### 9.3 Fallback

Si no hay POI elegibles en proximidad, no hay `poi_selected`. El evaluador devuelve `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

---

## 10. Prevención de entradas repetidas

### 10.1 Condición de bloqueo

Si existe un **ciclo activo** en la misma dirección:

```
if bot.cycle is not None:
    if bot.cycle.direction == direction_requerida:
        → NO generar nueva entrada
```

Donde:

| Campo | Descripción |
|-------|-------------|
| `bot.cycle` | Instancia de `Cycle` (o `None` si no hay ciclo activo). Ver `mechanical_bot/core.py`. |
| `bot.cycle.direction` | Dirección del ciclo (`"BUY"` o `"SELL"`). |
| `direction_requerida` | Dirección derivada de la POI (`+1` → `"BUY"`, `-1` → `"SELL"`). |

### 10.2 Comportamiento

Si la condición de bloqueo se cumple, el evaluador devuelve:

```
status = "CYCLE_ACTIVE_SAME_DIRECTION"
reason = "Existe un ciclo activo en la misma dirección"
```

Sin `poi_selected` ni `distance_pips`.

---

## 11. Campos de salida del evaluador

El evaluador devuelve un dict/lista con **exactamente** los siguientes campos. No se añaden campos adicionales.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `decision_time` | `datetime` | Momento en que se ejecutó la evaluación. |
| `status` | `str` | Estado de la evaluación. Ver enumeración en sección 11.2. |
| `reason` | `str` | Justificación legible del `status`. |
| `poi_selected` | `MarketObject \| None` | POI elegida, o `None` si no hay selección. |
| `distance_pips` | `float` | Distancia en pips de `poi_selected` al precio actual. `0.0` si está dentro de la zona. `None` si no hay selección. |
| `price` | `float` | Precio actual usado para evaluar proximidad. |
| `stochastic` | `dict` | Resultado del estocástico. Ver estructura en sección 11.3. |
| `candles_available` | `int` | Número de velas M15 cerradas devueltas por `closed_m15_candles`. |
| `next_condition` | `str` | Condición que debe cumplirse para que la siguiente evaluación genere una entrada válida. Ver sección 11.4. |

### 11.2 Valores de `status`

| Valor | Significado |
|-------|-------------|
| `"ENTRY_VALID"` | Se cumplen todas las condiciones: POI elegible en proximidad + cruce estocástico vigente coherente con dirección + no hay ciclo activo en la misma dirección. |
| `"NO_ELIGIBLE_POI_NEAR_PRICE"` | No hay POI elegible (`ObjectType.FVG` o `ObjectType.ORDER_BLOCK`, `Role.POI`, estado `ACTIVE` o `PARTIALLY_MITIGATED`) dentro de la zona o dentro del margen de 5 pips. |
| `"INSUFFICIENT_CANDLES"` | `closed_m15_candles` devolvió menos de 20 velas (`required_candles`). No se puede calcular el estocástico. |
| `"NO_CROSS"` | El estocástico no presenta un cruce válido del tipo requerido para la dirección de la POI seleccionada. |
| `"CROSS_EXPIRED"` | El cruce estocástico anterior venció (inversión K/D o 3 velas sin nuevo cruce válido). |
| `"CYCLE_ACTIVE_SAME_DIRECTION"` | Hay un ciclo activo (`bot.cycle is not None`) en la misma dirección que la POI seleccionada. |
| `"INVALID_DIRECTION"` | La POI seleccionada tiene `direction = 0` (no operable). |

### 11.3 Estructura de `stochastic`

```
{
    "k": float,
    "d": float,
    "previous_k": float,
    "previous_d": float,
    "cross_type": str  // "CROSS_UP_FROM_OVERSOLD" | "CROSS_DOWN_FROM_OVERBOUGHT" | "NO_CROSS"
}
```

- `cross_type` se calcula aplicando las reglas de sección 6.1 y 6.2 sobre los valores de `StochasticReading`.
- Si `stochastic_14_3_3` devolvió `None` (no hay suficientes velas), este campo contiene `{"cross_type": "NO_CROSS"}` o es `None` según la política de error del evaluador.

### 11.4 Valores de `next_condition`

| Valor | Significado |
|-------|-------------|
| `"AGUARDAR_CRUCE_M15"` | La POI está en proximidad pero el estocástico no presenta cruce. Esperar a que el estocástico M15 presente un cruce válido del tipo requerido en la próxima vela cerrada. |
| `"AGUARDAR_POI_EN_ZONA"` | El estocástico presenta cruce vigente pero no hay POI elegible en proximidad. Esperar a que el precio entre en proximidad de una POI elegible. |
| `"AGUARDAR_FIN_CICLO"` | Hay ciclo activo en la misma dirección. Esperar a que el ciclo se cierre antes de reevaluar. |
| `"SIN_CONDICION"` | No hay condición pendiente definida (STATUS terminal o no aplicable). |

---

## 12. Algoritmo de evaluación (secuencia)

El evaluador sigue esta secuencia exacta. En cualquier paso donde la condición falle, se devuelve el `status` correspondiente y se detiene la evaluación.

### Paso 1: Obtener POI candidatas

```
candidatas = [p para p en market_objects
              si p.type in (ObjectType.FVG, ObjectType.ORDER_BLOCK)
              y p.role == Role.POI
              y p.state in (ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED)]
```

Si `candidatas` está vacía: `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

### Paso 2: Filtrar por dirección operable

```
operables = [p para p en candidatas si p.direction in (+1, -1)]
```

Si `operables` está vacía: `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

### Paso 3: Filtrar por proximidad

```
cercanas = [p para p en operables
            si distance_pips(p, price) <= tolerance_pips]
```

Si `cercanas` está vacía: `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

### Paso 4: Seleccionar POI más cercana

```
poi = poi_selected(cercanas, price)  // sección 9
```

### Paso 5: Obtener velas M15 y calcular estocástico

```
candles = closed_m15_candles(symbol, count=80)
candles_available = len(candles)

si candles_available < 20:
    status = "INSUFFICIENT_CANDLES"

reading = stochastic_14_3_3(candles, config)

si reading is None:
    status = "INSUFFICIENT_CANDLES"
```

### Paso 6: Evaluar cruce

```
cross_type = evaluar_cross_type(reading, poi.direction)  // sección 6

si cross_type == "NO_CROSS":
    status = "NO_CROSS"
```

### Paso 7: Verificar caducidad del cruce

```
si cross_vencido(reading, poi.direction)  // sección 8
    status = "CROSS_EXPIRED"
```

### Paso 8: Verificar ciclo activo

```
si bot.cycle is not None y bot.cycle.direction == direction_string(poi.direction):
    status = "CYCLE_ACTIVE_SAME_DIRECTION"
```

### Paso 9: Entrada válida

```
si todos los pasos anteriores pasaron:
    status = "ENTRY_VALID"
```

---

## 13. Definiciones formales

### 13.1 `distance_pips(p, price)`

```
zone_low  = p.zone_low
zone_high = p.zone_high
pip_size  = 0.0001

si zone_low <= price <= zone_high:
    return 0.0

dist_low  = abs(price - zone_low)
dist_high = abs(price - zone_high)

return min(dist_low, dist_high) / pip_size
```

### 13.2 `cross_type(reading, direction)`

```
si direction == +1:
    si reading.crossed_up_from_oversold(20.0):
        return "CROSS_UP_FROM_OVERSOLD"
    sino:
        return "NO_CROSS"

si direction == -1:
    si reading.crossed_down_from_overbought(80.0):
        return "CROSS_DOWN_FROM_OVERBOUGHT"
    sino:
        return "NO_CROSS"
```

### 13.3 `cross_vencido(reading, direction)` — contrahistorial disponible

Usando los últimos valores de `k, d` de las últimas 3 velas (desde `candles[-3]` hasta `candles[-1]`):

```
si direction == +1:  // cruce alcista vigente requiere k > d
    si en las últimas 3 velas k <= d en todas:
        return True  // vencido por inversión

si direction == -1:  // cruce bajista vigente requiere k < d
    si en las últimas 3 velas k >= d en todas:
        return True  // vencido por inversión

// También vencido si no hay nuevo cruce válido en las últimas 3 velas
// y el cruce original está fuera de la ventana de 3 velas
```

En implementación real, esto requiere acceso a `StochasticReading` por vela. La verificación se hace sobre los datos disponibles; si no hay suficientes velas históricas para verificar las 3 velas anteriores al cruce, se considera que el cruce está vigente (no se puede probar la caducidad).

---

## 14. Parámetros no modificables (congelados para evaluación histórica)

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| `ObjectType` elegibles | `ObjectType.FVG`, `ObjectType.ORDER_BLOCK` | Definido por la ontología del motor ICT. |
| `Role` requerido | `Role.POI` | Filtro semántico: solo objetos con rol POI son entrada. |
| `ObjectState` elegibles | `ObjectState.ACTIVE`, `ObjectState.PARTIALLY_MITIGATED` | Estados no-terminales y no-mitigados completos. |
| Estados excluidos | `CREATED`, `MITIGATED`, `INVALIDATED`, `EXPIRED`, `CONSUMED` | Ver sección 2.2. |
| `k_period` | `14` | Estándar de estocástico. |
| `k_smoothing` | `3` | Suavizado estándar. |
| `d_period` | `3` | Promedio móvil de %K. |
| `required_candles` | `20` | `14 + 3 + 3`. |
| `pip_size` (EURUSD) | `0.0001` | Estándar de divisas. |
| `tolerance_pips` | `5` | Margen de proximidad operativa. |
| Umbral de cruce alcista | `20.0` (oversold) | Definición de zona de sobreventa. |
| Umbral de cruce bajista | `80.0` (overbought) | Definición de zona de sobrecompra. |
| `count` de `closed_m15_candles` | `80` | Historial suficiente para cálculo y verificación. |
| `cross_type` de referencia | `crossed_up_from_oversold(20.0)`, `crossed_down_from_overbought(80.0)` | Métodos de `StochasticReading`. |
| Caducidad por inversión | `k <= d` (alcista), `k >= d` (bajista) | Condición de reinversión de la relación. |
| Caducidad por tiempo | 3 velas M15 sin nuevo cruce válido | Ventana de vigencia del señal. |

---

## 15. Casos de prueba semánticos (sin código)

### Caso A: Entrada válida COMPRA

- Existe FVG alcista (`ObjectType.FVG`, `Role.POI`, `direction=+1`, `state=ACTIVE`).
- `zone_low`, `zone_high` definidos.
- Precio actual está a 2 pips de `zone_low` (fuera de zona, dentro de tolerancia).
- `closed_m15_candles` devuelve 80 velas.
- `stochastic_14_3_3` devuelve `StochasticReading` con `previous_k=18.0`, `previous_d=19.0`, `k=25.0`, `d=22.0`.
- `cross_type = "CROSS_UP_FROM_OVERSOLD"`.
- No hay ciclo activo en dirección `"BUY"`.
- **Resultado esperado:** `status = "ENTRY_VALID"`, `poi_selected = FVG`, `distance_pips = 2.0`.

### Caso B: Cruce bajista sin POI en proximidad

- Estocástico presenta `CROSS_DOWN_FROM_OVERBOUGHT`.
- No hay ninguna POI (`FVG` o `OB`) con `state` elegible en los 5 pips alrededor del precio.
- **Resultado esperado:** `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

### Caso C: POI con estado `MITIGATED`

- Existe FVG con `state = ObjectState.MITIGATED`.
- Aunque está cerca del precio y el estocástico presenta cruce, el FVG está en estado excluido.
- **Resultado esperado:** `status = "NO_ELIGIBLE_POI_NEAR_PRICE"` (la POI no es elegible, no se considera).

### Caso D: Doble POI en proximidad (desempate)

- FVG A: `distance_pips = 3.0`, `creation_time = T1`.
- FVG B: `distance_pips = 3.0`, `creation_time = T2` donde `T2 > T1`.
- Ambas con `direction = +1`.
- **Resultado esperado:** `poi_selected = FVG B` (más reciente por `creation_time`).

### Caso E: Cruce vencido por inversión K/D

- Hubo cruce alcista en vela t-3: `previous_k=18`, `previous_d=19`, `k=25`, `d=22`.
- En vela t-2: `k=20`, `d=23` (k < d, relación invertida).
- En vela t-1: `k=18`, `d=21` (k < d, seguimos invertidos).
- En vela t (actual): `k=17`, `d=20` (k < d).
- No hay nuevo cruce válido en las últimas 3 velas.
- **Resultado esperado:** `status = "CROSS_EXPIRED"`.

### Caso F: Ciclo activo bloquea entrada

- POI seleccionada con `direction = +1` → `"BUY"`.
- `bot.cycle` existe y `bot.cycle.direction = "BUY"`.
- **Resultado esperado:** `status = "CYCLE_ACTIVE_SAME_DIRECTION"`.

---

## 16. Invariantes y garantías

1. **Sin terms ambiguos:** todos los estados, umbrales, condiciones y resultados están enumerados explícitamente. No hay "aproximadamente", "cerca", "razonable".
2. **Sin look-ahead:** el estocástico se calcula solo sobre velas cerradas (`closed_m15_candles`). El cruce se evalúa sobre `candles[-1]` (vela más reciente cerrada).
3. **Parámetros fijos antes de evaluación:** todos los umbrales, periods y tolerancias se definen en sección 14 antes de ejecutar cualquier evaluación histórica.
4. **POI solo de fuente canónica:** `market_object.py`, `fvg_poi.py`, `order_block.py` son las únicas fuentes de objetos de mercado. No se crean POI fuera del motor.
5. **Estocástico solo de fuente canónica:** `stochastic_14_3_3` de `mechanical_bot/core.py` es la única función de cálculo. No se reimplementa.
6. **Velas M15 solo de fuente canónica:** `closed_m15_candles` de `mechanical_bot/mt5_adapter.py` es el único accessor. No se construye manualmente.
7. **Ciclos idempotentes:** reevaluar con los mismos datos produce el mismo `status`. No hay efectos secundarios en el evaluador (solo lectura).

---

## 17. Historial de versiones

| Versión | Fecha | Autor | Cambios |
|---------|-------|-------|---------|
| 1.0 | 2026-09-14 | D6 Research | Creación inicial. Congelamiento de parámetros para evaluación histórica POI canónica + estocástico M15. |

---

*Documento congelado. No se modifica durante la evaluación histórica. Cualquier cambio requiere nueva versión y reevaluación.*
