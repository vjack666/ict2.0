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

- **A0-A9:** definidos e implementados; evidencia CI full-stack sigue pendiente de cierre formal.
- **Funnel MTF+Sequence 20Y:** **CERRADO — PASS + GATE CI**.
- **TNA TRACE:** **PASS estratificado** (`PASS_TRACE_INTEGRITY`); no equivale a behavioral/full-span.
- **TNA BEHAVIORAL/full-span:** **PENDIENTE**.
- **Sequence × Context State:** **INSUFFICIENT_N**; no declarar diferencia de distribución.
- **Backtest:** **BLOQUEADO** hasta satisfacer la pila pre-backtest vigente + Funnel + TNA aceptables.
- **M5:** diferido.
- **OTE/Fibonacci:** prohibidos.

## Artefactos canónicos actuales

- Funnel: `reports/audits/experiments/fvg_ob/mtf_seq_funnel.json`.
- TNA trace estratificado: `reports/audits/temporal/AUDITORIA_TEMPORAL_AHF_RESULT.json`.
- Sequence × Context State: `reports/audits/experiments/sequential/exp_sequence_x_context_state_H1_20Y.json`.

## Runners

El Funnel 20Y fue producido por `scripts/audit/grok_run_funnel_20y_full.py`, que orquesta las funciones canónicas de `audits/codigo/mtf_seq_funnel.py`. El artifact está protegido por un assert CI.

El TNA full-span tiene driver versionado `scripts/audit/tna_20y_parallel.py`. Su PASS behavioral actual en código no debe declararse como resultado empírico hasta ejecutar el driver y versionar el reporte correspondiente.

## Regla

Cualquier modificación de la pila de auditorías requiere actualizar este addendum, el SDD principal, `.hermes-index.md` y el worklog antes de cambiar el Gate.

Un PASS de integridad nunca se convierte en edge por documentación. Un gate rojo no se convierte en verde cambiando el criterio después de observar el resultado.
