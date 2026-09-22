# Plan ejecutable — Mision 1 seis-TF -> Funnel -> Backtest -> IA

**Fecha:** 2026-09-21  
**Estado:** `F0_F5_COMPLETED_SHADOW_DIAGNOSTIC`
**SDD:** `docs/planificacion/SDD_MISION1_SIXTF_FUNNEL_BACKTEST_IA_V1.md`  
**Contratos base:** `CONTRATO_LINEAGE_HIERARCHY_V1`, `CONTRATO_EPISODES_FUNNEL_V1`  
**Politica:** `LOCAL_ONLY`, `can_trade=false`, sin nuevas ramas, sin push salvo instruccion explicita.

## Objetivo

Convertir el cierre PR16 de linaje seis-TF en una ruta ejecutable hacia:

```text
episodios seis-TF causales -> backtest funnel -> dataset IA -> entrenamiento shadow
```

## Fase cerrada ahora

### F0 — Buscar base reutilizable

- [x] Revisar indice maestro.
- [x] Revisar SDD Episodes/Funnel v1.
- [x] Revisar Contrato Episodes/Funnel v1.
- [x] Revisar Contrato Lineage Hierarchy v1.
- [x] Consultar Graphify para la relacion lineage/episodes/funnel.
- [x] Confirmar PR16 mergeado remoto como autoridad previa.

Resultado: existe base reutilizable; no se crea un segundo funnel.

### F1 — Crear puente post-PR16

- [x] Definir SDD de Mision 1.
- [x] Congelar no-regresion seis-TF: no H4/M15 como contexto principal.
- [x] Separar fase documental de implementacion, backtest y entrenamiento.
- [x] Definir gates M1-G0..M1-G7.
- [x] Declarar bloqueos actuales sin sobrescribir cambios locales.
- [x] Actualizar indice y bitacora.

Resultado: fase documental/preflight completada al 100%.

## Fases F2-F5 cerradas

Se implemento y verifico la ruta local completa F2-F5 en modo shadow
diagnostico.

### F2 — productor seis-TF hacia Episodes/Funnel

- [x] `engine/mission1_six_tf_pipeline.py`
- [x] `mission1_episodes.json`
- [x] Gate seis-TF completo: D1/H4/H1/M15/M5/M1.
- [x] FULL/PREFIX literal PASS.

### F3 — backtest economico aislado

- [x] `mission1_backtest.json`
- [x] Costes de spread, slippage y comision aplicados.
- [x] `economic_edge_claimed=false`
- [x] `can_trade=false`

### F4 — dataset causal IA

- [x] `mission1_dataset.json`
- [x] 60 filas, splits DESIGN/VALIDATION/HOLDOUT.
- [x] Labels futuros separados de features.

### F5 — entrenamiento shadow

- [x] `mission1_training.json`
- [x] Baseline determinista entrenado/evaluado.
- [x] `production_model_created=false`
- [x] `can_trade=false`

### Verificacion

- [x] `python -m pytest -q tests/test_mission1_six_tf_pipeline.py` -> `5 passed`
- [x] Regresion relacionada -> `51 passed`
- [x] CLI `scripts/audit/run_mission1_sixtf_pipeline.py` -> `status=PASS`

## No-go

- No entrenar IA hasta F4/F5.
- No backtest economico hasta F3.
- No declarar edge.
- No conectar MT5.
- No usar M1 inexistente por inferencia.
- No crear ramas nuevas.

## Siguiente paso autorizado tecnicamente

Sustituir la fixture contractual de F2 por productor historico real sobre la
fuente original, conservando los mismos gates. Esta siguiente etapa no es
necesaria para cerrar el cableado F2-F5 shadow, pero si para buscar evidencia
empirica real o edge.

## Fase siguiente ejecutada: F6 — preflight productor historico real

**Estado:** `PASS_PREFLIGHT / FACTORY_SIXTF_CONTEXT_EXISTS / CONNECTION_IMPLEMENTED_SHADOW`

- [x] Buscar SDD, planes y tareas pendientes relacionados.
- [x] Confirmar que la fase siguiente escrita es sustituir la fixture
  contractual por productor historico real sobre fuente original.
- [x] Ejecutar verificador real seis-TF de contexto contra `EURUSD.zip`.
- [x] Ejecutar verificador real H4/M15 de productor + causal replay contra
  `EURUSD.zip`.
- [x] Registrar que la fabrica de contexto/features seis-TF ya existe, pero
  no esta conectada como productor real de `MarketObject` + `Episodes/Funnel`.
- [x] Registrar que el productor historico real de `MarketObject` existente
  todavia es H4/M15 y no cubre objetos completos D1/H4/H1/M15/M5/M1.

Evidencia:

- `reports/audits/experiments/mission1/mission1_next_real_source_sixtf_context.json`
- `reports/audits/experiments/mission1/mission1_next_real_source_h4_m15_replay.json`
- `.hermes-worklog/2026-09-21_MISION1_F6_REAL_SOURCE_PREFLIGHT.md`

Resultado:

```text
six_tf_context_all_pass=true
h4_m15_replay_all_pass=true
factory_sixtf_context=EXISTS
producer_marketobject_scope=H4_M15_PILOT_ONLY
connection_to_real_episodes=PENDING
next_required_work=connect existing six-TF context factory to six-TF MarketObject production and build_episodes
```

No se declara full funnel real, edge, MT5 ni entrenamiento productivo.

## Mision 2 ejecutada — conector seis-TF MarketObject -> Episodes

**Estado:** `PASS_SHADOW_DIAGNOSTIC`

- [x] Crear puente entre fabrica seis-TF existente y `MarketObject`.
- [x] Validar `HierarchicalLineage(require_all_six_tfs=True)`.
- [x] Alimentar `build_setups_at()`.
- [x] Alimentar `build_episodes()`.
- [x] Conservar rechazos explicitos.
- [x] Ejecutar pruebas focales.
- [x] Ejecutar regresion relacionada.
- [x] Generar reporte local.
- [x] Actualizar bitacora, indice y Graphify.
- [x] Commit y push en rama existente, sin crear ramas nuevas.

Evidencia:

- `engine/sixtf_marketobject_connector.py`
- `tests/test_sixtf_marketobject_connector.py`
- `scripts/audit/run_sixtf_marketobject_connector.py`
- `reports/audits/experiments/mission1/sixtf_marketobject_connector_report.json`
- `.hermes-worklog/2026-09-21_MISION2_SIXTF_CONNECTOR_IMPLEMENTED.md`

Resultados:

```text
tests/test_sixtf_marketobject_connector.py -> 4 passed
regresion relacionada -> 38 passed
sixtf_marketobject_connector_report.status=PASS
lineage.status=LINEAGE_VALID
six_tfs_complete=true
setup_count=2
episode_count=1
rejection_count=1
can_trade=false
edge_claimed=false
```

## Mision 3 ejecutada — ventana historica multi-decision_time

**Estado:** `PASS_SHADOW_DIAGNOSTIC`

- [x] Extender runner con modo `window`.
- [x] Ejecutar multiples `decision_time` sobre datos locales seis-TF.
- [x] Comparar FULL vs PREFIX truncado en cada `decision_time`.
- [x] Registrar episodios aceptados y rechazos explicitos.
- [x] Agregar checksum de ventana.
- [x] Mantener `can_trade=false` y `edge_claimed=false`.
- [x] Ejecutar pruebas focales y regresion relacionada.

Evidencia:

- `scripts/audit/run_sixtf_marketobject_connector.py`
- `reports/audits/experiments/mission3/sixtf_window_report.json`
- `.hermes-worklog/2026-09-21_MISION3_SIXTF_WINDOW_FULL_PREFIX.md`

Resultados:

```text
status=PASS
decision_count=13
pass_count=13
episode_count=13
rejection_count=13
full_prefix_failure_count=0
window_checksum=77b70956af5e1d7036f97633229ade3f6ca05669728d359658698955e82d68df
tests focales -> 5 passed
regresion relacionada -> 39 passed
```

## Mision 4 ejecutada — backtest economico aislado seis-TF

**Estado tecnico:** `PASS_DIAGNOSTIC`  
**Estado economico:** `REVIEW_NEGATIVE_EXPECTANCY`

- [x] Crear consumidor aislado en `backtest/`.
- [x] Consumir episodios reales seis-TF.
- [x] Resolver salida con M1 futuro.
- [x] Aplicar spread, slippage y comision.
- [x] Mantener `can_trade=false` y `edge_claimed=false`.
- [x] Ejecutar ventana amplia viable.
- [x] Documentar resultado negativo sin maquillar.

Evidencia:

- `backtest/sixtf_episode_backtest.py`
- `scripts/audit/run_sixtf_episode_backtest.py`
- `tests/test_sixtf_episode_backtest.py`
- `reports/audits/experiments/mission4/sixtf_episode_backtest_2022_03.json`
- `.hermes-worklog/2026-09-21_MISION4_SIXTF_ECONOMIC_BACKTEST.md`

Resultado:

```text
period=2022-03-01T00:00:00Z -> 2022-03-31T23:00:00Z
decision_count=553
episode_count=553
resolved_count=466
TP=153
SL=313
HORIZON=87
win_rate=0.3283261802575107
mean_net_R=-0.5733476394850038
sum_net_R=-267.1800000000118
tests relacionados=45 passed
```

Siguiente paso:

```text
Mision 5: calibracion
  -> revisar entry/SL/TP/horizon/filtros
  -> no entrenar IA economica hasta mejorar expectancy
  -> mantener can_trade=false
```
