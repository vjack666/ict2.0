# Plan — Setup Grammar Supervision v1

**Fecha:** 2026-09-15  
**Estado:** `READY_FOR_IMPLEMENTATION_LOOP`  
**Politica:** `can_trade=false`

## Objetivo

Guiar el entrenamiento neuronal con la tesis ICT del proyecto para que la red
aprenda a diagnosticar la construccion del setup, no solo su outcome final.

## Fase 1 — Inventario teorico local

Leer y congelar las fuentes locales:

- `docs/ict/20_TESIS_ICT.md`
- `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`
- `docs/ict/21_POI.md`
- `docs/reglas/ICT_RULEBOOK.md`
- `docs/tesis/SDD_SEQUENCE_EVENT_WAIT.md`
- `reports/b1/OBJETIVO2_DISENIO_ENSAMBLADOR.json`

Salida: matriz teoria -> evidencia -> feature -> etiqueta.

## Fase 2 — Materializacion causal

Crear `SETUP_GRAMMAR_DATASET_V1` con una fila por `decision_time`.

Campos minimos:

```text
event_id
decision_time
source_time_by_feature
htf_narrative
po3_phase
liquidity_sweep
displacement_quality
structure_confirmation
pd_array_zone
retest_entry
poi_quality
exec_tf_integrity
setup_decision
weak_link
label_end_6
```

Regla: todo `source_time <= decision_time`.

## Fase 3 — Entrenamiento multi-task

Entrenar `setup_quality_v1` con varias cabezas:

```text
setup_decision_head
weak_link_head
failure_risk_head
quality_tier_head
outcome_head
```

La red debe aprender a explicar por que un setup es incompleto, no solo decir
si fallo.

## Fase 4 — Comparacion

Comparar cuatro rutas:

```text
motor solo
motor + failure_risk_v1
motor + setup_quality_v1
motor + failure_risk_v1 + setup_quality_v1
```

Validar en `VALIDATION`; evaluar `TEST_OOS` una sola vez.

## Fase 5 — Investigacion controlada

Si falta teoria clave, no se entrena con intuiciones sueltas. Se abre item
`RESEARCH_REQUIRED`, se documenta fuente externa y se convierte en contrato
local antes de usarlo como feature o etiqueta.

Prioridad de investigacion:

1. Killzones London/NY y conversion broker/UTC.
2. M3 exec TF y scalping fino.
3. Breaker/Mitigation/BPR como PD Arrays entrenables.

## Criterio de avance

No se avanza a backtest economico hasta que `setup_quality_v1` mejore en
VALIDATION y sostenga beneficio en TEST_OOS sin destruir cobertura.
