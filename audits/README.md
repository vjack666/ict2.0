# Auditorías ICT 2.0

Esta carpeta contiene el subsistema normativo de auditoría previo al backtest.

## Orden de ejecución

```text
A0 Data Integrity
A1 Schema / Canonical Data
A2 Point-in-Time / Look-Ahead
A3 Semantic / Contract
A4 Detector / Metamorphic
A5 Cross-Timeframe Alignment
A6 Lineage / Causal
A7 Funnel
A8 Coverage / Regime / Concentration
A9 Selection / Experiment Governance
```

No se ejecuta backtest de performance hasta superar los Gates A0-A9 según el contrato vigente.

## Estructura

- `contracts/` — contratos de entrada/salida y Gates.
- `core/` — utilidades comunes de auditoría.
- `checks/` — checks deterministas por dominio.
- `funnel/` — auditoría Funnel.
- `reports/` — generadores de reportes. Los reportes grandes derivados no se versionan aquí salvo decisión explícita.

## Reglas

1. Las auditorías son deterministas y point-in-time.
2. Una auditoría nunca relaja una regla para conseguir PASS.
3. Un FAIL debe producir diagnóstico, razón y artefacto reproducible.
4. Cada Gate actualiza `.hermes-index.md`, SDD y worklog.
5. Esta carpeta audita el motor; no contiene lógica de trading ni optimización de performance.
