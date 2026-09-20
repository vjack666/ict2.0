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
available_at = tradable_time -> confirmation_time -> creation_time -> candidate_time
candidate_at = candidate_time (ancla inicial; no implica disponibilidad)
confirmed_at = confirmation_time
tradable_at  = tradable_time
```

No se redefine `available_at` por ObjectType. La prioridad anterior es global y evita look-ahead en patrones cuyo candidate_time es un ancla anterior a su confirmación (FVG/OB).

Cuando existan las marcas:

```text
candidate_time <= confirmation_time <= tradable_time <= decision_time
```

`engine.episodes.available_time()` es la función canónica que deben consumir
los materializadores de IA para disponibilidad real del consumidor.

`engine.setup_builder._obj_time()` NO define `available_at`; ordena componentes ya compuestos por tiempo operativo. La auditoría 2026-09-18 lo alineó con la misma noción de uso seguro: tradable_time -> confirmation_time -> creation_time -> candidate_time.

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



## 10. Plan operativo aprobado — benchmark multi-TF EURUSD CSV (Windows CPU)

**Misión:** benchmark ICT causal D1 → H4 → H1 → M15 → M5 → M1; fecha de planificación 2026-09-19.  
**Estado de este capítulo:** PLAN_DE_IMPLEMENTACION_VERIFICADO_CON_CODIGO, ejecución aún PENDIENTE.  
**Responsable operativo:** Hermes (coordinación y ejecución con agentes funcionales).  
**Repositorio local:** C:\Users\v_jac\Desktop\ICT SYSTEM CLEAN.  
**Rama de aplicación:** hermes/temporal-windows-validation-20260918; actualizar PR #14, **NO FUSIONAR**.  
**Fuentes:** CSV extraídos bajo benchmark/eurusd_multitf/EURUSD/; manifiesto preexistente en benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json. El ZIP y los CSV son inmutables y no se versionan si superan los límites del repositorio.  
**Esta sección amplía el SDD existente:** no autoriza un Episode/Funnel/MarketState alternativo ni reemplaza sus contratos. Debe mantenerse la distinción entre una lectura de mercado, un candidato de secuencia y un Episode ACCEPTED del funnel.

### 10.1 Decisión de arquitectura y correcciones al reconocimiento

1. La autoridad de composición de episodios sigue en engine.episodes.build_episodes. Su firma comprobada es build_episodes(ms, decisions_T, ctx=None, *, config=None, contract_version=..., _candidates=None). El argumento privado _candidates es SOLO de pruebas: no usarlo para generar resultados científicos.
2. engine.historical_event_objects.build_historical_event_objects(frames, *, symbol="EURUSD", config=None) **solo exige H4 y M15**; devuelve objetos OB H4 / FVG M15 / BOS M15 / DISPLACEMENT M15. Sirve de baseline de continuidad, NO representa por sí solo seis temporalidades.
3. engine.market_state.MarketState ofrece ingest(obj), advance_bar(obj_id, bar, *, observed_tf=None), projection_at(t), state_at(obj_id, t), history_of(obj_id). Es la única autoridad de estado y transiciones. En advance_bar, omitir observed_tf para una vela del TF de autoridad; pasarlo solo para observaciones subordinadas que no mutan estado oficial.
4. engine.lifecycle.evaluate(market_object, closed_bar, *, authority_tf=None, decision_time=None, allow_expired=False, allow_consumed=False) requiere una vela cerrada con tf explícito y __index__ / index temporal válido. Nunca evaluar con un TF subordinado como autoridad. EXPIRED y CONSUMED están deshabilitados actualmente: **no simular esas transiciones ni afirmar que fueron observadas**. MITIGATED NO es terminal; una invalidación posterior aún es posible.
5. engine.multitf_context.build_multitf_context(ms, t, *, tfs=..., anchored_pd_zones=None, closed_index=None) recibe en ms un **diccionario de frames/estado por temporalidad**, NO la instancia MarketState. Delega a engine.plan.build_context_stack. Adaptar solo el input, no su semántica.
6. engine.bias.narrative.compute_htf_bias(d1, h4, h1, swing_lookback=2) devuelve HtfBias, no un dict de ctx. Registrar por separado cada dirección y la alineación; mapear ctx["htf_bias"] únicamente con las reglas documentadas del consumidor y sin forzar "bullish" cuando hay conflicto.
7. engine.Wyckoff.adapter.build_wyckoff_snapshot(frames, decision_time, *, context_state=None, ict_direction=None, authority_tf="D1", layers=("D1","H4","H1","M15")) EXISTE; su salida es WyckoffSnapshot de contexto, NO por ello un evento causal MarketObject. Serializar su to_dict() si está disponible y registrar asof/evidence. UNKNOWN/UNRESOLVED se preservan.
8. **Corrección esencial frente al inventario del explorador:** engine.sequence._make_event_object y engine.sequence._build_expediente SÍ crean MarketObject para LIQUIDITY y SWEEP; engine.sequence._run_sequence_impl crea RETURN y CONTRACT y expone señales con event_objects. La API pública verificada es run_sequence_traced(ltf_df_or_objs, est_htf_fn, cfg, ..., htf="H1"/"H4", est_htf_ctx_fn=..., exec_frames=..., audit=...) → (signals, phase_seen, expedientes, state). NO declarar esos tipos inexistentes. Lo que falta es probar que esta ruta y el productor histórico convergen sin alterar causalidad y que los eventos están accesibles en cada T, incluso antes del RETURN. Si no pueden conectarse, declarar ROUTE_NOT_INTEGRATED y conservar ambas salidas separadas. CHOCH tiene detector de estructura/columnas pero no se ha certificado un MarketObject independiente canónico; jamás crearlo sintéticamente para llenar la cadena.
9. El materializador scripts/lab/experiments/mt_temporal_episode_materializer.py mantiene la interfaz build_temporal_artifact(ms, decisions_T, ctx=None, *, context_by_decision=None, wyckoff_by_decision=None, config=None), temporalize_episode_artifact(ms, episode_artifact, *, default_context=None, context_by_decision=None, wyckoff_by_decision=None), order_reversal_report(episodes) y write_outputs(...). Mantenerlo como consumidor. No cambiar el contrato de cinco componentes del Setup para fingir que son once.
10. La política vigente en este SDD §9.1 y en engine.episodes.available_time() es **tradable_time → confirmation_time → creation_time → candidate_time**. candidate_time puede ser el ancla temprana de FVG/OB y no autoriza uso anticipado. Además comprobar temporalidad real de la vela de confirmación/cierre antes de publicar un objeto.
11. El antiguo piloto H4+M15, seis episodios y decision_time trimestral permanece identificado como CONTROL_LEGACY_NO_CERTIFICADO. Su "FULL/PREFIX por construcción" y "future injection por timestamps" NO son evidencia ejecutada. No reutilizar esos seis como training rows.

### 10.2 Árbol de trabajo previsto (rutas exactas y responsabilidades)

Reutilizar primero scripts y pruebas existentes; crear solo adaptadores o pruebas sin equivalente. No añadir otro SDD ni un segundo engine/.

| Ruta | Tipo | Responsabilidad |
|---|---|---|
| benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json | EXISTE LOCAL; verificar | Hashes por archivo, duplicados, conflictos, selección por fecha y TF. |
| docs/planificacion/SDD_EPISODES_FUNNEL_V1.md | EXISTE; ESTE PLAN | Contrato, decisiones, fases, gates y criterio de cierre. |
| scripts/lab/experiments/mt_benchmark_csv_loader.py | NUEVO adaptador aislado | Cargar CSV sin tocar fuentes; normalizar UTC, resolución temporal, calendario/close_time, selección única M5. |
| scripts/lab/experiments/mt_benchmark_multitf_builder.py | NUEVO adaptador aislado | Consumir detectores reales; coordinar MarketState con lifecycle y contexto D1→M1; mapa trazable de productores y roles. |
| scripts/lab/experiments/mt_benchmark_runner.py | NUEVO runner fino | Dos controles, descubrimiento event-driven, snapshots y llamadas al materializador original. |
| scripts/lab/experiments/mt_benchmark_causal_audit.py | NUEVO auditor fino | Ejecutar FULL/PREFIX y future injection con reconstrucción INDEPENDIENTE; diff por campo e identidad canónica. |
| scripts/lab/experiments/mt_benchmark_compare.py | NUEVO comparador fino | Comparación imparcial con control GPT; no hardcodear reglas/valores esperados en el motor. |
| tests/test_mt_benchmark_csv_loader.py | NUEVO | UTC/vela cerrada, M5 conflictivo, duplicados, fuentes, no look-ahead, 1971/1972 fuera del universo EURUSD literal. |
| tests/test_mt_benchmark_multitf_builder.py | NUEVO | Roles/lineage, acceso por T, replay a T, activo vs mitigado, desajustes de TF. |
| tests/test_mt_benchmark_causal_audit.py | NUEVO | FULL/PREFIX real, mutación futura real, control negativo de fuga, hashes estables sin UUID arbitrarios. |
| tests/test_mt_benchmark_runner.py | NUEVO | Dos controles, eventos event-driven, outputs sin órdenes ni entrenamiento; ausencia M1 en CONTROL A. |
| reports/audits/experiments/temporal/GPT_VS_HERMES_MULTITF_COMPARISON.md | OUTPUT | FIELD / GPT_CONTROL / HERMES / MATCH / DIFFERENCE / ROOT_CAUSE. |
| reports/audits/experiments/temporal/BENCHMARK_REAL_EXECUTION.json | OUTPUT | Config y decisiones congeladas, conteos y gates con referencias a artefactos por ejecución. |
| reports/audits/experiments/temporal/BENCHMARK_FULL_PREFIX.json | OUTPUT | Comparaciones de construcción independiente; 0 divergencias exigidas. |
| reports/audits/experiments/temporal/BENCHMARK_FUTURE_INJECTION.json | OUTPUT | Mutaciones >T, comparación reconstruida; 0 divergencias exigidas. |
| reports/audits/experiments/temporal/BENCHMARK_LIFECYCLE.json | OUTPUT | Historial de transiciones, edad, decisiones de vigencia, rechazos y ejemplos. |
| reports/audits/experiments/temporal/BENCHMARK_PROVENANCE.json | OUTPUT | Fuente/hashes, reglas de selección, rango, config, Python/OS/CPU, git SHA y hashes de outputs. |

Los CSV voluminosos, los ZIP, caches, entornos virtuales y artefactos grandes quedan **sin commit**. Antes de guardar archivos nuevos verificar si hay un script de benchmark adaptable; si existe, reutilizarlo y reflejar las rutas reales en esta tabla. Los scripts son adaptadores, nunca calculadores paralelos de BOS/FVG/ICT/Wyckoff.

### 10.3 Contratos de funciones a IMPLEMENTAR en los adaptadores (NO afirmar que ya existen)

Firmas de diseño, no APIs actuales del motor:

    load_selected_frames(
        manifest_path: Path, *, window_start: datetime, window_end: datetime,
        selected_tfs: tuple[str, ...], decision_time: datetime | None = None,
        source_profile: str = "RECENT", mutate_future: Callable | None = None
    ) -> tuple[dict[str, pd.DataFrame], dict]

    build_market_state_multitf(
        frames: Mapping[str, pd.DataFrame], *, symbol: str = "EURUSD",
        until_T: datetime | None = None, config: Mapping | None = None,
        sequence_mode: str = "DIAGNOSTIC"
    ) -> tuple[MarketState, dict]

    build_control_snapshot(
        frames: Mapping[str, pd.DataFrame], T: datetime, *,
        config: Mapping | None = None
    ) -> dict

    find_event_driven_decisions(
        frames: Mapping[str, pd.DataFrame], state: MarketState, *,
        start_T: datetime, end_T: datetime, max_episodes: int = 50
    ) -> tuple[list[datetime], dict]

    replay_authority_lifecycle(
        state: MarketState, frames: Mapping[str, pd.DataFrame], *,
        until_T: datetime
    ) -> dict

    run_full_prefix(
        manifest_path: Path, decision_times: Sequence[datetime], *,
        config: Mapping
    ) -> dict

    run_future_injection(
        manifest_path: Path, decision_times: Sequence[datetime], *,
        config: Mapping, seed: int = 20260919
    ) -> dict

    compare_gpt_controls(
        controls: Mapping, *, control_reference: Mapping,
        run_provenance: Mapping
    ) -> dict

Las firmas nuevas pueden adaptar nombres al código ya existente, pero NO sustituir las firmas verificadas del motor (§10.1). El loader recibe un manifiesto fijado en vez de un glob que pueda incluir archivos rechazados. La capa de construcción entrega POR SEPARADO MarketState, contexto, evidencia de secuencia y eventos aún no integrados; no fuerza un productor a simular otro.

### 10.4 FASE P0 — sello de fuentes, semántica temporal y preflight CPU (G0)

1. Conservar el ZIP único ya extraído y su SHA256; releer BENCHMARK_DATA_MANIFEST.json y confrontar SHA256/bytes de los CSV seleccionados con disco. Revisar que el manifiesto es un inventario, no prueba de equivalencia económica. Los reportes pequeños pueden entrar a Git; los CSV se quedan locales/read-only.
2. La elección del CSV es **por perfil temporal**, no por "mayor número de años": D1 EURUSD_D1.csv, H4 EURUSD_H4.csv, H1 EURUSD_H1.csv (H1_20y duplicado), M15 EURUSD_M15.csv, M5 EURUSD_M5_3m.csv para CONTROL A/B y ventana reciente, M1 EURUSD_M1.csv solo hasta su última vela real. EURUSD_M5_20y.csv se conserva para un estudio histórico DIFERENTE; no aporta a CONTROL A/B, termina en 2025 y tiene rellenos/solapes conflictivos. EURUSD_M5.csv NO se intercala con M5_3m ni M5_20y; registrar diferencias por timestamp y origen. Prohibido concatenar fuentes incompatibles, incluso cuando haya aparente continuidad de fechas.
3. D1 desde 1971 y H4 desde 1972 no prueban EURUSD transable literal. Restringir controles y piloto al período declarado en 2026, con warmup causal suficiente para indicadores y contexto; no usar ni certificar datos anteriores a la existencia real del instrumento. Registrar cobertura efectiva por TF, origen, huso horario, fines de semana, zero-range, huecos, OHLC inválido, conflictos. No borrar barras sin un filtro explícito y auditado que sea causal.
4. **STOP obligatorio antes de código de detección:** establecer con evidencia del proveedor y agregación OHLC si cada campo time es APERTURA o CIERRE. Normalizar internamente bar_open_time, bar_close_time y source_time sin modificar CSV original. Si la fuente guarda apertura, bar_close_time = apertura + duración de TF, con calendario efectivo (D1/H4 y DST requieren comprobación, no sumar ingenuamente 24h a sesiones especiales). Si guarda cierre, usar el cierre documentado. Verificar que el último bar aceptado cumple bar_close_time <= T en CADA TF. No desplazar time a ojo para hacer coincidir controles GPT.
5. CONTROL A = 2026-09-17T18:20:00Z: D1/H4/H1/M15/M5; M1 = OUT_OF_RANGE, NO MISSING_DATA. CONTROL B = 2026-08-24T20:35:00Z: seis TF solo si hay vela M1 cerrada <=T y el historial termina en ese instante. Si no, M1 = OUT_OF_RANGE y explicarlo. La lectura GPT es **referencia independiente**, no verdad normativa.
6. Gate Windows CPU inicial: ejecutar scripts/run_temporal_episode_windows_cpu.ps1 con Python 3.11 desde .venv_temporal, sin TensorFlow/Torch/CUDA. Registrar código de salida y salida real (no citar un reporte viejo como si fuera esta ejecución).
7. Entregables P0: manifiesto congelado, selección efectiva por control y hashes de archivos, política de close_time, tiempo último cerrado por TF, test loader, preflight Windows CPU. Si falla la semántica de tiempo, estado BLOCKED_TIME_SEMANTICS; no producir un falso "closed-only".

### 10.5 FASE P1 — constructor multi-TF y dos lecturas de control (G1)

**Decisión:** NO generalizar a ciegas build_historical_event_objects ni clonar su lógica H4/M15. Usarlo sin cambios como baseline de compatibilidad. Construir un **adaptador** en scripts/lab/experiments/mt_benchmark_multitf_builder.py que invoca productores EXISTENTES del motor y emite evidencia separada por TF. Solo pasar al MarketState objetos con timestamps, identidad, autoridad, parent_id y condiciones causales verificadas. Las salidas tabulares siguen tabulares hasta existir una conversión normativa y testeada.

A. Por cada T, cargar frames closed-only y conservar la serie histórica con lookback causal explícito. Llamar compute_htf_bias(frames["D1"],frames["H4"],frames["H1"]); crear el diccionario requerido por build_multitf_context(frames_annotated, T, ...), usando frames enriquecidos por el productor original que exija cada capa. No pasar MarketState al argumento ms de build_multitf_context. Conservar direcciones D1/H4/H1/M15/M5/M1 como observaciones diferenciadas; la alineación HtfBias no sustituye la dirección propia por TF.
B. Para POI, usar detect_order_blocks(rows, timeframe=tf, symbol="EURUSD", min_body_ratio=0.60) en D1/H4/H1; SOLO roles POI en esos TF, y respetar contrato de MarketObject.__post_init__. Para FVG, usar detect_fvg(rows, timeframe=tf, symbol="EURUSD") en M15/M5/M1; no presentar automáticamente cada FVG como REFINEMENT de un POI: elegir parent con evidencia de relación causal ya disponible en engine/relations.py/historical_event_objects.py o marcar UNLINKED_NO_LINEAGE. BOS/CHOCH usar detect_market_structure(frame, config=None). Esta API devuelve MarketStructure con .frame: las marcas BOS/CHOCH son columnas/observaciones; convertirlas a MarketObject solo tras hallar autoridad normativa compatible y testear su confirmación, o dejar CHOCH_TYPE=NOT_INTEGRATED. Displacement: detect_displacement(frame, cfg=None) produce DataFrame, no MarketObject; para eventos registrados en MarketState reutilizar la conversión histórica auditada, nunca inventar precio o parent.
C. **Ruta de cadena completa existente:** investigar y usar engine.sequence.run_sequence_traced(...), con SequenceConfig real, est_htf_fn/est_htf_ctx_fn closed-only y productores de POI respaldados. Su señal guarda event_objects para LIQUIDITY/SWEEP/DISPLACEMENT/BOS/REFINEMENT/RETURN/CONTRACT. Extraer esos objetos preservando el parent_object original; el mismo módulo usa uuid aleatorio en _make_event_object, así que registrar un identity_map canónico (tipo, TF, cierre, dirección, parent normalizado, ordinal) para comparar reconstrucciones sin confundir un UUID nuevo con diferencia causal. NO sustituir el id del motor en producción. Validar también las secuencias PENDING sin retorno: la ruta signals puede emitir solo al RETURN. Usar el audit/state incremental si permite observar el evento antes del RETURN sin mirar futuro; si no, marcar PENDING_SEQUENCE_NOT_EXPORTED, no reconstruir retrospectivamente.
D. **Dos carriles sin mezcla indebida:** (i) EPISODE_FUNNEL_CANONICAL, basado en cinco roles admitidos por engine.setup_builder y build_episodes; (ii) SEQUENCE_TRACE_CANONICAL, producido por engine.sequence y sus event_objects. Solo enlazar carriles por IDs de objeto/parent/tiempo/geometry comprobados, sin asumir que una coincidencia en una misma vela prueba parentesco. Un resultado de secuencia que NO atraviese build_episodes se etiqueta SEQUENCE_CANDIDATE o COMPLETE_SEQUENCE, nunca Episode ACCEPTED del funnel. Si no hay puente probado, reportar BRIDGE_NOT_INTEGRATED y conservar los resultados por separado.
E. Persistir CONTROL_A.json y CONTROL_B.json con T, último cierre por TF, dirección y regla, estructura/sweeps/displacement/CHOCH, zonas activas, estado de POI, retest, contexto Wyckoff y brechas. Las zonas 1.14790–1.14850 H1, 1.14867–1.14875 M15, 1.14903–1.14911 M5 y 1.14667–1.14682 H4 son **referencias GPT aproximadas** y pueden diferir por detector/time semantics; no hardcodearlas ni corregir el motor solo para igualarlas.
F. Wyckoff: invocar build_wyckoff_snapshot(frames, T, context_state=..., ict_direction=..., authority_tf="D1", layers=("D1","H4","H1","M15")); guardar phase/phase_state/events/effort_result/range_ref/volume_mode/ict_alignment y evidence_refs con asof<=T. Si falta información o la fase es UNKNOWN, conservarlo. No anunciar que un Spring/UTAD existe sin evento y sellos causales del motor.
G. Entregables P1: dos snapshots reales, productor y regla por cada observación, trazas de secuencia y listado OBJECT_TYPE→CREATOR→INTEGRATED/NOT_INTEGRATED con justificación. CONTROL A ≠ un setup ejecutable: si no hubo RETURN, estado PENDING.

### 10.6 FASE P2 — lifecycle, staleness y descubrimiento event-driven (G2)

1. Ingestar cada objeto cuando llega su sello realmente utilizable, no retro-publicar un FVG en la primera vela ancla. Ordenar una única cola global por bar_close_time y, dentro de cada TF, por índice; procesar **la misma vela de autoridad una sola vez por reloj de TF** y evaluar TODOS los objetos elegibles en ese cierre antes de avanzar el siguiente bar. MarketState._last_seen es reloj por TF, compartido por objetos: no recorrer todas las velas de un objeto y luego retroceder al segundo objeto; eso dispara OUT_OF_ORDER o corrompe auditoría. Si se necesita inspección aislada, usar replay por objeto en una copia independiente sin presentarlo como historial oficial compartido.
2. Para cada vela de authority_tf, construir {"time": close_time, "__index__": índice absoluto, "tf": authority_tf, "open":..., "high":..., "low":..., "close":...} y llamar MarketState.advance_bar(obj_id, bar) solo después de su instante de tradabilidad. Observaciones LTF con observed_tf no pueden decidir el estado H4. No reutilizar la vela que CREA un FVG/OB como auto-mitigación: borde temporal estricto posterior a su confirmación/tradable, siguiendo el contrato de engine.lifecycle._bar_after_tradable y las pruebas B1.
3. Los estados reales son CREATED/ACTIVE/PARTIALLY_MITIGATED/MITIGATED/INVALIDATED; EXPIRED/CONSUMED son enums pero no están emitidos en lifecycle v1. No convertir MITIGATED automáticamente en terminal, no declarar un objeto ACTIVE por defecto si faltó replay. Si la geometría o la autoridad no son evaluables, estado LIFECYCLE_UNVERIFIED y veto de aceptación.
4. Registrar historia causal MarketState.history_of(id) con timestamp y razón de cambio (si procede), first_touch_time, invalidated_time, barras recorridas y edad. Exigir coherencia con la serie de precio real entre creación y T. Para cada candidato registrar first_event_time / last_event_time / decision_time y sus diferencias en segundos. No usar TTL inventado: la elegibilidad del evento viejo depende de historial de lifecycle + invalidación/mitigación/pertinencia y del instante T. Investigar expresamente seis episodios legacy evaluados el 17-ago-2024 con hechos de 2022/2023; usar el sistema de transición como causa raíz, no reetiquetarlos.
5. Generar decision_times desde el evento necesario que el motor publicó causalmente (RETURN/CONTRACT para COMPLETE_SEQUENCE; último componente requerido para FUNNEL_CANDIDATE) dentro de 2026-06-18→2026-09-17, sin fechas trimestrales. El timestamp debe provenir del output real del productor, no del calendario de muestreo. No convertir un candidato PENDING sin RETURN en completo.
6. La cadena objetivo HTF_CONTEXT→LIQUIDITY→SWEEP→DISPLACEMENT→BOS/CHOCH→FVG/OB→RETURN→SETUP→CONTRACT es un **contrato de integridad**, NO autorización para exigir un orden fijo que el productor no garantiza para BOS/FVG/OB en todos los escenarios: verificar el orden causal y la tesis vigente por estrategia; las variantes deben estar predefinidas, no elegidas después de observar resultados. Si el productor/puente no da soporte a una etapa, reportar etapa NOT_INTEGRATED o PENDING, con primer punto de ruptura y datos no fabricados.
7. Objetivo hasta 50 episodios genuinos; generar también conteo exhaustivo de candidatos/rechazos de la ventana. No crear 50 seleccionando solo los más favorables; elegir orden determinista predefinido (por decision_time, ID canónico). Si 0 cumplen, dejar REAL_EPISODES=0 y la causa exacta; no relajar reglas.
8. Entregables P2: BENCHMARK_LIFECYCLE.json, decisiones event-driven, histogramas de edad por TF/estado, secuencias completas y pendientes, rechazo por razón, asof_T y trazabilidad hasta fuente. Mantener training_eligible=false.

### 10.7 FASE P3 — gates adversariales ejecutados, no "PASS por construcción" (G3)

**FULL/PREFIX verdadero:**
- Para cada T de los dos controles y cada T de una muestra reproducible de episodios (o todos si son <=50), ejecutar FULL: cargar todas las fuentes congeladas y reconstruir desde cero **detectores, contexto, MarketState con lifecycle, secuencias y episodios**, proyectar en T. Ejecutar PREFIX desde COPIAS en memoria de TODAS las fuentes truncadas por bar_close_time<=T; reconstruir el pipeline íntegro desde cero; comparar semánticamente los outputs EN T, incluyendo universo de candidatos, rechazos, estado, times, geometry, eventos, lineage, contexto y Wyckoff.
- **Prevenir atajo:** prohibido llamar dos veces a projection_at(T) sobre el mismo MarketState y llamarlo FULL/PREFIX. Si el modo FULL no reconstruye causalmente hasta T o el detector retroedita salidas con velas futuras, reportar divergencia y causa.
- Canonicalizar únicamente campos no científicos variables (wall-clock de generación, runtime y UUID aleatorio con identity_map estable). Nunca descartar event_time, candidate/confirmed/tradable, estado, parent lógico, precio, zona o ID semántico; los IDs deterministas deben compararse literalmente. Guardar hashes de payloads normalizados, diff campo-a-campo y command/config/source hashes por ejecución. Repetir al menos dos veces en un T fijo para detectar aleatoriedad.
- Si REAL_EPISODES=0, los controles y candidatos/rechazos siguen debiendo superar el gate; no marcar PASS vacío.

**FUTURE INJECTION verdadero:**
- Seleccionar >=10 T con datos futuros disponibles en las fuentes relevantes; incluir CONTROL B y puntos del piloto, más controles anteriores al final del rango. CONTROL A no tiene suficiente futuro en el ZIP si se encuentra al borde final: marcar INELIGIBLE_FOR_FUTURE_INJECTION, no fingir prueba.
- Rama A: pipeline completo desde fuentes originales. Rama B: COPIAS de todos los frames con exactamente las mismas filas/valores y hashes del prefijo <=T; modificar únicamente OHLC/tick_volume/spread de barras con bar_close_time>T y agregar, cuando sea causalmente válido, barras posteriores a T. Recalcular todo desde cero, sin reutilizar caches/detectores/MarketState de A.
- Probar al menos un control negativo inyectando deliberadamente UNA alteración <=T en una copia aparte: el comparador DEBE detectar diferencia; si no, el gate no observa lo que dice observar. NUNCA incorporar el control negativo al resultado científico.
- Comparar en T universo de candidatos, rechazos, estado, secuencia, contexto y Wyckoff. Exigir divergent=0 para todos los T elegibles y almacenar qué archivos/barras mutaron, qué prefijos quedaron bit-identical, seeds y diffs. Si no hay >=10 T elegibles, FUTURE_INJECTION=INSUFFICIENT_TEST_POINTS y READY_FOR_TEMPORAL_BASELINE=NO.

**ORDER REVERSAL:**
- Ejecutar el order_reversal_report existente sobre los episodios de longitud >=2; identical=0. Distinguir "el fingerprint cambia si invierto una lista" de "las FEATURES TENSORIALES consumidas por GRU cambian": en esta misión solo se certifica el primer punto. No declarar tensor/GRU certificado. Si no hay episodios, NOT_TESTED.

**RESULTADOS:** los tres gates se certifican por ejecución real con test_id, hash del runner, universo T, count, identical/divergent, fallo y referencia de output. Conservar rejections, no reportar solo episodios ACCEPTED.

### 10.8 FASE P4 — comparación GPT ↔ motor, reproducibilidad y cierre (G4)

1. Crear GPT_VS_HERMES_MULTITF_COMPARISON.md con columnas FIELD | GPT_CONTROL | HERMES | MATCH | DIFFERENCE | ROOT_CAUSE y secciones CONTROL A, CONTROL B, secuencia M15 y conjunto de episodios. Referencia textual disponible: A 2026-09-17 18:20Z, D1/H4 bajistas, H1 alcista, M15/M5 bajistas; B 2026-08-24 20:35Z, D1 alcista y otros cinco bajistas. Los niveles GPT se citan como aproximados, no requisitos duros; el detector del motor puede dar otros resultados legítimos.
2. Si el JSON/MD original del control GPT no está físicamente accesible para Hermes, compararlo solo contra el resumen textual proporcionado por el usuario y registrar GPT_REFERENCE_FORMAT=TEXT_SUMMARY; NO fingir lectura, hashes ni igualdad evento-a-evento contra archivos ausentes.
3. Clasificar cada desacuerdo: DATA_SOURCE_DIFFERENCE, TIME_ALIGNMENT, DETECTOR_RULE_DIFFERENCE, LIFECYCLE_DIFFERENCE, NOT_INTEGRATED, CONTROL_GPT_APPROXIMATION o VERIFIED_BUG. No modificar el motor para alcanzar el valor GPT.
4. Repetir el mismo runner dos veces en Windows CPU con mismo ZIP SHA256, commit/config y política de timestamps; exigir hashes iguales de outputs CIENTÍFICOS, exceptuando created_at/wall-clock y UUID normalizados de forma explícita. Los manifiestos con hora de ejecución pueden tener hashes distintos y no deben contarse como divergencia.
5. Ejecutar scripts/run_temporal_episode_windows_cpu.ps1 antes y después, y las nuevas pruebas de benchmark con .venv_temporal/Scripts/python.exe. Registrar stdout/stderr, exit code, versión Python/Windows/paquetes y CUDA_VISIBLE_DEVICES=-1. No instalar TensorFlow/Torch/CUDA, no enviar órdenes MT5.
6. Auditoría independiente de @vigil: revisar sellos temporales, fuentes elegidas, control negativo, flujo de lineage, snapshots FULL/PREFIX y futuro, ausencia de features de resultado futuro, ocho errores de selección/duplicados y etiquetas correctas NOT_INTEGRATED/OUT_OF_RANGE. @orion emite dictamen solo después. Actualizar worklog existente/índice/Engram local/Graphify cuando estén disponibles; si una integración opcional falla, documentarlo sin bloquear la validez científica y sin abrir línea Slack/UI.
7. Commit selectivo en hermes/temporal-windows-validation-20260918 y push para actualizar PR #14; NO MERGE. No subir los grandes CSV, ZIP, venv, caches ni credenciales. Antes de push cotejar HEAD con origin para no sobrescribir cambios de otros agentes.
8. Salida final: ambos controles, dataset+SHA, TFs realmente presentes, cadenas completas y pendientes, estados/edades, gates con tested/identical/divergent/NOT_TESTED y artefactos, comparación por causas, flags. Siempre training_eligible=false, can_trade=false, entry_authorized=false, READY_FOR_GRU=NO, READY_FOR_DEMO=NO.

### 10.9 Matriz de decisiones de diseño / riesgos (obligatoria en revisión)

| Riesgo / alternativa | Decisión exigida / tradeoff |
|---|---|
| Extender productor H4/M15 vs builder nuevo | Mantener productor histórico sin alterar. Adaptador de composición multi-TF llama detectores existentes y conserva salidas tabulares no certificadas; evita romper baseline, requiere test de integración de roles/lineage. |
| Secuencia vs funnel | Dos carriles identificados; enlace solo con evidencia causal. Reutiliza productores reales de LIQUIDITY/SWEEP/RETURN del engine.sequence sin declararlos inventados. Si no hay bridge, NO llamar Episode ACCEPTED a una secuencia. |
| M5 histórico vs reciente | M5_3m único para controles/piloto recientes. M5_20y aislado histórico; M5.csv rechazado por conflicto para este perfil. No stitching, no timestamp duplicado. |
| Time de apertura vs cierre | Decidir por evidencia de fuente/agregación; si no se puede, bloquear lectura closed-only. D1/H4 dependen de sesiones y DST. |
| Recalcular sobre millones de filas | Ingesta por chunks con índices de cierre; precomputar frames fuente SOLO para lectura, nunca reusar detector calculado con futuro en PREFIX/FUTURE INJECTION. Empezar controles con ventana causal acotada y verificar equivalencia frente a prefijo mayor antes de escalar. |
| Replay por objeto vs global | Ordenar globalmente por reloj de TF; jamás llevar reloj global H4 al futuro y después procesar otro OB H4 del pasado. Cuando sea imposible escalar, hacer replay independiente y marcarlo DIAGNOSTIC_ONLY. |
| MarketObject con UUID aleatorio | Identidad normalizada exclusivamente para comparación de salidas, sin cambiar ids persistidos ni esconder diferencias de parent/time/state. |
| POI viejo pero ACTIVE | ACTIVE no es prueba de vigencia. Registrar lifecycle completo, touches, mitigación, invalidación y pertinencia en T. No añadir TTL inventado. |
| CHOCH / BPR / BREAKER | CHOCH observable en frame no implica MarketObject; otros sin productor certificado son NOT_INTEGRATED/RESEARCH_REQUIRED. |
| M1 finaliza antes de CONTROL A | OUT_OF_RANGE en A; en B verificar cierre M1 <=T. Ausencia por no integrar productor = NOT_INTEGRATED, no MISSING_DATA. |
| Wyckoff incompleto | Usar adapter existente; UNKNOWN/MISSING no se transforman en spring/UTAD inventado. |
| El control GPT no es motor canónico | Comparación informativa, documentar diferencias explicables y no cambiar tesis por match artificial. |

### 10.10 Orden exacto de ejecución y gates de salida

**P0 → P1 → P2 → P3 → P4**. No saltar fases por presión de conteos.

- P0 DATA/CPU: input ZIP+manifest/hash, selección de TF, política de cierre, preflight Python 3.11. Si falla: DATA_RECONCILIATION_FAIL / BLOCKED_TIME_SEMANTICS.
- P1 CONTROL A/B: lectura multitemporal causal, lista de productores y la cadena real vs no integrada. Si no hay bridge, reportar estados independientes y seguir con diagnóstico, sin promover episodios.
- P2 LIFECYCLE/EPISODES: replay y edad demostrables; decision_time = tiempo del evento final del tipo de artefacto; hasta 50 genuinos, reportar 0 si 0. Nunca usar fecha trimestral.
- P3 CAUSAL AUDIT: FULL/PREFIX construido desde cero + future injection real >=10 T elegibles + control negativo + order reversal. Los fallos vuelven al módulo causal concreto y repiten P1/P2/P3 afectados; sin editar reglas para fabricar PASS.
- P4 QA/COMPARISON: repetición determinista, Windows CPU final, reporte GPT, auditoría independiente, worklog/Engram, commit/push PR #14; no fusionar.

**Presupuesto de ejecución:** no estimar minutos arbitrarios para 5.78M M1 y 1.7M M5 ni prometer tiempo futuro; registrar filas/s, RAM máxima, tiempo real por fase y límites configurables de ventana/chunks. Un smoke test de CONTROL B en CPU establecerá los costes observados. Si el replay completo supera recursos, reducir SOLO tamaño de lote/ventana de auditoría con justificación y mantener universo de control y los gates científicos; no relajar el requisito de reconstrucción independiente.

**Dictamen autorizado:** READY_FOR_TEMPORAL_BASELINE=YES solo con contrato temporal, datos, control A/B, lifecycle/staleness, episodio causal completo y vinculado al funnel (o especificación aprobada explícita de candidatos incompletos), FULL/PREFIX real con 0 divergencias, FUTURE_INJECTION real con 0 divergencias y >=10 T elegibles, order reversal con 0 idénticos, provenance y Windows CPU PASS. Si cualquier etapa sigue NOT_INTEGRATED, NO afirmar episodio ICT completo; reportar el primer bloqueo y fijar READY_FOR_TEMPORAL_BASELINE=NO. Ningún gate habilita training/trading.

### 10.11 Continuidad de la lista de Hermes (sin crear una misión paralela)

La situación actual indicada por Hermes es:
- [✓] Reconocimiento de repo/PR/piloto.
- [✓] Exploración de firmas y productores; COMPLEMENTADA aquí con la ruta real engine.sequence y la distinción MarketState vs frames.
- [✓] Inventario/manifest CSV local; **REVALIDAR** fuentes M5 seleccionadas, semántica del timestamp y hashes.
- [✓] Plan arquitectónico disponible en ESTE capítulo, listo para el constructor; no quedarse esperando a un subagente sin saldo.
- [ ] Aplicar P0: verificar datos/time semantics/Windows CPU.
- [ ] Aplicar P1: loader, builder, CONTROL A/B, trazas y Wyckoff.
- [ ] Aplicar P2: lifecycle, staleness, episodios event-driven.
- [ ] Aplicar P3: FULL/PREFIX real, future injection real, order reversal y tests adversariales.
- [ ] Aplicar P4: comparación GPT, audit independiente, gate CPU final, reportes.
- [ ] Cierre: worklog, índice, Engram local, commits selectivos, push PR #14, reporte exacto de la misión.

Si @architect/scout no responde por modelo/saldo: reasignar inmediatamente al agente funcional con modelo predeterminado disponible, o ejecutar inline el plan verificado. Registrar fallback en worklog y continuar. No pedir al usuario que recupere saldo. **Hermes no debe editar el motor por intuición ni afirmar PASS antes de las pruebas reales.**
