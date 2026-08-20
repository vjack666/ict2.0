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

## Subsistema implementado

La ejecución de auditorías vive en `audits/` y está desacoplada de la lógica de trading:

```text
`audits/`
├── contracts/   # GateStatus, Finding, AuditResult
├── core/        # invariantes temporales reutilizables
├── checks/      # checks por dominio, empezando por A0
├── funnel/      # motor A7
└── reports/     # artefactos derivados no versionados por defecto
```

Implementación inicial:

- `audits/contracts/gate.py`
- `audits/core/temporal.py`
- `audits/checks/data_integrity.py`
- `audits/funnel/engine.py`
- `tests/test_audit_subsystem.py`

## Estado

- A0-A9: definidos contractualmente.
- A0: primera implementación ejecutable.
- A2: utilidades temporales ejecutables.
- A7 Funnel: primera implementación ejecutable y con contrato de findings.
- Tests de subsistema: añadidos; Gate CI pendiente de evidencia.
- Backtest: bloqueado hasta PASS de la pila.
- M5: sigue diferido.
- OTE/Fibonacci: siguen prohibidos.

## Referencia SMC-SYSTEMS

La auditoría comparativa de `vjack666/SMC-SYSTEMS` identificó material útil de validación posterior (split cronológico, walk-forward, PBO/DSR/PurgedKFold/CVaR), pero no se adelanta al Funnel. El repositorio externo es referencia comparativa, no autoridad normativa.

## Regla

Cualquier modificación de la pila de auditorías requiere actualizar este addendum, el SDD principal, `.hermes-index.md` y el worklog antes de cambiar el Gate.
