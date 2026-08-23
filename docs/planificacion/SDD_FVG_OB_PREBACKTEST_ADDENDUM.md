# Addendum SDD — Pre-Backtest Audit Stack

Este documento extiende `SDD_FVG_OB_ARCHITECTURE_MAP.md` y es normativo mientras se completa la etapa pre-backtest.

## Cambio de arquitectura del plan

La ejecución/backtest no es el siguiente Gate inmediato. Antes se mantiene una capa de auditoría estructural:

```text
DATA
 ↓
DATA INTEGRITY
 ↓
SCHEMA / CANONICALIZATION
 ↓
POINT-IN-TIME
 ↓
SEMANTICS / CONTRACTS
 ↓
DETECTOR / METAMORPHIC
 ↓
CROSS-TIMEFRAME
 ↓
LINEAGE
 ↓
FUNNEL
 ↓
COVERAGE / REGIME
 ↓
EXPERIMENT GOVERNANCE
 ↓
TNA TRACE / BEHAVIORAL
 ↓
BACKTEST ELIGIBLE
```

## Motivo

El backtest mide comportamiento de una especificación de ejecución. Si la población de FVG/OB, su causalidad, navegación o datos no son confiables, la performance no es evidencia limpia del motor.

## Estado actualizado

- **A0-A9:** **PASS local full-stack reproducible**; confirmación CI del workflow queda pendiente.
- **Funnel MTF+Sequence 20Y:** **CERRADO — PASS + GATE CI**.
- **TNA FULL/PREFIX:** **PASS_BY_LAYER_INDUCTION + GATE PASS**; 124377 decisiones, 0 divergencias.
- **Ejecución:** **CONGELADA para `EXECUTION_INTRADAY_M15_V1`**, con validación de invariancia causal PASS.
- **Sequence × Context State:** **INSUFFICIENT_N**; no declarar diferencia de distribución.
- **Backtest:** gates pre-backtest PASS local, pero requiere decisión explícita del cliente y gate propio de datos/runtime; no autoriza PnL automáticamente.
- **M5:** diferido.
- **OTE/Fibonacci:** prohibidos.

## Artefactos canónicos actuales

- Funnel: `reports/audits/mtf_seq_funnel.json`.
- TNA trace estratificado: `reports/audits/AUDITORIA_TEMPORAL_AHF_RESULT.json`.
- Sequence × Context State: `reports/audits/exp_sequence_x_context_state_H1_20Y.json`.
- A0-A9 full-stack: `reports/audits/A0_A9_audit_stack.json`.
- Ejecución congelada: `docs/planificacion/EXECUTION_FREEZE_2026-08-22.json` y `reports/audits/execution_freeze_2026-08-22.json`.
- Cierre agregado: `reports/audits/pre_backtest_gate_close_2026-08-22.json`.

## Runners

El Funnel 20Y fue producido por `scripts/audit/grok_run_funnel_20y_full.py`, que orquesta las funciones canónicas de `audits/codigo/mtf_seq_funnel.py`. El artifact está protegido por un assert CI.

El TNA full-span tiene driver versionado `scripts/audit/tna_20y_parallel.py`; el gate cerrado en esta etapa es el artefacto behavioral/full-span streaming ya versionado, no una autorización de edge.

La ejecución congelada se valida con `audits/codigo/run_execution_freeze.py`; el perfil M15 no se extiende por inferencia a M5/M1/scalping ni a otro dataset M15.

## Regla

Cualquier modificación de la pila de auditorías requiere actualizar este addendum, el SDD principal, `.hermes-index.md` y el worklog antes de cambiar el Gate.

Un PASS de integridad nunca se convierte en edge por documentación. Un gate rojo no se convierte en verde cambiando el criterio después de observar el resultado.
