# Funnel 20Y — MTF + Sequence + FVG/OB

**Status:** `COMPLETE`

## Anti-indicadores (norma aplicada)

```
EMA              = NO
ATR como bias    = NO
OTE / Fibonacci  = NO  (dealing range = EQ 50% only)
Fuente           = structure/BOS + FVG/OB + sequential + MTFNavigator
```

## FVG/OB (dataset completo 20Y, sin truncar)

| TF | bars | FVG | OB | relaciones STRICT | audit |
|----|-----:|----:|---:|------------------:|-------|
| H1 | 124377 | 22477 | 2799 | 702 | GateStatus.PASS |
| H4 | 32133 | 6497 | 862 | 206 | GateStatus.PASS |
| D1 | 6258 | 1543 | 214 | 58 | GateStatus.PASS |

## Sequence H1 (canonical_bos, full 20Y)

- n_chains: **1460**
- COMPLETE: **3**
- by_depth: `{1:767, 2:575, 3:86, 4:29, 7:3}`
- audit: `PASS`

## MTF navigation (dense, sample_every=100, full span)

- n_samples: **1239**
- ok_rate: **1.0**
- audit_status: `PASS`
- complete: `True`

## Policy

```
Funnel  =  auditoría de población / lineage / navegación
Funnel  ≠  edge, PnL, entry
```
