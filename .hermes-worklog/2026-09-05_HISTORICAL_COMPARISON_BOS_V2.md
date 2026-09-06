# Auditoria de continuidad: correccion BOS vs corrida V2 Q1

Fecha: 2026-09-05
Alcance: comparar la correccion aplicada el 2026-09-04 con la corrida V2 Q1 ejecutada hoy. Una sola reproduccion del runner historico; sin loops ni reintentos.

## Hallazgo
La correccion de BOS de ayer sigue presente en la rama actual (`cd1a5c2`, `engine/bos/structure.py`). Colapsa BOS consecutivos del mismo impulso y publica solo el primer evento hasta que cambia la direccion. No hay evidencia de regresion de esa correccion.

El resultado de 0 entradas de `v2_unblock_q1_backtest.json` no contradice el resultado de ayer: son pipelines y contratos distintos.

| Corrida | Entry point | Timeframes | Configuracion relevante | Resultado |
|---|---|---|---|---|
| Ayer, artefacto existente | `scripts/lab/experiments/run_pass_edge_proxy_pilot.py` | D1,H4,H1,M15,M5 | `execution_tf=M5`, `htf_timeframe=H4`, horizonte 12, runner legacy=false en su propio resumen | 2022 completo: 77 senales/trades; Q1 reproducido hoy: 17 senales/trades, 5 resueltos, media -0.433239R |
| Hoy, V2 | `scripts/export_visual_backtest.py` | M15,M5,M1 | `htf_timeframe=M15`, `require_displacement=true`, `displace_gap=6`, `sweep_lookback=8`, `multitf_context=false` | 4898 eventos, 123 sweeps, 0 displacement, 0 BOS, 0 entradas |

## Interpretacion
La corrida V2 se detiene antes de BOS porque no encuentra ningun displacement despues de los sweeps bajo su contexto M15 y sus marcos M15/M5/M1. Por tanto el funnel devuelve `BACKTEST_SIGNALS_MISSING` correctamente. No se deben fabricar episodios, labels ni metricas.

La diferencia no es que el arreglo de ayer se haya perdido; es que la comparacion no estaba controlada. El runner de ayer incluye H4/H1 y fija H4 como contexto HTF. La corrida V2 usa M15 como HTF efectivo y no activa el contexto multi-TF. Sus conteos no son comparables hasta igualar contrato y configuracion.

## Evidencia ejecutada
- `git show cd1a5c2 -- engine/bos/structure.py`: muestra `_collapse_bos_impulse` y su uso en `detect_market_structure`.
- Reproduccion unica Q1 del runner anterior: `reports/audits/experiments/ai/v2_unblock_q1_legacy_compare.json`.
- Corrida V2 actual: `reports/audits/experiments/ai/v2_unblock_q1_backtest.json`.
- El funnel V2 queda bloqueado por ausencia real de senales; no hay resultado economico V2.

## Decision y siguiente accion
Estado: REVIEW, no regresion BOS demostrada; comparabilidad V2 pendiente.

Siguiente accion acotada: ejecutar una unica corrida V2 de comparacion con los mismos marcos/contexto del runner de ayer (D1,H4,H1,M15,M5, HTF H4, execution M5, horizonte 12), manteniendo `can_trade=false`, y comparar phase_seen y lineage. Si vuelve a haber 0 displacement, el problema queda localizado en la regla/configuracion de displacement del motor y se corrige en `engine/`, no en el backtest.

No se autoriza promocion, trading ni entrenamiento con el funnel bloqueado.
