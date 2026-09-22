# Contrato — Episodes / Funnel causal v1

> Enmienda vigente de Ruben (2026-09-11): se autoriza avanzar autonomamente con entrenamiento y evaluacion de IA sobre datos existentes e inmutables. No se requiere una nueva autorizacion humana para cada fase. La ausencia de licencia o permiso escrito de Dukascopy deja de ser un bloqueo interno y no se solicitara licencia. Rige `docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md` sobre las restricciones anteriores de este documento. Los controles tecnicos se verifican durante el trabajo; sus fallos se reportan sin alterar datos ni fabricar certificaciones. Esta autorizacion no habilita trading ni promocion automatica a produccion.


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

Debe conservar, como mínimo, los campos reales producidos por
`engine/setup_builder.py` y `engine/market_object.py` (la entrada es un
`Setup` compuesto por `build_setups_at(ms, T, ctx)`, donde `T` es el
`decision_time`; no existe un campo `observation_time` aparte de `T`):

```text
symbol, decision_time (= T),
candidate_time (disponibilidad del componente; ver §6.2),
tradable_time (si existe en el componente),
context_htf, poi, refinement, confirmation, trigger (refs a MarketObject),
direction, eligibility (SetupEligibility),
object ids = .id de cada componente (context_htf.id, poi.id, ...),
origin_tf, authority_tf (por componente),
parent/related lineage (MarketObject.parent_object / related_objects),
contract_version (= EPISODES_FUNNEL_V1; campo propio del funnel, no del motor),
generator_commit (ver §8: capturado por el runner vía `git rev-parse HEAD`)
```

Si falta identidad, tiempo, autoridad o linaje requerido, el registro se
rechaza de forma explícita; nunca se completa silenciosamente.

## 4. Definición de Episode v1

En v1, un Episode representa **un Setup canónico** y todas sus observaciones
repetidas. No se fusionan setups distintos por cercanía temporal, mismo POI o
misma dirección; esa hipótesis requeriría un contrato v2.

La identidad debe ser estable y reproducible. `decision_time` es el `T` de
entrada. Cada `*_id` es el `.id` del `MarketObject` correspondiente; si un
componente es `None` (p.ej. setup incompleto) se usa el sentinel `NONE` para
que la clave sea determinista:

```text
canonical_setup_key = symbol |
  decision_time |
  context_id | poi_id | refinement_id |
  confirmation_id | trigger_id | direction

# context_id    = context_htf.id    or "NONE"
# poi_id        = poi.id            or "NONE"
# refinement_id = refinement.id     or "NONE"
# confirmation_id = confirmation.id or "NONE"
# trigger_id    = trigger.id        or "NONE"

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

### Mapeo desde `SetupEligibility`

El estado del Episode se deriva de la elegibilidad del `Setup` compuesto en T,
sin reintroducir lógica de elegibilidad (la autoridad es `setup_builder`):

```text
ELIGIBLE       → ACCEPTED    (sin razón de rechazo)
SUPERSEDED     → SUPERSEDED  (reason = SETUP_SUPERSEDED)
BLOCKED        → REJECTED    (reason = SETUP_BLOCKED)
OUT_OF_CONTEXT → REJECTED    (reason = OUT_OF_CONTEXT)
```

Cualquier otro estado de elegibilidad o componente faltante se resuelve con la
razón canónica correspondiente antes de formar el Episode.

La lista puede ampliarse solo mediante modificación contractual. Cada rechazo
debe incluir `reason`, `stage`, `object_refs` y `decision_time`.

## 6. Tiempo y causalidad

1. `decision_time` (el `T` de entrada) es el instante al que se evalúa el
   snapshot; todas las proyecciones vienen de `projection_at(T)`, por lo que
   ningún objeto con `creation_time > T` puede aparecer.
2. `available_time` de un componente se define como su `candidate_time`
   (tiempo en que el objeto es detectable). Se exige `available_time <=
   decision_time` para todo componente aceptado.
3. `confirmation_time <= tradable_time <= decision_time` cuando esos campos
   existan en el `MarketObject` componente.
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
| E2 | FULL/PREFIX literal: el funnel es determinista causal — `build_episodes` sobre datos FULL == sobre datos truncados en T, para varias decisiones T (distinto del gate G7 de MarketState) | Obligatorio |
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

## 11. Enmienda de implementación seis-TF — 2026-09-21

La implementación local autorizada para conectar seis temporalidades al Funnel
v1 es:

```text
engine/sixtf_marketobject_connector.py
```

Este conector es compatible con el contrato porque:

1. Publica objetos por `MarketState.ingest()` y lee por `projection_at(T)`.
2. Convierte la fábrica/contexto seis-TF existente en `MarketObject` con
   identidad estable.
3. Mantiene `parent_object` / `related_objects` explícitos.
4. Valida `HierarchicalLineage(require_all_six_tfs=True)` antes de aceptar.
5. Alimenta `build_setups_at()` y después `build_episodes()`.
6. Conserva rechazos explícitos; no oculta candidatos rechazados.
7. Mantiene `can_trade=false`, `edge_claimed=false` y `diagnostic_only=true`.

Evidencia de cierre de la enmienda:

```text
tests/test_sixtf_marketobject_connector.py -> 4 passed
regresion relacionada -> 38 passed
reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json
```

Esta enmienda no cambia el criterio de cierre global del contrato. Para ventana
histórica completa sigue siendo obligatorio ejecutar FULL/PREFIX sobre múltiples
`decision_time` antes de usar la salida para backtest económico o dataset IA.

## 12. Evidencia de ventana FULL/PREFIX — 2026-09-21

La obligacion de FULL/PREFIX multi-`decision_time` fue ejecutada en modo shadow
diagnostico mediante:

```text
scripts/audit/run_sixtf_marketobject_connector.py window
```

Artefacto:

```text
reports/audits/experiments/mission3/sixtf_window_report.json
```

Resultado de la ventana auditada:

```text
status=PASS
decision_count=13
episode_count=13
rejection_count=13
full_prefix_failure_count=0
all_lineage_valid=true
all_six_tfs_complete=true
window_checksum=77b70956af5e1d7036f97633229ade3f6ca05669728d359658698955e82d68df
```

Este resultado satisface el gate causal de ventana para la muestra auditada. No
autoriza trading, no demuestra edge y no sustituye el backtest economico
aislado.

## 13. Consumo economico aislado — 2026-09-21

El primer consumidor economico aislado compatible con Episodes seis-TF es:

```text
backtest/sixtf_episode_backtest.py
scripts/audit/run_sixtf_episode_backtest.py
```

Propiedades:

- consume Episodes ya aceptados;
- no crea señales;
- resuelve outcome solo con M1 futuro;
- aplica costes explicitos mediante `backtest.economics`;
- conserva `can_trade=false` y `edge_claimed=false`.

Resultado de la ventana auditada:

```text
status=PASS_DIAGNOSTIC
economic_status=REVIEW_NEGATIVE_EXPECTANCY
decision_count=553
mean_net_R=-0.5733476394850038
sum_net_R=-267.1800000000118
```

Este resultado no prueba edge; al contrario, bloquea cualquier promocion
economica hasta calibrar reglas/filtros y volver a auditar.
