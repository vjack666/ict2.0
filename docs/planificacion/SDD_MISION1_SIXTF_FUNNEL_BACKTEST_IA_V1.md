# SDD — Mision 1: puente seis-TF hacia Funnel, Backtest e IA v1

**Fecha:** 2026-09-21  
**Estado:** `MISSION1_F2_F5_COMPLETED_SHADOW_DIAGNOSTIC`
**Modo:** `LOCAL_ONLY`  
**Autoridad previa:** PR #16 `MERGED` en `origin/hermes/evidencia-ict-replay-pass-20260920` (`d4fdf68def1915ce29f0e3abe31e33f19eeb92ea`)  
**No autoriza:** trading, MT5 live, ordenes, promocion, cambio de dataset, fabricacion de M1 ni entrenamiento productivo.

## 1. Respuesta ejecutiva

Si hay base reutilizable para la Mision 1:

1. `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md`
2. `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`
3. `docs/contratos/CONTRATO_LINEAGE_HIERARCHY_V1.md`
4. PR #16: `full six-TF lineage gate`
5. HTML de trazado: `reports/audits/experiments/temporal/PR16_SIXTF_LINEAGE_TRACE_20260921.html`

Lo que no existia era un SDD puente post-PR16 que convirtiera esa base en una
fase ordenada hacia backtest funnel e IA. Este documento cubre ese hueco y
cierra al 100% la fase documental/preflight de Mision 1.

## 2. Objetivo de Mision 1

Instalar la ruta conceptual y verificable que une:

```text
linaje seis-TF causal
  -> objetos/eventos con disponibilidad causal
  -> episodios/funnel aceptados y rechazados
  -> backtest economico aislado
  -> dataset causal para IA
  -> entrenamiento/evaluacion shadow
```

Mision 1 no busca demostrar edge ni entrenar un modelo en esta fase. Busca que
el proyecto tenga contrato, gates, artefactos, responsabilidades y no-go claros
para que la siguiente implementacion no vuelva a usar H4/M15 como atajo.

## 3. Alcance exacto de esta fase

### Incluido

- Inventariar si existen SDD/planes reutilizables.
- Declarar la autoridad vigente despues de PR #16.
- Definir el puente entre seis temporalidades y `engine/episodes.py`.
- Definir gates obligatorios antes de backtest.
- Definir gates obligatorios antes de entrenamiento IA.
- Documentar riesgos y bloqueos actuales.
- Enlazar la fase desde el indice maestro y bitacora.

### Excluido

- Ejecutar backtest economico.
- Entrenar GRU, TensorFlow u otro modelo.
- Conectar MT5 o emitir ordenes.
- Modificar `EURUSD.zip` o fabricar cobertura M1 posterior al dato real.
- Crear nuevas ramas.
- Sobrescribir cambios locales no relacionados.

## 4. Autoridades tecnicas

| Capa | Autoridad vigente | Estado |
|---|---|---|
| Linaje seis-TF | `engine/lineage.py`, `engine/lineage_hierarchy.py`, PR #16 | `MERGED_REMOTE / LOCAL_PRESERVED` |
| Secuencia causal multi-vela | `engine/sequence.py` | Phase-1 instalada localmente |
| Objetos de mercado | `engine/market_object.py`, `engine/historical_event_objects.py`, `engine/sixtf_marketobject_connector.py` | Conector seis-TF -> Episodes implementado en shadow diagnostic; replay integral de ventana historica pendiente |
| MarketState | `engine/market_state.py` | Consumidor causal; no debe fabricar padres |
| Setup Builder | `engine/setup_builder.py` | Autoridad de elegibilidad |
| Episodes/Funnel | `engine/episodes.py`, `audits/codigo/episodes.py` | SDD v1 existente; conector seis-TF ejecutable agregado |
| Backtest economico | consumidor aislado futuro bajo `backtest/` | No iniciado en esta fase |
| IA | `runtime/ai_learning/` | Shadow; no entrenamiento en esta fase |

## 5. Contrato de no-regresion seis-TF

La Mision 1 queda bloqueada si cualquier ruta intenta reducir el contexto a:

```text
H4 -> M15
```

El contexto minimo para candidatos nuevos es:

```text
D1 -> H4 -> H1 -> M15 -> M5 -> M1
```

Reglas:

1. H4/M15 puede mantenerse solo como regresion legacy o smoke test.
2. Un candidato nuevo de funnel debe publicar `lineage.status`.
3. `LINEAGE_VALID` exige cobertura causal segun contrato.
4. `LINEAGE_LEGACY_UNVALIDATED`, `LINEAGE_INCOMPLETE`, `LINEAGE_FUTURE`,
   `LINEAGE_ORPHAN`, `LINEAGE_CYCLE`, `LINEAGE_UNRESOLVED` e
   `LINEAGE_INVALID` fallan cerrado para candidato nuevo.
5. La ausencia de M1 posterior al fin real de la fuente se reporta como
   cobertura insuficiente; no se completa por inferencia.

## 6. Fases de Mision 1

### F0 — Auditoria documental y autoridad

**Estado:** `PASS`

Evidencia:

- SDD Episodes/Funnel v1 encontrado.
- Contrato Episodes/Funnel v1 encontrado.
- Contrato Lineage Hierarchy v1 encontrado.
- PR #16 registrado como mergeado en GitHub.
- HTML de trazado PR16 existente.

### F1 — SDD puente post-PR16

**Estado:** `PASS`

Entregable: este SDD. Define el camino unico y los gates antes de implementar o
entrenar. Esta es la fase que queda cerrada al 100% en esta mision.

### F2 — Implementacion del productor seis-TF hacia Episodes/Funnel

**Estado:** `PASS`

Debe producir, para cada `decision_time`, candidatos con:

- seis capas disponibles o rechazo explicito;
- lineage jerarquico validado;
- ids estables de objetos;
- causal `available_at`/cierre de vela;
- aceptados y rechazados sin ocultar ceros;
- FULL/PREFIX literal contra columnas causales.

Evidencia local:

- `engine/mission1_six_tf_pipeline.py`
- `scripts/audit/run_mission1_sixtf_pipeline.py`
- `tests/test_mission1_six_tf_pipeline.py`
- `reports/audits/experiments/mission1/mission1_episodes.json`

### F3 — Backtest funnel economico aislado

**Estado:** `PASS_SHADOW_DIAGNOSTIC`

No puede importar `engine/` de forma inversa ni mutar el motor diario. Debe
agregar costes, fill, spread, slippage, SL/TP, sesiones y PnL como consumidor
aislado. Un backtest verde no autoriza trading.

Evidencia local:

- `reports/audits/experiments/mission1/mission1_backtest.json`
- `can_trade=false`
- `economic_edge_claimed=false`

### F4 — Dataset causal para IA

**Estado:** `PASS_SHADOW_DIAGNOSTIC`

El dataset se materializa solo desde episodios causales. Labels futuros deben
estar separados de features. Splits temporales: DESIGN/TRAIN/VALIDATION/TEST
sin mirar TEST para decisiones de modelado.

Evidencia local:

- `reports/audits/experiments/mission1/mission1_dataset.json`
- 60 filas causales: 36 DESIGN, 12 VALIDATION, 12 HOLDOUT
- Labels futuros separados de `features_at_t`

### F5 — Entrenamiento IA shadow

**Estado:** `PASS_BASELINE_SHADOW_DIAGNOSTIC`

Entrenamiento permitido solo como `shadow_mode=true`, `can_trade=false`, con
baseline, calibracion, abstencion, seeds, reload y evaluacion OOS. No fusiona
con el motor sin nueva certificacion.

Evidencia local:

- `reports/audits/experiments/mission1/mission1_training.json`
- baseline determinista `deterministic_majority_baseline`
- `fit_executed=true`
- `production_model_created=false`
- `holdout_accuracy=0.3333333333333333`
- Este resultado cierra el cableado shadow, no demuestra edge.

## 7. Gates obligatorios para pasar de F1 a F2

| Gate | Requisito | Evidencia esperada |
|---|---|---|
| M1-G0 | Checkout operativo identificado sin sobrescribir cambios locales | `git status`, branch, SHA |
| M1-G1 | PR #16 disponible localmente o en worktree aislado | SHA `d4fdf68d` o HEAD equivalente |
| M1-G2 | Productor historico real cubre D1/H4/H1/M15/M5/M1 por cierre | verifier seis-TF |
| M1-G3 | `engine/episodes.py` consume lineage validado | tests focales |
| M1-G4 | FULL/PREFIX literal de episodios | reporte con divergencias cero |
| M1-G5 | Rechazos explicitos, no `None` silencioso | reporte de razones |
| M1-G6 | Suite relacionada verde | pytest focal + grupo causal |
| M1-G7 | Bitacora, indice, graphify y commit selectivo | evidencia local |

## 8. Riesgos actuales

1. El checkout principal tiene cambios sucios no relacionados; no se debe hacer
   reset, clean ni cambio destructivo.
2. La rama local actual es de preservacion, no la base remota mergeada de PR16.
3. El SDD Episodes/Funnel v1 es valido, pero nacio antes de PR16; cualquier
   implementacion nueva debe añadir gate seis-TF, no solo H4/M15.
4. Los inventarios A/B de detectores no equivalen a funnel completo.
5. Cualquier entrenamiento sobre muestras anteriores debe tratarse como
   historico/diagnostico hasta que salga de episodios seis-TF causales.

## 9. Dictamen de cierre

`MISION1_F2_F5 = COMPLETED_SHADOW_DIAGNOSTIC`.

La base si existia, pero no estaba conectada como mision post-PR16. Queda
implementado el puente local deterministicamente: episodios seis-TF, backtest
economico aislado, dataset causal y entrenamiento baseline shadow. El resultado
no declara edge, no crea modelo productivo y no autoriza trading.

## 10. Fase F6 — fuente real y productor historico

**Estado 2026-09-21:** `PASS_PREFLIGHT / FACTORY_SIXTF_CONTEXT_EXISTS / CONNECTION_IMPLEMENTED_SHADOW`.

Se ejecuto la siguiente fase escrita en los planes: sustituir la fixture
contractual por evidencia real. La fuente original ya pasa el gate seis-TF de
contexto, y el productor/replay historico real existente pasa el piloto H4/M15.
La auditoria posterior aclara un punto importante: no falta "toda la fabrica".
Ya existe una fabrica/capa real de contexto y features seis-TF en
`scripts/lab/experiments/v2_extractor_engine.py`, `engine/multitf_context.py`,
`engine/mtf_navigation.py` y `engine/ahf.py`. Esa capa carga y navega
D1/H4/H1/M15/M5/M1 con velas cerradas. Lo que falta conectar es su salida al
contrato canónico de objetos:

```text
Context/features seis-TF reales
  -> MarketObject con parent_object/related_objects
  -> HierarchicalLineage VALID
  -> SetupBuilder
  -> Episodes/Funnel real
```

`engine/historical_event_objects.py` sigue siendo el productor histórico real
de `MarketObject`, pero su alcance actual es H4/M15. `engine/detector_event_bridge.py`
puede convertir ocurrencias de detectores de las seis temporalidades a
`MarketObject`, pero declara explícitamente `lineage_status=UNRESOLVED` y
`lifecycle_status=NOT_REPLAYED`; no construye secuencia, lifecycle ni funnel.

Evidencia:

- `mission1_next_real_source_sixtf_context.json`: `all_pass=true`,
  `all_six_layers_available=true`, `all_six_layers_closed_only=true`,
  `future_invariance=true`, `control_a_m1_coverage=false` esperado por fin real
  de M1.
- `mission1_next_real_source_h4_m15_replay.json`: `all_pass=true`, control A
  `PASS_H4_M15_PIT_PILOT`, control B `PASS_H4_M15_PIT_PILOT`.
- `scripts/lab/experiments/v2_extractor_engine.py`: `TIMEFRAMES =
  ("D1", "H4", "H1", "M15", "M5", "M1")`; genera `features_at_t` y snapshot
  de contexto, pero registra `lineage.available=false`.
- `engine/setup_builder.py` y `engine/episodes.py`: ya consumen
  `MarketObject` con relaciones por `parent_object/related_objects`; el hueco
  esta antes de ellos, en la conversion de contexto/eventos seis-TF a grafo
  real de objetos.

Siguiente implementacion requerida:

```text
conectar fabrica seis-TF existente
  -> productor MarketObject seis-TF
  -> D1/H4/H1 context/POI
  -> M15 refinement/structure
  -> M5 confirmation
  -> M1 trigger/retest
  -> HierarchicalLineage LINEAGE_VALID
  -> build_episodes real
```

Esa extension inicial ya fue completada en la Mision 2 como conector ejecutable
de un `decision_time` auditado. La Mision 1 real-source deja de estar bloqueada
por ausencia de conexion y pasa al siguiente bloqueo metodologico: escalar a
ventana historica completa y ejecutar FULL/PREFIX de ventana antes de cualquier
backtest economico real.

## 11. Mision 2 — conector seis-TF MarketObject -> Episodes

**Estado 2026-09-21:** `PASS_SHADOW_DIAGNOSTIC`.

Se implemento:

```text
MTFNavigator / contexto seis-TF
  -> MarketObject seis-TF
  -> HierarchicalLineage(require_all_six_tfs=True)
  -> build_setups_at()
  -> build_episodes()
```

Entregables:

- `engine/sixtf_marketobject_connector.py`
- `tests/test_sixtf_marketobject_connector.py`
- `scripts/audit/run_sixtf_marketobject_connector.py`
- `reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json`
- `.hermes-worklog/2026-09-21_MISION2_SIXTF_CONNECTOR_IMPLEMENTED.md`

Evidencia:

```text
python -m pytest -q tests/test_sixtf_marketobject_connector.py
4 passed

python -m pytest -q tests/test_sixtf_marketobject_connector.py tests/test_lineage_hierarchy.py tests/test_setup_builder_integration.py tests/test_episodes.py
38 passed
```

Reporte con fuente local parquet:

```text
status=PASS
lineage.status=LINEAGE_VALID
six_tfs_complete=true
setup_count=2
episode_count=1
rejection_count=1
can_trade=false
edge_claimed=false
diagnostic_only=true
```

La implementacion no declara edge ni trading. El siguiente paso metodologico es:

```text
ventana historica multi-decision_time
  -> episodios aceptados/rechazados reales
  -> FULL/PREFIX de ventana
  -> backtest economico aislado
  -> dataset IA shadow
```
