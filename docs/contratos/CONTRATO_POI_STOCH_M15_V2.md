# CONTRATO_POI_STOCH_M15_V2.md

**Archivo:** `docs/contratos/CONTRATO_POI_STOCH_M15_V2.md`
**Versión:** 2.0
**Fecha:** 2026-09-14
**Autor:** D6 Research
**Misión:** MC-20260914-083000-poi-stoch-m15
**Propósito:** Especificación congelada de la estrategia POI canónica (FVG + OB) + estocástico M15, versión corregida que resuelve las contradicciones del v1 y define una sola regla coherente para la estrategia simplificada.

---

## 0. Declaración de corrección respecto al v1

El v1 (CONTRATO_POI_STOCH_M15_V1.md) contenía las siguientes contradicciones que este v2 resuelve expresamente:

| # | Contradicción v1 | Resolución v2 |
|---|------------------|---------------|
| C1 | Sección 2.1 exigía `obj.role == Role.POI` como condición de elegibilidad, pero el motor operativo publica FVG/OB exclusivamente con `Role.REFINEMENT` (ver `engine/detectors/fvg.py`, `engine/detectors/ob.py`). | Sección 2.1 elimina `Role.POI` como condición. Adopta criterio alternativo basado en tipo, temporalidad acordada, estado, símbolo, geometría y disponibilidad temporal. |
| C2 | Sección 14 congelaba `Role.POI` como parámetro no modificable, pero el único `Role.POI` del codebase está en `engine/historical_event_objects.py` (línea 105, flujo histórico) y `engine/plan_emitters.py` (línea 64, backtest). | Sección 2.4 decide explícitamente: el contrato NO exige `Role.POI`. Define cuándo `Role.POI` aplica (flujos históricos/backtest) y cuándo no. |
| C3 | El evaluador (`engine/poi_stoch_evaluator.py`, línea 287) filtraba por `Role.POI`, haciendo imposible que el flujo operativo produjera `ENTRY_VALID`. | El evaluador corrige su filtro para usar el criterio de la sección 2.1 de este v2. |
| C4 | No había definición de temporalidades elegibles ni prioridad entre objetos superpuestos. | Sección 2.2 define temporalidades acordadas; sección 9.4 define prioridad entre superpuestos. |
| C5 | La caducidad (sección 8) era ambigua: no distinguía entre cruce vigente por verificación vs. cruce presumido vigente por falta de datos. | Sección 8 define tres estados de verificación del cruce: verificado vigente, verificado vencido, no verificable (no vigente). |
| C6 | No había mecanismo de identificador único del cruce que impidiera reutilización. | Sección 8.3 introduce `cross_id` único y regla de no reutilización. |
| C7 | No había regla de coincidencia entre contacto con la zona y cruce M15. | Sección 7.3 define la coincidencia requerida. |

**Este contrato NO elimina FVG ni restringe temporalidades silenciosamente.** Mantiene FVG y OB como tipos elegibles, y mantiene todas las temporalidades donde el motor las detecta (D1, H4, H1, M15), con reglas explícitas de cuáles son POI-TFs acordadas y cuál es el rol de M15.

---

## 1. Fuentes canónicas

| Entidad | Archivo de origen | Responsabilidad |
|---------|-------------------|-----------------|
| `MarketObject`, `ObjectType`, `Role`, `ObjectState` | `engine/market_object.py` | Definición de objetos, tipos, roles y estados. Incluye `_POI_TFS = {"D1", "H4", "H1"}` y `_ALLOWED_TRANSITIONS`. |
| `detect_fvg`, campos `fvg_top`/`fvg_bottom`/`fvg_fill_status`/`fvg_anchored_htf` | `engine/fvg_poi.py` (usage) / `engine/detectors/fvg.py` (fuente) | Detección geométrica de FVG. Publica con `role=Role.REFINEMENT`. |
| `detect_order_blocks`, campos `ob_top`/`ob_bottom`/`ob_status`/`ob_anchored_htf` | `engine/order_block.py` (usage) / `engine/detectors/ob.py` (fuente) | Detección geométrica de OB. Publica con `role=Role.REFINEMENT`. |
| Transiciones `ACTIVE → MITIGATED → INVALIDATED`, estados elegibles | `engine/lifecycle.py` | Autoridad canónica de transición de estado. |
| `stochastic_14_3_3(candles, config)` → `StochasticReading` | `mechanical_bot/core.py` | Cálculo de estocástico 14,3,3. |
| `closed_m15_candles(symbol, count=80)` → `list[Candle]` | `mechanical_bot/mt5_adapter.py` | Obtención de velas M15 cerradas. |
| `build_ltf_canonical_feed`, `build_canonical_objects` | `engine/ltf_canonical_feed.py` | Ensamblador read-only del flujo operativo diario. |
| `HtfPdIndex`, `zones_at` | `engine/htf_pd_index.py` | Índice temporal de PD arrays HTF vigentes (percepción, no decisión). |

---

## 2. POI elegibles

### 2.1 Criterios de selección (criterio alternativo)

Un `MarketObject` es **POI elegible** **si y solo si** se cumplen **todas** las siguientes condiciones:

| Condición | Valor requerido | Observación |
|-----------|-----------------|-------------|
| `obj.type` | `ObjectType.FVG` **o** `ObjectType.ORDER_BLOCK` | Tipos PD Array del motor ICT. |
| `obj.origin_tf` | `"D1"`, `"H4"` **o** `"H1"` | **Temporalidades acordadas como POI-TFs.** Ver sección 2.2. |
| `obj.state` | `ObjectState.ACTIVE` **o** `ObjectState.PARTIALLY_MITIGATED` | Estados no-terminales. Ver sección 2.3. |
| `obj.symbol` | Coincide con el símbolo de evaluación | El objeto debe pertenecer al símbolo evaluado. |
| `obj.zone_high`, `obj.zone_low` | Ambos son números finitos (`math.isfinite(zone_high) and math.isfinite(zone_low) == True`) y `zone_high >= zone_low` | Geometría válida. |
| `obj.tradable_time` | No es `None` y `tradable_time <= decision_time` | El objeto debe haber nacido (ser comercializable) antes o en el momento de decisión. |
| `obj.direction` | `+1` o `-1` | Dirección operable. Se verifica en paso 2 del algoritmo (sección 12). |

**Condición de nacimiento:** El objeto nace (se vuelve `tradable`) en `tradable_time`. No se requiere `Role.POI` para que sea POI elegible.

### 2.2 Temporalidades acordadas

| Categoría | Temporalidades | Rol en la estrategia |
|-----------|---------------|---------------------|
| **POI-TFs acordadas** | `"D1"`, `"H4"`, `"H1"` | Son las temporalidades donde un FVG o OB se considera POI (punto de entrada potencial) para la estrategia simplificada. Coinciden con `_POI_TFS` del motor (`engine/market_object.py` línea 64). |
| **TF de ejecución / refinamiento** | `"M15"` | Es la temporalidad de ejecución. Los FVG/OB detectados en M15 por el motor operativo (`engine/ltf_canonical_feed.py`, `engine/htf_pd_index.py`) son **refinamientos** de la estructura, no POI primarios. Pueden ser usados como contexto o confirmación, pero NO como POI elegible para entrada en esta estrategia. |
| **TFs no acordadas para esta estrategia** | Cualquier otra (`M5`, `M1`, `W1`, etc.) | No son POI-TFs acordadas. Los objetos en estas temporalidades no son elegibles como POI. |

**Razón de la distinción:** El motor operativo detecta FVG/OB en M15 como parte del feed LTF (`engine/ltf_canonical_feed.py` línea 192-193), pero la estrategia POI+Stoch define POI como estructura de temporalidad superior (D1/H4/H1) confirmada por estocástico M15. M15 es el TF donde se evalúa el estocástico y donde se ejecuta, no el TF donde nace el POI.

### 2.3 Estados excluidos

Un objeto en **cualquiera** de los siguientes estados **NO** es POI elegible:

| Estado | Valor | Motivo |
|--------|-------|--------|
| `ObjectState.CREATED` | `"CREATED"` | Objeto recién creado, aún no evaluado por el lifecycle. No es comercializable. |
| `ObjectState.MITIGATED` | `"MITIGATED"` | Zona completamente recorrida. Aunque no es terminal, no es elegible para entrada (precedencia `INVALIDATED > MITIGATED` según convención v1 del motor). |
| `ObjectState.INVALIDATED` | `"INVALIDATED"` | Terminal: estructura rota confirmada. |
| `ObjectState.EXPIRED` | `"EXPIRED"` | Terminal. |
| `ObjectState.CONSUMED` | `"CONSUMED"` | Terminal. |

**Nota sobre `PARTIALLY_MITIGATED`:** Es un estado no-terminal intermedio. Está incluido como elegible porque el lifecycle permite que un objeto `ACTIVE` pase a `PARTIALLY_MITIGATED` sin perder su validez como POI; la zona aún no fue completamente recorrida.

### 2.4 Decisión explícita: `Role.POI` vs criterio alternativo

**DECISIÓN:** Este contrato **NO exige `Role.POI`** como condición de elegibilidad de POI. Adopta el **criterio alternativo** definido en la sección 2.1.

**Justificación:**

1. **Incompatibilidad del flujo operativo:** El motor operativo (`engine/detectors/fvg.py`, `engine/detectors/ob.py`, `engine/ltf_canonical_feed.py`) publica FVG y OB exclusivamente con `role=Role.REFINEMENT`. Jamás publica `Role.POI`. Exigir `Role.POI` como condición de elegibilidad hace que el evaluador nunca encuentre POI en el flujo operativo, resultando en `status = "NO_ELIGIBLE_POI_NEAR_PRICE"` de forma permanente e inintencional.

2. **Origen histórico de `Role.POI`:** El único lugar donde se asigna `Role.POI` en el codebase es:
   - `engine/historical_event_objects.py` línea 105: `ob.role = Role.POI` — asigna `Role.POI` a OBs de H4 **solo en el flujo de construcción de objetos históricos para backtest**.
   - `engine/plan_emitters.py` línea 64: `o.role is Role.POI` — filtra por `Role.POI` en el emisor H1 del backtest.
   
   Ambos son componentes de **backtest/histórico**, no del flujo operativo diario. El v1 congeló `Role.POI` como parámetro (sección 14) sin verificar que el flujo operativo lo publicara.

3. **Separación de concerns:** `Role.REFINEMENT` indica que el objeto es una refinación de estructura (FVG/OB detectado por el motor). `Role.POI` indica que el objeto fue seleccionado como POI en un flujo de evaluación histórica. Son roles semánticos distintos para contextos distintos. Mezclarlos como si fueran intercambiables es la raíz de la contradicción.

4. **Criterio alternativo es suficiente y más robusto:** El criterio de la sección 2.1 (tipo + temporalidad acordada + estado + símbolo + geometría + disponibilidad temporal) es más robusto que un filtro de rol porque:
   - No depende de una asignación de rol que el motor operativo no hace.
   - Captura la esencia de lo que hace un POI: es un FVG/OB en una temporalidad acordada, en estado operable, con geometría válida, disponible en el momento de decisión.
   - Es verificable sobre el feed operativo real (`build_ltf_canonical_feed` + `build_canonical_objects`).

**Alcance de `Role.POI` luego de esta decisión:**

- `Role.POI` **sigue existiendo** como valor del enum `Role` y como rol asignado por `engine/historical_event_objects.py` y `engine/plan_emitters.py` en sus respectivos contextos (backtest, histórico).
- `Role.POI` **no es condición** de este contrato para la estrategia simplificada.
- Si en el futuro el flujo operativo empieza a publicar `Role.POI`, este contrato no se opone: el criterio alternativo sigue siendo válido, y `Role.POI` sería información adicional, no un filtro excluyente.

**Cambio respecto al v1:** El v1 exigía explícitamente `Role.POI`. El v2 lo reemplaza por el criterio alternativo. Este cambio está documentado en la sección 0 (tabla de contradicciones) y en esta sección 2.4. Ningún otro contrato de la misión se modifica; esta decisión es local a MC-20260914-083000-poi-stoch-m15.

### 2.5 Simetría de zona

| Tipo | `zone_high` | `zone_low` | Dirección implícita |
|------|-------------|------------|---------------------|
| FVG alcista (bullish) | `low[i]` | `high[i-2]` | `+1` |
| FVG bajista (bearish) | `low[i-2]` | `high[i]` | `-1` |
| OB alcista (bullish) | `high` de la vela source | `low` de la vela source | `+1` |
| OB bajista (bearish) | `high` de la vela source | `low` de la vela source | `-1` |

Zona = intervalo cerrado `[zone_low, zone_high]`.

---

## 3. Dirección

| `obj.direction` | Acción a evaluar |
|-----------------|------------------|
| `+1` | COMPRA (BUY) |
| `-1` | VENTA (SELL) |

`direction = 0` no es POI operable; se descarta en el paso 2 del algoritmo (sección 12). No es error; es filtro normal.

---

## 4. Proximidad

### 4.1 Parámetros fijos

| Parámetro | Valor |
|-----------|-------|
| `pip_size` (EURUSD) | `0.0001` |
| `tolerance_pips` | `5` |
| `tolerance_price` | `tolerance_pips × pip_size = 0.0005` |

### 4.2 Precio de referencia

| Acción | Precio de referencia |
|--------|---------------------|
| COMPRA (BUY, `direction = +1`) | **Ask** del mercado en `decision_time`. |
| VENTA (SELL, `direction = -1`) | **Bid** del mercado en `decision_time`. |

Si el evaluador no tiene acceso separado a ask/bid, usa el precio del snapshot operativo (`engine/mt5_operational_snapshot.py`) que contiene ambos. No se usa un precio único ambiguo.

### 4.3 Condición de proximidad

Sea `price` el precio de referencia definido en la sección 4.2, y sean `zone_low`, `zone_high` los límites de la POI.

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

### 4.4 POI no proximity

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
| `required_candles` | `14 + 3 + 3 = 20` |

### 5.2 Obtención de datos

```
candles = closed_m15_candles(symbol, count=80)
```

- Devuelve `list[Candle]` donde `Candle = Candle(high, low, close)`. **Sin timestamp** en la firma de `Candle`, pero las velas son **M15 cerradas** (el adapter garantiza que cada `Candle` corresponde a una vela M15 cerrada; el orden es cronológico).
- `count=80` es el máximo solicitado; el servicio puede devolver menos si hay histórico insuficiente.
- Si la longitud devuelta es `< required_candles` (20), el estocástico no se calcula → `status = "INSUFFICIENT_CANDLES"`.

### 5.3 Cálculo

```
reading = stochastic_14_3_3(candles, config)
```

Si `reading is None`: `status = "INSUFFICIENT_CANDLES"`.

`StochasticReading` contiene:

| Campo | Descripción |
|-------|-------------|
| `k` | Valor actual de %K suavizado (después del cierre de `candles[-1]`). |
| `d` | Valor actual de %D suavizado (después del cierre de `candles[-1]`). |
| `previous_k` | Valor de %K en la vela cerrada anterior (`candles[-2]`). |
| `previous_d` | Valor de %D en la vela cerrada anterior (`candles[-2]`). |

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

## 7. Coincidencia temporal y de contacto

### 7.1 Vela de referencia del cruce

El cruce estocástico debe ocurrir **en la vela M15 cerrada más reciente** disponible en `candles`.

- La vela más reciente es `candles[-1]` (último elemento de la lista devuelta por `closed_m15_candles`).
- El estocástico se calcula sobre el historial completo disponible; `reading.k` y `reading.d` representan los valores después del cierre de `candles[-1]`. `previous_k` y `previous_d` representan los valores después del cierre de `candles[-2]`.
- El cruce se evalúa comparando `(previous_k, previous_d)` con `(k, d)` de `reading`. Si las reglas de la sección 6.1 o 6.2 se cumplen, el cruce ocurrió **entre `candles[-2]` y `candles[-1]`**, es decir, en la última transición de vela cerrada a vela cerrada.

### 7.2 Condición de cruce vigente

El cruce es **vigente** si y solo si:

1. `cross_type` indica un cruce válido (sección 6.1 o 6.2).
2. Los valores `k` y `d` actuales corresponden a la vela más reciente cerrada (`candles[-1]`).
3. El cruce no ha vencido (ver sección 8).
4. El cruce es **verificable** en cuanto a su temporalidad (ver sección 8.2.3).

### 7.3 Coincidencia entre contacto con la zona y cruce M15

**REGLA DE COINCIDENCIA:** Para que una entrada sea válida, deben coincidir **dos eventos independientes** en la misma dirección:

| Evento | Condición | TF |
|--------|-----------|-----|
| **Contacto con la zona POI** | El precio de referencia (ask para COMPRA, bid para VENTA) está dentro de la zona `[zone_low, zone_high]` de la POI elegida, **O** está a ≤5 pips de la zona (sección 4.3). | El precio de referencia es el precio actual del mercado en `decision_time`. |
| **Cruce M15** | El estocástico M15 presenta un cruce válido del tipo requerido para la dirección de la POI (sección 6.1 o 6.2), vigente (sección 8), y ocurrido en la última vela cerrada (`candles[-1]`). | M15. |

**Ambos eventos deben estar presentes simultáneamente.** No basta con que la POI esté en proximidad si el estocástico no presenta cruce. No basta con que el estocástico presente cruce si no hay POI en proximidad.

**La temporalidad de cada evento es distinta y eso es correcto:** La POI es una estructura de temporalidad superior (D1/H4/H1). El estocástico es M15. La coincidencia no requiere que ambos eventos ocurran en la misma temporalidad; requiere que ambos condiciones se cumplan en el mismo `decision_time`. Esto es coherente con la metodología ICT: la POI es el "dónde" (nivel de estructura), el estocástico M15 es el "cuándo" (timing de ejecución).

**Verificación de contacto:** El contacto con la zona se verifica mediante `distance_pips == 0.0` (precio dentro de la zona) **o** `distance_pips ≤ tolerance_pips` (precio en el margen). No se requiere que el precio haya tocado la zona previamente (touch histórico); la proximidad actual es suficiente. Si en el futuro se requiere touch histórico, ese requisito se añade como nueva sección sin modificar esta.

---

## 8. Vigencia del cruce

### 8.1 Definición de cruce vigente

Un cruce estocástico es **vigente** en `decision_time` si y solo si:

1. **Ocurrió en la última vela cerrada:** El cruce se produjo entre `candles[-2]` y `candles[-1]` (es decir, `cross_type` es válido al evaluar `reading` sobre `candles`).
2. **No ha vencido por inversión K/D:** Para cruce alcista (`k > d` en el momento del cruce), la relación `k > d` se mantiene en `candles[-1]`. Para cruce bajista (`k < d` en el momento del cruce), la relación `k < d` se mantiene en `candles[-1]`.
3. **No ha vencido por caducidad temporal:** No han pasado 3 velas M15 consecutivas sin un nuevo cruce válido del tipo correcto desde el cruce original (ver sección 8.2.2).
4. **Es verificable:** La temporalidad del cruce puede verificarse a partir de los datos disponibles (ver sección 8.2.3).
5. **No ha sido consumido:** Su `cross_id` (ver sección 8.3) no ha sido usado previamente para generar una entrada.

### 8.2 Mecanismos de vencimiento

#### 8.2.1 Inversión de la relación K/D

```
Para cruce alcista vigente (k > d desde el cruce):
    k <= d  →  el cruce vence

Para cruce bajista vigente (k < d desde el cruce):
    k >= d  →  el cruce vence
```

Verificado sobre los valores de `candles[-1]` (la vela más reciente cerrada).

#### 8.2.2 Tres velas M15 sin nuevo cruce válido

Si se abren **3 velas M15 consecutivas** después del cruce original sin que se produzca un **nuevo cruce válido** del tipo correcto (mismo tipo que el cruce original), el cruce original **VENCE**.

```
velas_desde_cruce >= 3  AND  no_hay_nuevo_cruce_valido_en_esas_velas  →  el cruce vence
```

Donde:
- `velas_desde_cruce` cuenta las velas M15 desde `candles[-1]` del cruce original (excluyendo la vela del cruce) hasta la vela actual.
- `no_hay_nuevo_cruce_valido` significa que en ninguna de esas velas se cumplieron las reglas de la sección 6.1 o 6.2 para el mismo tipo de cruce.

**Implementación sobre historial disponible:** El evaluador recorre las últimas 3 velas (`candles[-3]`, `candles[-2]`, `candles[-1]`) y verifica si en alguna de ellas hubo cruce válido del tipo requerido. Si en las 3 no hubo, el cruce anterior está vencido. Si hay al menos un nuevo cruce válido en esas 3 velas, el cruce anterior **no** está vencido por este mecanismo (aunque puede estarlo por inversión K/D).

#### 8.2.3 Verificabilidad de la temporalidad del cruce

Esta sección resuelve el hallazgo C5 del v1: definir explícitamente cuándo un cruce es vigente vs. cuándo no se puede considerar vigente.

| Situación | Estado del cruce | Motivo |
|-----------|-----------------|--------|
| `len(candles) >= 4` y se puede verificar las 3 velas de caducidad | **Verificable.** Aplicar las reglas 8.2.1 y 8.2.2. | Hay suficientes velas para verificar la caducidad. |
| `len(candles) < 4` (menos de 4 velas M15 disponibles) | **No verificable → NO VIGENTE.** `status = "INSUFFICIENT_CANDLES"` o `status = "CROSS_EXPIRED"` según corresponda. | No hay suficientes velas para verificar los 3 días de caducidad. No se puede asumir que el cruce está vigente por falta de datos. |
| `candles[-1]` no corresponde a una vela M15 cerrada (datos corruptos o de otra temporalidad) | **No verificable → NO VIGENTE.** | La temporalidad del cruce no puede verificarse. |
| `stochastic_14_3_3` devolvió `None` (no hay suficientes velas para el cálculo) | **No aplicable.** `status = "INSUFFICIENT_CANDLES"`. | El cruce no existe porque el estocástico no se calculó. |

**Regla general:** Si la temporalidad del cruce no puede verificarse con los datos disponibles, el cruce **NO es vigente**. No se aplica presunción de vigencia por falta de datos.

### 8.3 Identificador único del cruce (`cross_id`) y no reutilización

Cada cruce estocástico válido se identifica de forma única por:

```
cross_id = f"{cross_type}_{candles[-1]_immutable_signature}"
```

Donde `candles[-1]_immutable_signature` es una firma inmutable de la vela `candles[-1]` que incluye al menos:
- `high`, `low`, `close` de la vela.
- Posición del cruce en la secuencia (el índice de `candles[-1]` en el historial de velas disponibles, o un hash de la secuencia de velas usada).

**Propósito:** `cross_id` permite:
1. Identificar unívocamente qué cruce se usó para una entrada.
2. Verificar que el mismo cruce no se reutiliza en evaluaciones posteriores.
3. Auditoría: cada entrada generada se asocia a un `cross_id` específico.

**Regla de no reutilización:**

```
Si en una evaluación previa se generó una entrada con cross_id = X,
y en la evaluación actual el cruce presente tiene cross_id = X,
→ El cruce NO es vigente para una nueva entrada (ya fue consumido).
```

**Implementación:** El evaluador mantiene un registro de `cross_ids` consumidos. Si el `cross_id` del cruce actual ya está en el registro, el cruce se considera vencido/consumido → `status = "CROSS_EXPIRED"` con `reason = "Cruce ya consumido en evaluación previa"`.

### 8.4 Vencimiento al cerrarse la siguiente vela

El cruce **vence automáticamente al cerrarse la siguiente vela M15 después del cruce**, si no se cumple alguna de las condiciones de vigencia:

- Cuando llega una nueva vela M15 cerrada (`candles` cambia: el antiguo `candles[-1]` pasa a ser `candles[-2]`, y la nueva vela es `candles[-1]`):
  1. Se recalcula `reading` sobre el nuevo conjunto de velas.
  2. Si el nuevo `reading` no presenta un cruce válido del tipo correcto, el cruce anterior **vence** (salvo que la regla de 3 velas aún no haya expirado).
  3. Si el nuevo `reading` presenta el mismo `cross_type` pero con valores diferentes, el cruce anterior **vence** y el nuevo cruce (si es válido) tiene su propio `cross_id`.
  4. Si el nuevo `reading` presenta un cruce del tipo opuesto, el cruce anterior **vence** inmediatamente (inversión K/D).

**Resumen:** El cruce es vigente solo en la evaluación inmediatamente posterior a su ocurrencia (es decir, cuando `candles[-1]` es la vela donde ocurrió el cruce). La siguiente evaluación (con una nueva vela cerrada) debe presentar un nuevo cruce válido o el cruce anterior vence. Esto es coherente con la regla de 3 velas: el cruce tiene 3 velas de vida máxima, y la primera de esas velas es la que cierra inmediatamente después del cruce.

---

## 9. Resolución de POI superpuestas

Cuando hay **múltiples POI elegibles** que cumplen la condición de proximidad (sección 4):

### 9.1 Criterio principal: menor distancia

```
poi_selected = argmin_{p ∈ elegibles_cercanas} distance_pips(p)
```

Seleccionar la POI con el menor `distance_pips` (más cercana al precio actual).

### 9.2 Criterio de desempate: mayor antigüedad por `creation_time`

Si dos o más POI tienen el mismo `distance_pips` (empate):

```
poi_selected = argmax_{p ∈ empate} creation_time(p)
```

Seleccionar la POI con el `creation_time` más reciente (mayor valor temporal).

`creation_time` es el campo del `MarketObject` que registra cuándo se creó el objeto (vía detector). Es comparable directamente.

### 9.3 Fallback

Si no hay POI elegibles en proximidad, no hay `poi_selected`. El evaluador devuelve `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

### 9.4 Prioridad entre objetos superpuestos (nueva regla)

**Definición de superposición:** Dos POI `A` y `B` están superpuestas si sus zonas se solapan:

```
max(zone_low_A, zone_low_B) < min(zone_high_A, zone_high_B)
```

**Regla de prioridad cuando hay POI superpuestas en la misma dirección:**

```
Prioridad 1: Mayor temporalidad (POI-TF). Orden: D1 > H4 > H1.
Prioridad 2: Si mismo POI-TF, menor distance_pips.
Prioridad 3: Si mismo distance_pips, mayor creation_time (más reciente).
```

**Regla de conflicto entre POI opuestas (direcciones opuestas) en superposición:**

Cuando hay una POI alcista (`direction = +1`) y una POI bajista (`direction = -1`) cuyas zonas se solapan y ambas están en proximidad del precio:

```
1. Si solo una de las dos cumple la condición de proximidad estricta (price dentro de la zona):
    → Seleccionar esa POI. La otra se descarta.

2. Si ambas tienen price dentro de sus zonas (precio dentro de la superposición):
    → Seleccionar la POI de mayor temporalidad (D1 > H4 > H1).
    → Si mismo POI-TF, seleccionar la de mayor creation_time (más reciente).
    → La POI de menor temporalidad se descarta como "POI opuesta en conflicto".

3. Si ninguna tiene price dentro de la zona pero ambas están dentro del margen de tolerancia:
    → Aplicar las reglas 9.1-9.3 (menor distance_pips, luego desempate por creation_time).
    → Si la POI ganadora tiene direction opuesto a otra POI también en proximidad, la regla de conflicto de la regla 2 se aplica como desempate adicional.
```

**Prevención de repeticiones por conflicto de direcciones:**

```
Si en una evaluación previa se seleccionó una POI con direction = D
y en la evaluación actual la POI seleccionada (por las reglas anteriores) tiene direction = D,
y el cross_id del cruce actual es el mismo que el de la evaluación previa:
    → NO generar nueva entrada (cross_id ya consumido, ver sección 8.3).

Si la POI seleccionada tiene direction diferente a la evaluación previa:
    → Es una nueva entrada potencial (el ciclo anterior debe haber terminado para que sea válida,
      ver sección 10).
```

---

## 10. Prevención de entradas repetidas

### 10.1 Condición de bloqueo por ciclo activo

Si existe un **ciclo activo** (`bot.cycle is not None`) en la misma dirección:

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

### 10.2 Condición de bloqueo por `cross_id` consumido

Si el `cross_id` del cruce actual ya fue utilizado en una evaluación previa para generar una entrada (ver sección 8.3):

```
if cross_id actual en registro_cross_ids_consumidos:
    → NO generar nueva entrada
    → status = "CROSS_EXPIRED"
    → reason = "Cruce ya consumido en evaluación previa"
```

### 10.3 Comportamiento

Si la condición de bloqueo se cumple, el evaluador devuelve:

```
status = "CYCLE_ACTIVE_SAME_DIRECTION"  (si es por ciclo)
         O "CROSS_EXPIRED"              (si es por cross_id consumido)

reason = "Existe un ciclo activo en la misma dirección"
         O "Cruce ya consumido en evaluación previa"

Sin poi_selected ni distance_pips (en caso de ciclo).
Con poi_selected y distance_pips (en caso de cross_id consumido, para auditoría).
```

### 10.4 Registro de `cross_ids` consumidos

El evaluador mantiene un conjunto `registro_cross_ids_consumidos` que contiene los `cross_id` de todos los cruces que han generado una entrada válida (`status = "ENTRY_VALID"`). Este registro:

- Se actualiza cada vez que `status = "ENTRY_VALID"`.
- Se consulta antes de declarar `ENTRY_VALID` para verificar que el `cross_id` actual no esté en el registro.
- Es persistente entre evaluaciones (no se resetea automáticamente).
- En contexto de backtest histórico, el registro se construye secuencialmente sobre la serie temporal.

---

## 11. Campos de salida del evaluador

El evaluador devuelve un dict con **exactamente** los siguientes campos. No se añaden campos adicionales.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `decision_time` | `datetime` | Momento en que se ejecutó la evaluación. |
| `status` | `str` | Estado de la evaluación. Ver enumeración en sección 11.2. |
| `reason` | `str` | Justificación legible del `status`. |
| `poi_selected` | `MarketObject | None` | POI elegida, o `None` si no hay selección. |
| `distance_pips` | `float` | Distancia en pips de `poi_selected` al precio actual. `0.0` si está dentro de la zona. `None` si no hay selección. |
| `price` | `float` | Precio de referencia usado para evaluar proximidad (ask o bid según dirección). |
| `price_type` | `str` | Tipo de precio usado: `"ASK"` para COMPRA, `"BID"` para VENTA. |
| `stochastic` | `dict` | Resultado del estocástico. Ver estructura en sección 11.3. |
| `candles_available` | `int` | Número de velas M15 cerradas devueltas por `closed_m15_candles`. |
| `cross_id` | `str` | Identificador único del cruce evaluado (sección 8.3). `None` si no hay cruce. |
| `next_condition` | `str` | Condición que debe cumplirse para que la siguiente evaluación genere una entrada válida. Ver sección 11.4. |

### 11.2 Valores de `status`

| Valor | Significado |
|-------|-------------|
| `"ENTRY_VALID"` | Se cumplen todas las condiciones: POI elegible en proximidad + cruce estocástico vigente coherente con dirección + no hay ciclo activo en la misma dirección + cross_id no consumido + cruce verificable. |
| `"NO_ELIGIBLE_POI_NEAR_PRICE"` | No hay POI elegible (criterio sección 2.1) dentro de la zona o dentro del margen de 5 pips. Incluye el caso donde no hay objetos con `origin_tf` en POI-TFs acordadas. |
| `"INSUFFICIENT_CANDLES"` | `closed_m15_candles` devolvió menos de 20 velas (`required_candles`). No se puede calcular el estocástico. |
| `"NO_CROSS"` | El estocástico no presenta un cruce válido del tipo requerido para la dirección de la POI seleccionada. |
| `"CROSS_EXPIRED"` | El cruce estocástico venció (inversión K/D, 3 velas sin nuevo cruce válido, cruce no verificable, o cross_id ya consumido). |
| `"CYCLE_ACTIVE_SAME_DIRECTION"` | Hay un ciclo activo (`bot.cycle is not None`) en la misma dirección que la POI seleccionada. |
| `"INVALID_DIRECTION"` | La POI seleccionada tiene `direction = 0` (no operable). |
| `"CONFLICT_OPPOSITE_POI"` | Hay POI opuestas (alcista y bajista) en superposición y conflicto de dirección; se resolvió por prioridad de temporalidad pero el resultado es ambiguo o el precio está en la superposición de ambas. |

### 11.3 Estructura de `stochastic`

```json
{
    "k": float,
    "d": float,
    "previous_k": float,
    "previous_d": float,
    "cross_type": "CROSS_UP_FROM_OVERSOLD" | "CROSS_DOWN_FROM_OVERBOUGHT" | "NO_CROSS",
    "cross_id": "string | null"
}
```

- `cross_type` se calcula aplicando las reglas de sección 6.1 y 6.2 sobre los valores de `StochasticReading`.
- `cross_id` se calcula según la sección 8.3 cuando `cross_type` es válido; es `null` cuando `cross_type == "NO_CROSS"`.
- Si `stochastic_14_3_3` devolvió `None` (no hay suficientes velas), este campo contiene `{"cross_type": "NO_CROSS", "cross_id": null}`.

### 11.4 Valores de `next_condition`

| Valor | Significado |
|-------|-------------|
| `"AGUARDAR_CRUCE_M15"` | La POI está en proximidad pero el estocástico no presenta cruce vigente. Esperar a que el estocástico M15 presente un cruce válido del tipo requerido en la próxima vela cerrada. |
| `"AGUARDAR_POI_EN_ZONA"` | El estocástico presenta cruce vigente pero no hay POI elegible en proximidad. Esperar a que el precio entre en proximidad de una POI elegible. |
| `"AGUARDAR_FIN_CICLO"` | Hay ciclo activo en la misma dirección. Esperar a que el ciclo se cierre antes de reevaluar. |
| `"AGUARDAR_CRUCE_NUEVO"` | El cruce actual venció o fue consumido. Esperar un nuevo cruce M15 válido. |
| `"SIN_CONDICION"` | No hay condición pendiente definida (STATUS terminal o no aplicable). |

---

## 12. Algoritmo de evaluación (secuencia)

El evaluador sigue esta secuencia exacta. En cualquier paso donde la condición falle, se devuelve el `status` correspondiente y se detiene la evaluación.

### Paso 1: Obtener POI candidatas

```
candidatas = [
    p para p en market_objects
    si p.type in (ObjectType.FVG, ObjectType.ORDER_BLOCK)
    y p.origin_tf in ("D1", "H4", "H1")
    y p.state in (ObjectState.ACTIVE, ObjectState.PARTIALLY_MITIGATED)
    y p.symbol == symbol_evaluado
    y math.isfinite(p.zone_high) and math.isfinite(p.zone_low)
    y p.zone_high >= p.zone_low
    y p.tradable_time is not None
    y p.tradable_time <= decision_time
]
```

Si `candidatas` está vacía: `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

**Nota:** `Role.POI` NO es un filtro en este paso. El motor operativo publica con `Role.REFINEMENT`; eso es aceptable. Ver sección 2.4.

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

### Paso 4: Detectar conflicto de POI opuestas

```
si existe p1 en cercanas con direction = +1
y existe p2 en cercanas con direction = -1
y p1 y p2 están superpuestas (sección 9.4):
    aplicar regla de conflicto 9.4
    → puede resultar en status = "CONFLICT_OPPOSITE_POI" o en selección de una de las dos
```

### Paso 5: Seleccionar POI más cercana

```
poi = poi_selected(cercanas, price)  // sección 9
```

### Paso 6: Obtener velas M15 y calcular estocástico

```
candles = closed_m15_candles(symbol, count=80)
candles_available = len(candles)

si candles_available < 20:
    status = "INSUFFICIENT_CANDLES"

reading = stochastic_14_3_3(candles, config)

si reading is None:
    status = "INSUFFICIENT_CANDLES"
```

### Paso 7: Evaluar cruce

```
cross_type = evaluar_cross_type(reading, poi.direction)  // sección 6

si cross_type == "NO_CROSS":
    status = "NO_CROSS"
```

### Paso 8: Calcular cross_id

```
si cross_type es válido:
    cross_id = calcular_cross_id(cross_type, candles)
else:
    cross_id = None
```

### Paso 9: Verificar caducidad del cruce

```
si cross_vencido(reading, poi.direction, candles, cross_id, registro_cross_ids_consumidos):
    status = "CROSS_EXPIRED"
```

La función `cross_vencido` aplica:
1. Inversión K/D (sección 8.2.1).
2. Tres velas sin nuevo cruce válido (sección 8.2.2).
3. No verificabilidad de temporalidad (sección 8.2.3).
4. cross_id ya consumido (sección 8.3).

### Paso 10: Verificar ciclo activo

```
si bot.cycle is not None y bot.cycle.direction == direction_string(poi.direction):
    status = "CYCLE_ACTIVE_SAME_DIRECTION"
```

### Paso 11: Entrada válida

```
si todos los pasos anteriores pasaron:
    registro_cross_ids_consumidos.agregar(cross_id)
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

return "NO_CROSS"
```

### 13.3 `calcular_cross_id(cross_type, candles)`

```
# Firma inmutable de la última vela (candles[-1])
ultima_vela = candles[-1]
firma_vela = hash_deterministico(
    high=ultima_vela.high,
    low=ultima_vela.low,
    close=ultima_vela.close,
    posicion=len(candles) - 1
)

return f"{cross_type}_{firma_vela}"
```

El `hash_deterministico` debe ser reproducible: mismo input → mismo hash. Se recomienda usar una función hash determinista simple (ej. hashlib.sha256 de la representación serialized de los campos).

### 13.4 `cross_vencido(reading, direction, candles, cross_id, registro_consumidos)`

```
# 1. Verificar si cross_id ya fue consumido
si cross_id is not None y cross_id in registro_consumidos:
    return True  # cruce ya consumido

# 2. Verificar inversión K/D
si direction == +1:
    si reading.k <= reading.d:
        return True  # vencido por inversión
si direction == -1:
    si reading.k >= reading.d:
        return True  # vencido por inversión

# 3. Verificar caducidad por 3 velas
# Requiere al menos 4 velas (1 del cruce + 3 para verificar)
si len(candles) < 4:
    return True  # no verificable → vencido

ultimas_indices = [len(candles) - 3, len(candles) - 2, len(candles) - 1]
for idx in ultimas_indices:
    lectura_idx = stochastic_14_3_3(candles[:idx+1], config)
    si lectura_idx is not None:
        si _hubo_cruce_valido_en_vela(candles, config, idx, direction):
            return False  # hay un nuevo cruce válido

return True  # ninguna de las 3 velas tenía cruce válido → vencido
```

### 13.5 `estetablece_conflicto_opuestas(cercanas)`

```
para cada par (p1, p2) en cercanas donde p1.direction != p2.direction:
    si max(p1.zone_low, p2.zone_low) < min(p1.zone_high, p2.zone_high):
        # zonas superpuestas
        return True, (p1, p2)
return False, None
```

---

## 14. Parámetros no modificables (congelados para evaluación histórica)

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| `ObjectType` elegibles | `ObjectType.FVG`, `ObjectType.ORDER_BLOCK` | Definido por la ontología del motor ICT. |
| `origin_tf` elegibles (POI-TFs acordadas) | `"D1"`, `"H4"`, `"H1"` | Temporalidades acordadas para POI. Coinciden con `_POI_TFS` del motor. M15 es TF de ejecución, no POI-TF. |
| `ObjectState` elegibles | `ObjectState.ACTIVE`, `ObjectState.PARTIALLY_MITIGATED` | Estados no-terminales y no-mitigados completos. |
| Estados excluidos | `CREATED`, `MITIGATED`, `INVALIDATED`, `EXPIRED`, `CONSUMED` | Ver sección 2.3. |
| `Role` como filtro | **NO APLICA** | El contrato NO filtra por `Role`. Ver sección 2.4. |
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
| Caducidad por tiempo | 3 velas M15 sin nuevo cruce válido | Ventana de vigencia de la señal. |
| Mínimo de velas para verificación | `4` (1 del cruce + 3 para verificar) | Requisito para verificar la caducidad por tiempo. |
| `cross_id` | `f"{cross_type}_{hash(candles[-1])}"` | Identificador único que impide reutilización. |

---

## 15. Casos de prueba semánticos (sin código)

### Caso A: Entrada válida COMPRA

- Existe FVG alcista (`ObjectType.FVG`, `origin_tf="H1"`, `direction=+1`, `state=ACTIVE`, `symbol="EURUSD"`).
- `zone_low`, `zone_high` definidos y finitos.
- Precio actual (ask) está a 2 pips de `zone_low` (fuera de zona, dentro de tolerancia).
- `closed_m15_candles` devuelve 80 velas.
- `stochastic_14_3_3` devuelve `StochasticReading` con `previous_k=18.0`, `previous_d=19.0`, `k=25.0`, `d=22.0`.
- `cross_type = "CROSS_UP_FROM_OVERSOLD"`.
- `cross_id` calculado y no consumido.
- No hay ciclo activo en dirección `"BUY"`.
- **Resultado esperado:** `status = "ENTRY_VALID"`, `poi_selected = FVG`, `distance_pips = 2.0`, `cross_id` registrado en `registro_cross_ids_consumidos`.

### Caso B: Cruce bajista sin POI en proximidad

- Estocástico presenta `CROSS_DOWN_FROM_OVERBOUGHT`.
- No hay ninguna POI (`FVG` o `OB`) con `origin_tf` en POI-TFs acordadas y `state` elegible en los 5 pips alrededor del precio.
- **Resultado esperado:** `status = "NO_ELIGIBLE_POI_NEAR_PRICE"`.

### Caso C: POI con `origin_tf = "M15"` (no elegible)

- Existe FVG detectado en M15 (`origin_tf="M15"`, `state=ACTIVE`).
- Aunque está cerca del precio y el estocástico presenta cruce, el FVG no es elegible porque `origin_tf="M15"` no es una POI-TF acordada.
- **Resultado esperado:** `status = "NO_ELIGIBLE_POI_NEAR_PRICE"` (la POI no es elegible por temporalidad, no por rol).

### Caso D: POI con estado `MITIGATED`

- Existe FVG con `state = ObjectState.MITIGATED` y `origin_tf="H4"`.
- Aunque está cerca del precio y el estocástico presenta cruce, el FVG está en estado excluido.
- **Resultado esperado:** `status = "NO_ELIGIBLE_POI_NEAR_PRICE"` (la POI no es elegible, no se considera).

### Caso E: Doble POI en proximidad (desempate)

- FVG A: `distance_pips = 3.0`, `creation_time = T1`.
- FVG B: `distance_pips = 3.0`, `creation_time = T2` donde `T2 > T1`.
- Ambas con `direction = +1`, `origin_tf="H4"`.
- **Resultado esperado:** `poi_selected = FVG B` (más reciente por `creation_time`).

### Caso F: Cruce vencido por inversión K/D

- Hubo cruce alcista en vela t-3: `previous_k=18`, `previous_d=19`, `k=25`, `d=22`.
- En vela t-2: `k=20`, `d=23` (k < d, relación invertida).
- En vela t-1: `k=18`, `d=21` (k < d, seguimos invertidos).
- En vela t (actual): `k=17`, `d=20` (k < d).
- No hay nuevo cruce válido en las últimas 3 velas.
- **Resultado esperado:** `status = "CROSS_EXPIRED"`.

### Caso G: Cruce no verificable por insuficientes velas

- `closed_m15_candles` devuelve solo 30 velas (suficientes para el cálculo del estocástico, que requiere 20).
- Se detecta un cruce válido.
- Pero para verificar la caducidad por 3 velas se necesitan al menos 4 velas (1 del cruce + 3 para verificar). Con 30 velas hay suficiente.
- **Resultado esperado:** El cruce es verificable. Si las 3 velas anteriores no tienen nuevo cruce, `status = "CROSS_EXPIRED"`.

### Caso H: Cruce no verificable (menos de 4 velas después del cruce)

- `closed_m15_candles` devuelve 20 velas exactas (mínimo para cálculo).
- Se detecta un cruce válido en `candles[-1]`.
- No hay velas adicionales para verificar la caducidad (necesitaríamos al menos 4 velas totales, y con 20 hay suficiente para el cálculo pero el cruce está en la última vela; las 3 velas anteriores existen, así que sí hay 4 velas: la del cruce + 3 anteriores).
- Esto funciona si `candles[-1]` es la vela del cruce y hay al menos 3 velas antes (`candles[-4]` existe).
- **Resultado esperado:** Verificable si `len(candles) >= 4`. No verificable si `len(candles) < 4`.

### Caso I: `cross_id` ya consumido

- Evaluación 1: `status = "ENTRY_VALID"`, `cross_id = "CROSS_UP_FROM_OVERSOLD_abc123"`. Se registra en `registro_cross_ids_consumidos`.
- Evaluación 2 (con mismas velas, misma POI): el cruce presente tiene el mismo `cross_id = "CROSS_UP_FROM_OVERSOLD_abc123"`.
- **Resultado esperado:** `status = "CROSS_EXPIRED"`, `reason = "Cruce ya consumido en evaluación previa"`.

### Caso J: Conflicto entre POI opuestas superpuestas

- FVG alcista (`direction=+1`, `origin_tf="H4"`, `zone=[1.0990, 1.1000]`) en proximidad.
- OB bajista (`direction=-1`, `origin_tf="H1"`, `zone=[1.0995, 1.1005]`) en proximidad.
- Las zonas se solapan: `[1.0995, 1.1000]`.
- Precio (bid/ask) está dentro de la superposición (`1.0998`).
- Ambas están dentro de la zona → conflicto.
- Prioridad por temporalidad: H4 > H1 → se selecciona FVG alcista.
- **Resultado esperado:** `poi_selected = FVG alcista`, `status = "ENTRY_VALID"` (si hay cruce M15 coherente con COMPRA) o `status = "NO_CROSS"` (si hay cruce bajista) o `status = "ENTRY_VALID"` (si hay cruce alcista).

### Caso K: POI con `origin_tf` no acordado (ej. `"W1"`)

- Existe FVG con `origin_tf="W1"`.
- **Resultado esperado:** No es POI elegible. `status = "NO_ELIGIBLE_POI_NEAR_PRICE"` (el objeto no cumple el criterio de temporalidad acordada).

---

## 16. Invariantes y garantías

1. **Sin términos ambiguos:** todos los estados, umbrales, condiciones y resultados están enumerados explícitamente. No hay "aproximadamente", "cerca", "razonable".
2. **Sin look-ahead:** el estocástico se calcula solo sobre velas cerradas (`closed_m15_candles`). El cruce se evalúa sobre `candles[-1]` (vela más reciente cerrada).
3. **Parámetros fijos antes de evaluación:** todos los umbrales, periods y tolerancias se definen en sección 14 antes de ejecutar cualquier evaluación histórica.
4. **POI solo de fuente canónica:** `engine/detectors/fvg.py`, `engine/detectors/ob.py`, `engine/ltf_canonical_feed.py` son las únicas fuentes de objetos de mercado para la evaluación operativa. No se crean POI fuera del motor.
5. **Estocástico solo de fuente canónica:** `stochastic_14_3_3` de `mechanical_bot/core.py` es la única función de cálculo. No se reimplementa.
6. **Velas M15 solo de fuente canónica:** `closed_m15_candles` de `mechanical_bot/mt5_adapter.py` es el único accessor. No se construye manualmente.
7. **Ciclos idempotentes:** reevaluar con los mismos datos produce el mismo `status`. No hay efectos secundarios en el evaluador (solo lectura), salvo el registro de `cross_ids` consumidos que es un efecto de estado explícito documentado.
8. **Role.POI no es filtro:** el evaluador no filtra por `Role.POI`. El motor operativo publica con `Role.REFINEMENT`; eso es aceptable. Ver sección 2.4.
9. **FVG no eliminado:** el FVG es tipo elegible igual que OB. No hay restricción de temporalidades silenciosa: M15 sigue siendo detectado por el motor, pero no es POI-TF acordada para esta estrategia.
10. **`cross_id` único y persistente:** cada cruce válido tiene un identificador que lo hace único e impide reutilización. El registro de `cross_ids` consumidos es explícito y auditable.

---

## 17. Historial de versiones

| Versión | Fecha | Autor | Cambios |
|---------|-------|-------|---------|
| 1.0 | 2026-09-14 | D6 Research | Creación inicial. Congelamiento de parámetros para evaluación histórica POI canónica + estocástico M15. |
| 2.0 | 2026-09-14 | D6 Research | Corrección de contradicciones del v1: (1) elimina `Role.POI` como condición de elegibilidad, adopta criterio alternativo (tipo + temporalidad acordada + estado + símbolo + geometría + disponibilidad temporal); (2) define POI-TFs acordadas (D1/H4/H1) y exclusión de M15 como POI-TF; (3) define prioridad entre objetos superpuestos; (4) define conflicto entre POI opuestas; (5) define `cross_id` único y no reutilización; (6) define verificabilidad de la temporalidad del cruce; (7) define precio de referencia (ask/bid) por dirección; (8) define coincidencia entre contacto con zona y cruce M15. Decisión explícita en sección 2.4: el contrato NO exige `Role.POI`. |

---

## 18. Relación con otros contratos de la misión

| Contrato | Relación con este |
|----------|-------------------|
| `CONTRATO_HISTORICAL_EVENT_OBJECT_PRODUCER_V1.md` | Define cómo se construyen los objetos históricos para backtest. En ese flujo, `Role.POI` se asigna a OBs de H4 (línea 105 de `historical_event_objects.py`). Este contrato v2 reconoce que `Role.POI` existe en ese contexto pero no lo exige para la estrategia simplificada. |
| `CONTRATO_MT5_OPERATIONAL_SNAPSHOT_V1.md` | Define el snapshot operativo que incluye ask/bid. Este contrato v2 usa el snapshot para definir el precio de referencia por dirección (sección 4.2). |
| `CONTRATO_FVG_OB_RELACION.md` | Define relaciones entre FVG y OB. Este contrato usa esas relaciones implícitamente (los objetos son los mismos). |
| `CONTRATO_EPISODES_FUNNEL_V1.md` | Gobierna el pipeline de evaluación de episodios. Este contrato es un insumo del evaluador que alimenta el funnel. |
| `ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md` | Autoriza avance autónomo en investigación. Este contrato es producto de esa autonomía en el ámbito de MC-20260914-083000-poi-stoch-m15. |

---

*Documento congelado. No se modifica durante la evaluación histórica. Cualquier cambio requiere nueva versión y reevaluación.*
