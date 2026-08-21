# SDD — Frontera entre motor activo y laboratorio

**Estado:** NORMATIVO para la misión de consolidación
**Fecha:** 2026-08-21

## Objetivo

Mantener la lectura diaria de Hermes estable mientras el laboratorio investiga
y prepara candidatos de mejora. Investigar no equivale a promocionar.

## Autoridades

| Componente | Autoridad | Regla |
|---|---|---|
| `ACTIVE_ENGINE` | Lectura diaria MT5 → engine → brief → gráficos | Solo lectura; no entrena, no emite órdenes y no se modifica durante una lectura |
| `CANDIDATE_ENGINE` | Experimentos y propuestas del laboratorio | No puede reemplazar al activo directamente |
| Hermes | Estado, misiones, evidencia, recuperación y gates | No declara éxito por texto de agente |
| Usuario | Objetivo, SDD, protocolos y promoción | Aprueba cambios de autoridad o producción |

## Registro vigente

La frontera se declara en `runtime/engine_registry.json` y se valida mediante
`runtime/engine_registry.py`. El runtime diario debe fallar cerrado si la
política deja de ser `OBSERVE_ONLY_NO_ORDER` o si el laboratorio puede sustituir
al motor activo.

El estado actual es deliberadamente `UNPINNED_WORKTREE`: el repositorio tiene
artefactos experimentales locales sin consolidar. No se declara una versión
reproducible de producción hasta congelar código, datos y configuración.

## Reconciliación experimental

`scripts/lab/experiments/reconcile_current_experiments.py` lee exclusivamente
los JSON de auditoría en disco y produce:

- `reports/audits/experiments/current_batch/EXP_MASTER_RECONCILIATION.json`;
- `reports/audits/experiments/current_batch/EXP_MASTER_RECONCILIATION.md`.

La ausencia de un artefacto se marca `BLOCKED`. El informe no promueve señales,
parámetros ni motores.

## Promoción futura

Una promoción requiere, como mínimo, evidencia reproducible, integridad de
datos, pruebas fuera de muestra, revisión de costes, estabilidad temporal,
red-team, SDD/plan de actualización y aprobación del usuario. La versión activa
anterior se conserva y puede restaurarse.
