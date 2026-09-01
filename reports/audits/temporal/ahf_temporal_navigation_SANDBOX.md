# TNA SANDBOX — Multi-ventana mínima

- **Cobertura:** `STRATIFIED_MULTI_WINDOW_MINI`
- **Overall:** **PASS**
- **Rollback fix validado:** **true** (max depth observado = 2.0)
- **Barras totales:** 170 (STEP=4)
- **Invalidaciones:** 51
- **Dataset:** `datasets/eurusd_dukascopy_20y`
- **Policy:** AHF_STATE_NOT_ENTRY
- **Precompute sequences:** False (sandbox speed)

## Gates

| Gate | Estado |
|------|--------|
| TNA-TRACE-INTEGRITY | **PASS** |
| ROLLBACK_DEPTH_INSTRUMENTATION | **PASS** |
| **OVERALL** | **PASS** |

## Por ventana

| Ventana | Barras | Status | Inv | RB max | Down/Up |
|---------|-------:|--------|----:|-------:|---------|
| 2017-smoke | 55 | PASS_TRACE_INTEGRITY | 18 | 1.0 | 4/2 |
| 2020-covid | 60 | PASS_TRACE_INTEGRITY | 18 | 2.0 | 20/17 |
| 2024-recent | 55 | PASS_TRACE_INTEGRITY | 15 | 1.0 | — |

## Hallazgo clave

Antes del fix, `rollback_depth` era **siempre 0** (parent_state se trataba como TF).
Después del fix (`state_to_tf`), se observan profundidades 1 y 2 en invalidaciones reales.

## Nota de cobertura

Esta corrida **no** declara PASS full-span de 20 años (124k barras).
Sirve para validar instrumentación y comportamiento en 3 regímenes distintos.
La corrida full-span sigue pendiente en máquina con más recursos (`scripts/tna_audit_runner.py`).
