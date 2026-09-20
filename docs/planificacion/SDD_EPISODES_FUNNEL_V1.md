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


## Enmienda operacional 2026-09-20 — Inventario → MarketState, sin saltarse el funnel

En `C:\\Users\\v_jac\\Desktop\\ICT SYSTEM` (ORIGINAL), el inventario de detectores (`scripts/audit/ict_event_inventory.py`) ahora emite `nivel`, `zone_high`, `source_close` y `confirmation_time_utc`. El puente `engine/detector_event_bridge.py` lo convierte en un conjunto **diagnóstico** de MarketObjects con identidad estable, deduplicación y nacimiento observable en la confirmación; `scripts/audit/ict_event_market_state.py` entrega un resumen por control. La salida A=154/B=582 representa **ocurrencias aisladas**, no setups o episodios. Para OB no se puede usar como nacimiento visible la vela de footprint previa a follow-through; para MSS se mantiene su tipo distinto de CHOCH. Los objetos del puente NO constituyen una fuente de lineage/lifecycle/eligibilidad por sí solos.

Gates de esta fase: test unitario y datos reales del inventario completados en entorno de auditoría; P1 FULL_FUNNEL=NOT_RUN, FULL_PREFIX_DETECTORS=NOT_RUN, lifecycle completo=NOT_RUN, revisión independiente=NOT_RUN. El hecho de que `MarketState` tenga objetos ACTIVE inicialmente NO constituye certificación de estado actual: falta replay por TF. La integración futura debe reutilizar `engine/historical_event_objects.py` y `engine/episodes.py`, con causalidad y lineage acreditados. **No promover ni entrenar por estos conteos**.

Ver `.hermes-worklog/2026-09-20_DETECTOR_MARKETSTATE_BRIDGE_ORIGINAL.md` para los comandos exactos, métricas reproducibles y el protocolo de integración selectiva al ORIGINAL.


## Enmienda 2026-09-20 — Simulación causal cerrada H4/M15 previa al funnel

**Misión y alcance acotado:** implementar una infraestructura verificable de replay que consuma los `MarketObject` del productor **ya existente** `engine.historical_event_objects.build_historical_event_objects` (H4/M15). No redefinir detectores, no inventar asociaciones LIQUIDITY→SWEEP ni transformar 154/582 ocurrencias del inventario en secuencias aceptadas. El conector del inventario `engine/detector_event_bridge.py` es diagnóstico y NO es automáticamente el productor canónico de episodios.

**Código incorporado:** `engine/causal_replay.py` fusiona los streams de velas previamente normalizadas a **hora de cierre UTC**, con heap cronológico O(temporalidades). Valida orden estricto por TF, timestamps aware, OHLC mínimo, unicidad de objetos, autoridad TF=origen, confirmación anterior o igual a tradable y padre explícito observable **antes** del hijo; rechaza punteros `related_objects` precompletados que pueden filtrar hijos futuros. Clona los objetos de entrada y retrasa la hora observable de nacimiento hasta `tradable_time` (un OB no nace visiblemente en la vela fuente). Al cerrar la vela de autoridad evalúa únicamente FVG/OB/BREAKER/BPR ya nacidos en un cierre estrictamente anterior, mediante `MarketState.advance_bar` y el lifecycle existente; no auto-mitiga un objeto con su vela confirmatoria, ni permite que M15 cambie el estado oficial de un objeto H4. El planificador no deduce relaciones por proximidad, ni recalcula el productor ni decide señales.

**CLI de piloto:** `scripts/audit/run_causal_replay.py --source ...EURUSD.zip --control A|B --output ...` usa `read_source` y `verify_sha256_manifest` ya existentes, elige H4/M15 y convierte las marcas `CSV time=OPEN` a cierre antes del replay. Guarda resumen JSON con SHA256 y hasta 20 MarketObjects trazables, señalando `SIX_TF_CONTEXT/SEQUENCE/FUNNEL/EPISODES=NOT_RUN`. La duración fija para H4/D1 está sujeta a comprobación del calendario broker/DST. Ningún campo `state` de objetos producidos equivale a rentabilidad.

**Pruebas de desarrollo del planificador:** `PYTHONPATH=. python -m pytest -q tests/test_causal_replay.py` → **6 PASS** en entorno aislado de desarrollo; se verificó que el contenido publicado de módulo, test y CLI coincide exactamente con sus Git blob SHA locales. Estas seis pruebas usan un `FakeMS` para aislar el ordenamiento, el tiempo observable, autoridad, deduplicación y rechazo fail-closed. **No constituyen prueba de integración con el MarketState real ni ejecución del piloto EURUSD en Windows**. Estos gates están **PENDIENTES** de Hermes en ORIGINAL y de revisión externa: `tests/test_market_state.py`, `tests/test_historical_event_objects.py`, replay A y B con datos reales, comparación FULL/PREFIX del productor y motor, future injection, seis TF, secuencias, funnel, episodios y revisión Vigil. Si falta cobertura, falla un test o aparece MemoryError, registrar el primer bloqueo, no producir PASS.

**Siguiente intervención (Hermes):** reproducir piloto H4/M15 con el código publicado, ejecutar suite de integración y registrar hashes, tiempos, estados, relaciones y rechazos. Sólo entonces planear acoplamiento al motor `run_sequence_traced` y `build_episodes` usando su contrato verdadero; no reemplazar `engine/sequence.py` por este scheduler ni crear setups sintéticos. Se reutiliza este SDD y la bitácora; no hay autorización de merge de esta rama ni de operación MT5.
