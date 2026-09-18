# SDD — Episodes / Funnel causal v1

> Enmienda vigente de Ruben (2026-09-11): se autoriza avanzar autonomamente con entrenamiento y evaluacion de IA sobre datos existentes e inmutables. No se requiere una nueva autorizacion humana para cada fase. La ausencia de licencia o permiso escrito de Dukascopy deja de ser un bloqueo interno y no se solicitara licencia. Rige `docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md` sobre las restricciones anteriores de este documento. Los controles tecnicos se verifican durante el trabajo; sus fallos se reportan sin alterar datos ni fabricar certificaciones. Esta autorizacion no habilita trading ni promocion automatica a produccion.


**Estado:** NORMATIVO; implementación local revisada, pendiente únicamente de auditoría independiente y GO de publicación
**Fecha:** 2026-08-30
**Contrato:** `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`
**Padre:** `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`

## 1. Objetivo

Construir una capa de agrupación y auditoría sobre setups históricos ya
compuestos. La capa debe responder:

```text
qué setup existía en T,
por qué fue aceptado o rechazado,
qué episode representa,
qué linaje y temporalidad lo justifican,
y qué información futura queda separada como label.
```

## 2. Arquitectura autorizada

```text
engine/market_state.py
        │ projection_at(T)
        ▼
engine/setup_builder.py
        │ Setup(T), elegibilidad
        ▼
engine/episodes.py          ← única capa nueva de composición v1
        │ Episode + FunnelRecord
        ▼
audits/codigo/episodes.py   ← auditoría, no autoridad de cálculo
        ▼
reports/audits/episodes/    ← evidencia reproducible
```

`engine/episodes.py` no puede importar `backtest/`, no puede llamar a
`lifecycle.evaluate`, no puede avanzar `MarketState` y no puede recalcular AHF,
FVG/OB, relaciones ni Setup Builder.

La única fuente de candidatos es `build_setups_at(ms, T, ctx)`, que devuelve
`Setup` compuestos por `setup_builder`. El funnel no reimplementa la
composición ni la elegibilidad: deriva el estado del Episode directamente de
`Setup.eligibility` (`SetupEligibility` → `ACCEPTED`/`REJECTED`/`SUPERSEDED`).

## 3. Componentes

### 3.1 `Episode`

Debe contener `episode_id`, `canonical_setup_key`, `symbol`, `decision_time`,
`direction`, referencias a los cinco componentes del setup (sus `.id`),
temporalidades, estado (derivado de `SetupEligibility`), razones, lineage,
`contract_version` y metadatos de procedencia.

### 3.2 `FunnelRecord`

Debe conservar cada candidato y su etapa (`SNAPSHOT`, `SETUP`, `TEMPORAL`,
`LINEAGE`, `IDENTITY`, `DEDUPLICATION`, `EPISODE`) con `accepted`, `reason`,
`decision_time` y referencias de objetos.

### 3.3 Runner de auditoría

El runner debe producir un reporte JSON determinista con conteos por etapa,
dirección y TF; razones de rechazo; lineage; duplicados; provenance; checksum;
`aggregated_status`; y resultado FULL/PREFIX.

## 4. Pipeline causal

1. Leer configuración y manifiesto; validar identidad.
2. Obtener snapshots en una lista de decisiones T declarada.
3. Construir setups únicamente desde cada snapshot.
4. Validar tiempos, autoridad y lineage.
5. Formar la clave canónica y deduplicar de forma idempotente.
6. Crear el Episode aceptado o registrar el rechazo.
7. Separar cualquier outcome/label futuro del registro causal.
8. Agregar resultados sin borrar poblaciones ni ceros.
9. Repetir con FULL/PREFIX y comparar literalmente.

## 5. FULL/PREFIX

Para cada decisión T:

```text
FULL(snapshot_at(T)) == PREFIX(snapshot_at(T))
```

La comparación cubre `episode_id`, componentes, estados, tiempos, lineage,
razones, deduplicación, agregados y orden de registros. No se acepta comparar
solo conteos o checksum final. Una divergencia debe identificar campo, TF,
objeto, T y causa raíz.

## 6. Multiagentes y write sets

Los trabajos independientes se pueden paralelizar únicamente así:

| Dueño | Write set | Dependencia |
|---|---|---|
| D1 | contrato, SDD, índice, worklog | primero/último |
| D2 | `engine/episodes.py` y tests de dominio | después de E0 |
| D5 | `audits/codigo/episodes.py`, tests negativos y runner | junto a D2 si no comparte archivos |
| D7 | reportes, verificación y commit selectivo | después de D2/D5 |

Ningún agente crea otra versión de `Episode`, otro Funnel o una copia de
`MarketState`. La integración debe localizar la autoridad antes de fusionar.

## 7. Definition of Done

- contrato y SDD enlazados desde el índice y el arranque de Hermes;
- `engine/episodes.py` implementado sin mutaciones ni futuro;
- todos los candidatos y rechazos explicables;
- identidad y deduplicación deterministas;
- FULL/PREFIX literal PASS en la configuración declarada;
- tests focales, negativos y suite completa PASS;
- reporte con provenance, commit, configuración y checksum;
- bitácora, Graphify e índice actualizados;
- commit local selectivo, sin push automático;
- estado entregado como `COMPLETED` solo con todos los gates PASS.

## 8. Fuera de alcance

Resultado de trading, rentabilidad, optimización, entrenamiento, broker,
producción, CME/OI, descarga externa, cambio de dataset, Wyckoff-7 estadístico,
OTE y cualquier promoción.


## 9. Extensión autorizada — Temporal Episode para IA

Esta sección adapta el SDD existente al objetivo de representación temporal para
IA. No crea otro motor, otro `Episode`, otro `MarketState` ni otro funnel.

### 9.1 Autoridad temporal

El contrato `CONTRATO_EPISODES_FUNNEL_V1.md §6` sigue siendo la autoridad:

```text
available_at = candidate_time
fallback     = creation_time únicamente cuando candidate_time no existe
confirmed_at = confirmation_time
tradable_at  = tradable_time
```

No se redefine `available_at` por ObjectType.

Cuando existan las marcas:

```text
candidate_time <= confirmation_time <= tradable_time <= decision_time
```

`engine.episodes.available_time()` es la función canónica que deben consumir
los materializadores de IA.

`engine.setup_builder._obj_time()` NO define `available_at`. Es una referencia
de orden para componentes ya compuestos y se mantiene separada hasta que una
auditoría específica demuestre que su semántica deba cambiar.

### 9.2 Auditoría de productores reales

| ObjectType | Productor real localizado | Contrato temporal observado | Estado |
|---|---|---|---|
| ORDER_BLOCK | `engine/detectors/ob.py::detect_order_blocks` | candidate + confirmation + tradable | IMPLEMENTED_AND_CAUSAL |
| FVG | `engine/detectors/fvg.py::detect_fvg` | candidate + confirmation + tradable | IMPLEMENTED_AND_CAUSAL |
| BOS | `engine/historical_event_objects.py::build_historical_event_objects`; también `engine/sequence.py::_make_event_object` | histórico: candidate + confirmation + tradable; sequence legacy: creation fallback | IMPLEMENTED_AND_CAUSAL |
| DISPLACEMENT | `engine/historical_event_objects.py::build_historical_event_objects`; también `engine/sequence.py::_make_event_object` | histórico: candidate + confirmation + tradable; sequence legacy: creation fallback | IMPLEMENTED_AND_CAUSAL |
| LIQUIDITY | `engine/sequence.py::_make_event_object` | creation fallback | IMPLEMENTED_LEGACY_TIME |
| SWEEP | `engine/sequence.py::_build_expediente` / `_make_event_object` | creation fallback | IMPLEMENTED_LEGACY_TIME |
| RETURN | `engine/sequence.py::_make_event_object` | creation fallback | IMPLEMENTED_LEGACY_TIME |
| CONTRACT | `engine/sequence.py::_make_event_object` | creation fallback | IMPLEMENTED_LEGACY_TIME |
| CHOCH | se observa como señal/flag del motor, pero no se localizó productor canónico dedicado de `MarketObject(type=CHOCH)` | no certificado como objeto independiente | RESEARCH_REQUIRED |
| BREAKER | enum/ontología presentes; no se localizó productor canónico dedicado en la ruta auditada | no certificado | RESEARCH_REQUIRED |
| BPR | enum/ontología presentes; no se localizó productor canónico dedicado ni definición autoritativa en la ruta auditada | no certificado | RESEARCH_REQUIRED |

Los estados `RESEARCH_REQUIRED` no se rellenan con datos inventados. Si aparecen
en una entrada externa, el materializador conserva el objeto y su contrato
temporal existente, pero no atribuye semántica adicional.

### 9.3 Materializador autorizado

La implementación vive en:

`scripts/lab/experiments/mt_temporal_episode_materializer.py`

Responsabilidades:

1. consumir `build_episodes()` y `MarketState.projection_at(T)`;
2. incluir solo objetos conocidos en T y ancestros de lineage presentes en T;
3. ordenar `events[]` por `available_at`; en empates, el padre precede al hijo;
4. conservar candidate / confirmation / tradable por separado;
5. fallar cerrado ante futuro, temporalidad incomparable o parent fuera del snapshot;
6. registrar Wyckoff únicamente cuando un productor/contexto causal lo entregue;
7. no recalcular detectores, lifecycle, setups, labels ni outcomes.

### 9.4 Gates de la extensión

Antes de baseline temporal:

- order reversal sensible al orden;
- FULL/PREFIX literal sobre el episodio temporal;
- invariancia ante inyección de información posterior a T;
- campos Wyckoff ausentes marcados como MISSING/RESEARCH_REQUIRED, nunca inventados;
- `training_eligible=false`, `can_trade=false`, `entry_authorized=false`.

