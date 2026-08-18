# Worklog — Pre-Backtest Audit Stack

**Fecha:** 2026-08-18
**Estado:** DEFINICIÓN COMPLETADA — IMPLEMENTACIÓN PENDIENTE

## Decisión

Se revisó la estrategia de validación del motor ICT y se decidió no ejecutar un backtest de performance como siguiente Gate. Se introduce una pila de auditorías pre-backtest y el Funnel pasa a ser el Gate central de la etapa.

## Stack

A0 Data Integrity
A1 Schema / Canonical Data
A2 Temporal / Point-in-Time
A3 Semantic / Contract
A4 Detector / Metamorphic
A5 Cross-Timeframe Alignment
A6 Lineage / Causal
A7 Funnel
A8 Coverage / Regime / Concentration
A9 Selection / Experiment Governance

## Razón crítica

Un backtest prematuro puede producir métricas aparentemente buenas sobre una población de objetos todavía susceptible a errores semánticos, look-ahead, duplicación, joins futuros, concentración temporal o lineage incorrecto. Por ello el backtest queda bloqueado hasta superar la auditoría estructural.

## Revisión de SMC-SYSTEMS

Se inspeccionó `vjack666/SMC-SYSTEMS`. Su Completion Report registra split cronológico, validación de integración, walk-forward y técnicas cuantitativas posteriores como PurgedKFold, CVaR, DSR y PBO. Estas técnicas se consideran útiles para una etapa posterior, pero no sustituyen la auditoría estructural previa. El repositorio permanece como fuente comparativa, no como autoridad normativa.

## Documentación creada

- `docs/PLAN_PRE_BACKTEST_AUDIT_STACK.md`
- `docs/SDD_FUNNEL_AUDIT.md`
- `docs/CONTRATO_FUNNEL_AUDIT.md`
- `docs/SDD_FVG_OB_PREBACKTEST_ADDENDUM.md`

También se actualizó `.hermes-index.md` para bloquear formalmente el backtest hasta A0-A9.

## Próximo paso

Implementar A0-A6, ejecutar Gates, y sólo después construir/ejecutar A7 Funnel. Cada Gate debe terminar con tests, evidencia, SDD, índice y worklog sincronizados.
