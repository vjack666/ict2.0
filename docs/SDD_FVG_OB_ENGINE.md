# SDD — EVOLUCIÓN DEL MOTOR ICT: FVG + ORDER BLOCKS

**Versión:** 1.0  
**Fecha:** 2026-08-17  
**Estado:** Contrato de diseño para implementación Hermes  
**Fuente de verdad:** `docs/ict/SPEC_TESIS_FORMAL.md` + enmienda vigente de eliminación de OTE

## 1. Propósito

Diseñar una evolución del motor que convierta FVG y Order Blocks en entidades temporales y causales integradas con Swing/BOS/CHOCH, liquidez y displacement.

El diseño debe favorecer aprendizaje posterior: el dataset de señales debe conservar contexto y lineage, no sólo la etiqueta final.

## 2. Modelo conceptual

```text
Market Data
   ↓
Swing / Structure
   ↓
Liquidity → Sweep
   ↓
Displacement
   ↓
BOS / CHOCH / MSS
   ↓
PD Arrays
   ├── FVG
   ├── OB
   ├── Breaker
   └── BPR
   ↓
POI / Quality
   ↓
Retest / Execution
   ↓
SL / TP / Outcome
```

## 3. Entidades

### FVG

Campos mínimos:

- `id`
- `direction`
- `timeframe`
- `created_at`
- `confirmed_at`
- `tradable_at`
- `top`
- `bottom`
- `midpoint`
- `size`
- `state`
- `mitigation_level`
- `first_touch_at`
- `touch_count`
- `invalidated_at`
- `age`
- `displacement_id`
- `structure_event_id`
- `sweep_id`
- `quality`

Estados recomendados:
`CREATED → ACTIVE → PARTIALLY_MITIGATED → MITIGATED` y `INVALIDATED/EXPIRED` según reglas de la tesis.

### Order Block

Campos mínimos:

- `id`
- `direction`
- `timeframe`
- `source_candle`
- `created_at`
- `confirmed_at`
- `tradable_at`
- `high`
- `low`
- `state`
- `body_ratio`
- `displacement_id`
- `structure_event_id`
- `sweep_id`
- `mitigation`
- `invalidated_at`
- `breaker_id`
- `quality`

### Breaker

Debe conservar referencia al OB padre y al evento que lo invalidó. Sólo puede activarse como Breaker cuando la transición de estructura requerida por la tesis esté confirmada.

### BPR / composite POI

Debe representar una relación entre componentes, no duplicar sus datos. Ejemplo:

`BPR = OB#12 + FVG#33 + overlap_range`.

### POI

POI es un **rol** asignado a uno o más PD Arrays. Debe conservar:

- componentes;
- TF;
- dirección;
- dealing-range context;
- HTF alignment;
- displacement strength;
- stacking;
- freshness;
- quality score;
- lineage.

No debe ocultar ni destruir los objetos originales.

## 4. Lineage

Cada objeto derivado debe poder responder:

- ¿Qué sweep lo precedió?
- ¿Qué displacement lo creó?
- ¿Qué evento de estructura confirmó el movimiento?
- ¿Qué FVG/OB nació de ese movimiento?
- ¿Qué POI se formó?
- ¿Cuándo se volvió tradable?

La relación debe ser unidireccional respecto al tiempo histórico y auditable.

## 5. Temporalidad

Separar explícitamente:

- HTF: bias/contexto.
- ITF: zona/POI.
- EXEC: confirmación y entrada.

Un objeto HTF no puede usar información posterior al timestamp de la decisión EXEC para validar una señal histórica.

## 6. Ejecución

La entrada debe poder esperar:

`structure confirmation → zone creation → zone becomes tradable → price returns → execution confirmation → entry`.

No se debe confundir creación de zona con ejecución.

## 7. Calidad

La calidad es una función explicable, no un gate opaco. Features iniciales:

- sweep asociado;
- displacement fuerte;
- BOS/CHOCH/MSS asociado;
- FVG fresco;
- OB fresco;
- OB+FVG overlap;
- stacking multi-TF;
- HTF alignment;
- killzone, si corresponde;
- edad y mitigación.

Los pesos deben poder medirse por ablación y no deben congelarse como verdad absoluta.

## 8. Backtest y aprendizaje

Todas las entidades deben ser observables en el backtest para poder medir:

- creación;
- confirmación;
- primer toque;
- entrada;
- mitigación;
- invalidación;
- MFE;
- MAE;
- outcome R.

El sistema debe permitir comparar cohortes con y sin FVG/OB.

## 9. Seguridad contra look-ahead

Toda función que consume datos futuros para confirmar una entidad debe producir un timestamp de confirmación. La entidad no puede participar en una decisión antes de `tradable_at`.

Los tests deben mutar o truncar el futuro y comprobar que las señales históricas anteriores no cambian.

## 10. Compatibilidad

La evolución no debe romper Swing/BOS/CHOCH existentes. Si una nueva implementación modifica resultados de estructura, Hermes debe aislar primero el cambio y demostrar que es intencional.

## 11. Observabilidad

Cada señal debe poder explicar, como mínimo:

`bias → liquidity → sweep → displacement → structure → PD array → POI → retest → entry → SL → TP`.

Si una señal no puede explicar su lineage, debe considerarse incompleta para aprendizaje.
