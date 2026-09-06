# Análisis de conservación de contexto D1/H4/H1/M15

Fecha: 2026-09-06. Estado: `PASS_TECHNICAL_REVIEW_EDGE`.

## Comparación causal

Se comparó EURUSD Q1 2022 en replay canónico M15. La referencia H4 previa
usaba M15/M5/M1/H4. El modo completo añadió D1/H4/H1, conservó la vela M15 que
confirmó el sweep y ejecutó el gate top-down sobre velas cerradas.

| Medida | Solo H4 | D1/H4/H1/M15 |
| --- | ---: | ---: |
| Sweeps observados | 237 | 75 |
| Displacement | 27 | 8 |
| BOS | 19 | 8 |
| Señales/trades diagnósticos | 18 | 8 |
| Invalidaciones `DIRECTION_FLIP` | 24 | 1 |
| Referencia sellada por señal | H4 | D1, H4, H1, M15 |
| Capas ancladas futuras o faltantes | no auditables antes | 0 / 0 |

Las diez señales menos no se perdieron por una ventana artificial ni por una
vela M5/M15: no atravesaron el gate D1/H4/H1. Esto reduce cambios de dirección
internos y conserva la tesis de arriba abajo.

## Cambios aplicados

- El exportador completo carga D1/H4/H1 cuando se solicita `--multitf-context`.
- El ancla de contexto conserva D1/H4/H1 y la vela M15 del sweep.
- El replay cachea el snapshot mientras no cambian las últimas velas cerradas
  D1/H4/H1. M5/M1 no se recalculan como contexto de sesgo porque solo refinan
  ejecución y no pueden vetar la tesis mayor.

## Interpretación correcta

La mejora es de integridad de contexto: 24 cancelaciones por cambio direccional
pasaron a 1. No es aún una mejora de rentabilidad. En seis velas de horizonte,
la mayoría de resultados queda `OPEN`, y ocho observaciones no prueban edge.

`can_trade=false`, `DIAGNOSTIC_ONLY`, sin promoción, órdenes ni push.

Evidencia: `v2_full_context_anchor_q1_cached_backtest.json` y
`v2_full_context_anchor_q1_analysis.json`.
