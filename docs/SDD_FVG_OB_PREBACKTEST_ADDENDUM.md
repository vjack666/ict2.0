# Addendum SDD — Pre-Backtest Audit Stack

Este documento extiende `SDD_FVG_OB_ARCHITECTURE_MAP.md` y es normativo mientras se implementa la etapa pre-backtest.

## Cambio de arquitectura del plan

La ejecución deja de ser el siguiente Gate inmediato. Antes del backtest se introduce una capa de auditoría estructural:

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
BACKTEST ELIGIBLE
```

## Motivo

El backtest mide comportamiento de una especificación de ejecución. Si la población de FVG/OB, su causalidad o sus datos no son confiables, la performance no es evidencia limpia del motor. La auditoría Funnel y sus predecesoras buscan demostrar primero la integridad de esa población.

## Estado

- A0-A9: definidos contractualmente.
- A7 Funnel: definido como Gate central.
- Backtest: bloqueado hasta PASS de la pila.
- M5: sigue diferido.
- OTE/Fibonacci: siguen prohibidos.

## Referencia SMC-SYSTEMS

La auditoría comparativa de `vjack666/SMC-SYSTEMS` identificó material útil de validación posterior (split cronológico, walk-forward, PBO/DSR/PurgedKFold/CVaR), pero no se adelanta al Funnel. El repositorio externo es referencia comparativa, no autoridad normativa.

## Regla

Cualquier modificación de la pila de auditorías requiere actualizar este addendum, el SDD principal, `.hermes-index.md` y el worklog antes de cambiar el Gate.
