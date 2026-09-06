# Corrección causal y OOS Q2 con cola de resolución — 2026-09-06

## Estado
COMPLETED_DIAGNOSTIC_ONLY. `can_trade=false`; no hubo promoción, órdenes ni push.

## Hallazgo y corrección
El replay previo de Q2 cerraba en `2022-06-30 00:00 UTC`, dejando las entradas tardías sin sus 200 velas M15. Al extender la ventana se detectó además que el ciclo de vida retrospectivo de BOS/CHOCH podía alterar el sesgo de un snapshot anterior.

El motor conserva ahora `bos_active_dir`/`choch_active_dir` y su barra fuente por cada vela cerrada. `engine.plan` usa ese estado point-in-time para D1/H4/H1: una invalidación o supersesión posterior no cambia el contexto congelado de una decisión pasada.

## Evidencia
- Prueba focal temporal y regresiones: 8 passed.
- Comprobación H4 real: los snapshots entre 2022-06-28 y 2022-06-30 son idénticos con datos cortados al 30 de junio o extendidos al 8 de julio.
- OOS causal: `reports/audits/experiments/ai/v2_context_oos_q2_causal_buffered_20260906/summary.json`.

## Resultado OOS (abril--junio 2022, H200; datos de resolución hasta 2022-07-08)
| Perfil | Señales | TP | SL | Sin resolver |
|---|---:|---:|---:|---:|
| H4 solo | 12 | 2 | 6 | 4 |
| D1/H4/H1/M15 | 6 | 1 | 3 | 2 |

Los dos registros del 2022-06-29 quedaron separados por 8h45: 01:00 UTC terminó TP; 09:45 UTC sigue OPEN/sin resolución. No se contabiliza OPEN como ganancia o pérdida.

## Artefactos anteriores
`v2_context_oos_q2_20220906` queda invalidado para métricas de resultado: carecía de la cola de resolución y se produjo antes de la corrección point-in-time. Se conserva para trazabilidad, no como evidencia de edge.

## Ampliación Q2--Q4
La matriz causal consolidada termina BLOCKED_INSUFFICIENT_RESOLVED_SUPPORT: 7 trades resueltos full-context, por debajo de 30; no hay materialización ni entrenamiento.
