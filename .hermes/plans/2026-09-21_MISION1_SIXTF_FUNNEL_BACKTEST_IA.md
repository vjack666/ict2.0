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
