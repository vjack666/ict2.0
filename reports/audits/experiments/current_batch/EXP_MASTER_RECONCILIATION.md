# Reconciliación maestra de experimentos A/B/C

> Fuente de verdad: JSON de auditoría presentes en `reports/audits/experiments/current_batch/`. Los resúmenes de agentes no sustituyen artefactos.

- Generado: `2026-08-21T19:41:15.126758+00:00`
- Esperados: `15` · observados: `10`
- Promoción: **BLOCKED**
- Motivo: Current batch is diagnostic only; B is missing, A2 is blocked, and no candidate may replace GEN-000.

## Proposiciones

- `P1_baseline_edge`: **CONDITIONAL_PASS**
- `P2_htf_incremental_value`: **BLOCKED**
- `P3_oos_robustness`: **INCOMPLETE**
- `P4_m15_m5_live_scope`: **NOT_TESTED**

## Experimentos

| Grupo | Experimento | Estado | Provisional | Evidencia |
|---|---|---|---|---|
| A | EXP_A1 | **PASS** | no | sí |
| A | EXP_A2 | **BLOCKED** | no | sí |
| A | EXP_A3 | **FAIL** | no | sí |
| A | EXP_A4 | **PASS** | sí | sí |
| A | EXP_A5 | **PASS** | no | sí |
| B | EXP_B1 | **BLOCKED** | no | no |
| B | EXP_B2 | **BLOCKED** | no | no |
| B | EXP_B3 | **BLOCKED** | no | no |
| B | EXP_B4 | **BLOCKED** | no | no |
| B | EXP_B5 | **BLOCKED** | no | no |
| C | EXP_C1 | **PASS** | sí | sí |
| C | EXP_C2 | **FAIL** | sí | sí |
| C | EXP_C3 | **BLOCKED** | no | sí |
| C | EXP_C4 | **PASS** | no | sí |
| C | EXP_C5 | **FAIL** | no | sí |

## Política

- Este informe no promueve señales ni cambios de motor.
- Un experimento sin JSON de auditoría queda `BLOCKED`.
- La producción permanece en `GEN-000` hasta una promoción gobernada.
