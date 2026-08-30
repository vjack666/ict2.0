# Contrato — Episodes / Funnel causal v1

**Estado:** NORMATIVO PARA IMPLEMENTACIÓN LOCAL
**Fecha:** 2026-08-30
**Padre:** `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`
**Departamentos:** D2 Ingeniería, D5 Assurance, D1 Documentación, D7 Delivery
**Autoridad de entrada:** `engine/market_state.py` y `engine/setup_builder.py`

## 1. Propósito

Convertir snapshots históricos de `MarketState(T)` y `Setup(T)` en episodios
causales, deterministas y auditables. El Funnel debe conservar tanto los
aceptados como los rechazados y explicar cada reducción.

```text
MarketState(T)
    ↓
Setup(T) desde projection_at(T)
    ↓
validación temporal + lineage + identidad
    ↓
Episode causal
    ↓
dataset descriptivo auditable
```

Un Episode es una unidad de agrupación histórica. No es una orden, señal,
predicción ni prueba de edge.

## 2. Límites absolutos

- No recalcular Lifecycle, MarketState, relaciones ni AHF.
- No usar `active()` del presente cuando se necesita `T`.
- No mutar `MarketObject`, `MarketState` ni `Setup` de entrada.
- No usar velas posteriores a `decision_time` para aceptar o rechazar.
- No mezclar el label de resultado futuro con el estado causal conocido en T.
- No entrenar IA, hacer trading, backtest de rendimiento ni reclamar edge.
- No modificar datasets ni inventar sustitutos de procedencia.

## 3. Entrada obligatoria

Cada candidato debe provenir de:

```text
MarketState.projection_at(T)
build_setups_at(market_state, T, context)
```

Debe conservar, como mínimo:

```text
symbol, decision_time, observation_time, tradable_time,
context_htf, poi, refinement, confirmation, trigger,
direction, setup_eligibility, object ids, origin_tf, authority_tf,
parent/related lineage, contract_version, generator_commit
```

Si falta identidad, tiempo, autoridad o linaje requerido, el registro se
rechaza de forma explícita; nunca se completa silenciosamente.

## 4. Definición de Episode v1

En v1, un Episode representa **un Setup canónico** y todas sus observaciones
repetidas. No se fusionan setups distintos por cercanía temporal, mismo POI o
misma dirección; esa hipótesis requeriría un contrato v2.

La identidad debe ser estable y reproducible:

```text
canonical_setup_key = symbol |
  decision_time |
  context_id | poi_id | refinement_id |
  confirmation_id | trigger_id | direction

episode_id = EP_<sha256(canonical_setup_key)[0:24]>
```

No se acepta UUID aleatorio como identidad de evidencia. Dos observaciones con
la misma clave representan el mismo episodio y se deduplican sin aumentar el
conteo.

## 5. Estados y razones canónicas

### Estados del registro

```text
ACCEPTED       candidato convertido en Episode válido
REJECTED       candidato descartado por una razón explícita
SUPERSEDED     setup cuyo POI/estructura quedó invalidado
```

### Razones de rechazo mínimas

```text
MISSING_SNAPSHOT
MISSING_IDENTITY
MISSING_REQUIRED_COMPONENT
OUT_OF_CONTEXT
SETUP_BLOCKED
SETUP_SUPERSEDED
INVALID_AUTHORITY
TEMPORAL_ORDER
FUTURE_DATA
MISSING_LINEAGE
INVALID_LINEAGE
DUPLICATE_EVENT
DUPLICATE_SETUP
CONFIG_MISMATCH
```

La lista puede ampliarse solo mediante modificación contractual. Cada rechazo
debe incluir `reason`, `stage`, `object_refs` y `observation_time`.

## 6. Tiempo y causalidad

1. `decision_time` es el instante al que se evalúa el snapshot.
2. Todo componente aceptado debe tener `available_time <= decision_time`.
3. `confirmation_time <= tradable_time <= decision_time` cuando esos campos
   existan para el componente.
4. Un objeto H4 conserva `authority_tf=H4`; una observación M15 no puede
   cambiar su estado oficial.
5. `outcome`, `label_available_time` y métricas posteriores son campos de
   etiquetado futuro; no participan en aceptación del Episode.
6. Una barra/evento fuera de orden es `TEMPORAL_ORDER`, no se reordena en
   silencio.

## 7. Lineage y validación

Un Episode aceptado debe poder recorrer:

```text
context_htf → poi → refinement → confirmation → trigger
```

Cada referencia debe existir, tener dirección compatible y respetar el orden
temporal. Se rechazan huérfanos, ciclos, referencias futuras y relaciones que
no estén presentes en el snapshot causal.

## 8. Salida mínima

El artefacto del Funnel debe contener:

```json
{
  "contract_version": "EPISODES_FUNNEL_V1",
  "generator_commit": "...",
  "config": {},
  "provenance": {},
  "records": [],
  "episodes": [],
  "rejections": [],
  "aggregates": {},
  "gates": {}
}
```

`records` conserva entradas aceptadas y rechazadas. `episodes` solo contiene
los aceptados. `aggregates` debe separar por TF, dirección y etapa sin ocultar
ceros. El checksum debe excluir campos no deterministas como `generated_at`.

## 9. Gates obligatorios

| Gate | Requisito | Estado para iniciar implementación |
|---|---|---|
| E0 | Contrato y SDD presentes y enlazados | PASS documental |
| E1 | Entrada exclusiva `projection_at(T)` | Test negativo contra estado presente |
| E2 | FULL/PREFIX literal en varias decisiones | Obligatorio |
| E3 | Identidad estable e idempotencia | Obligatorio |
| E4 | Rechazos, lineage y tiempos completos | Obligatorio |
| E5 | Determinismo y checksum reproducible | Obligatorio |
| E6 | Suite focal y suite completa verdes | Obligatorio |
| E7 | Bitácora, índice, Graphify y commit local | Obligatorio |

Un gate ausente es `REVIEW`; un gate fallido es `BLOCKED`. Ningún resultado
parcial autoriza declarar `COMPLETED`.

## 10. Criterio de cierre

El contrato queda satisfecho cuando una segunda ejecución con el mismo corpus,
configuración y commit produce el mismo conjunto de Episodes, rechazos,
agregados y checksum lógico, y cuando FULL/PREFIX coincide literalmente para
todo lo observable en cada T probado.
