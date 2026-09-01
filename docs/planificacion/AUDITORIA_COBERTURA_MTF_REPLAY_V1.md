# Auditoría de cobertura — Replay Orchestrator MTF v1

**Fecha:** 2026-09-01

**Estado:** CERRADA — diseño nuevo requerido, motores existentes reutilizados

**Owner:** D1 PMO con revisión D2 Ingeniería y D5 Assurance

**Modo:** `LOCAL_ONLY`

## Objetivo auditado

Determinar si el proyecto ya puede reproducir, en un único reloj causal, el
camino `contexto HTF → zona ITF → disparo EXEC → invalidación → outcome`, y si
el visor local existente puede mostrarlo sin crear otro motor.

## Dictamen

El repositorio ya contiene las autoridades de detección, lifecycle,
`MarketState`, `SetupBuilder`, Episodes/Funnel y resolución OHLC. También existe
un visor local útil en el worktree `codex/visual-replay-wyckoff-v1-1`. Falta la
capa que ordena esas autoridades barra por barra entre temporalidades.

Por tanto:

- no se crea otro detector, lifecycle, MarketState, SetupBuilder ni Funnel;
- se crea un **orquestador consumidor** dentro de `backtest/`;
- se extiende el contrato del artefacto visual a versión 2.0;
- se porta el visor por cambio mínimo y auditable, nunca copiando su motor
  histórico de proyección;
- el resultado sigue siendo diagnóstico: no prueba edge ni autoriza órdenes.

## Matriz REUSE / EXTEND / NEW

| Necesidad | Autoridad o activo hallado | Decisión | Motivo |
|---|---|---|---|
| Contexto y navegación MTF | `SDD_CONTEXT_STATE_MTF_NAVIGATION.md`, AHF | REUSE | Ya gobierna locks, rollback y lectura top-down. |
| Roles HTF/ITF/EXEC | `CONTRATO_MULTI_TF_LAYERS.md` | REUSE | Las tres capas ya son independientes. |
| Vida y autoridad de objetos | `engine/lifecycle.py` y SDD post-A7 | REUSE | El TF observador no puede matar al TF autoridad. |
| Estado as-of T | `engine/market_state.py` | REUSE | Es la proyección causal vigente. |
| Elegibilidad del setup | `engine/setup_builder.py` | REUSE | Separa estado del objeto de elegibilidad. |
| Episodes/Funnel | `engine/episodes.py` y su contrato | REUSE | Agrupa decisiones; no es backtest ni orden. |
| Desenlace OHLC | `engine/sequential_outcome.py` | REUSE | Resuelve SL/TP/horizonte después de la entrada. |
| Exportador visual | `backtest/replay.py`, `backtest/schema.py` | EXTEND | El schema 1.0 no expresa snapshots MTF, invalidaciones ni Episodes. |
| Visor web local | worktree `codex/visual-replay-wyckoff-v1-1` | EXTEND/PORT | Ya posee cursor y carriles TF; su proyección histórica no es autoridad. |
| Reloj causal multitemporal | No existe como componente canónico | NEW | Debe fusionar cierres y aplicar un orden determinista. |
| Perfil de temporalidades | Reglas dispersas en libros 15–18 | NEW CONFIG | Evita fijar M5 como obligatorio para todo intradía. |
| Checkpoint/reanudación | Parcial en otras zonas | NEW LOCAL | Necesario para equipos con memoria limitada y corridas largas. |

## Huecos reales

1. El replay actual ejecuta una secuencia principal y añade contexto MTF, pero
   no dirige todas las transiciones H4/M15/M5 en un solo reloj.
2. El schema visual 1.0 y el schema 1.1/1.2 del visor histórico no tienen una
   autoridad documental común.
3. No está congelado qué ocurre cuando varias velas cierran en el mismo
   timestamp.
4. No existe una distinción exportada entre `setup invalidado antes de entry` y
   `trade abierto cuyo contexto se invalida después`.
5. Falta una política de recursos para no cargar veinte años y todas las
   temporalidades en memoria.

## Mejoras incorporadas al pedido

- **Reloj por lotes:** `CLOSE_BATCH → SNAPSHOT → DECISION → EXECUTION`. Evita
  carreras cuando H4, M15 y M5 cierran a la misma hora.
- **Perfiles, no hardcode:** intradía M15, intradía con refinamiento M5 y
  scalping son configuraciones diferentes.
- **Artefacto por deltas:** snapshots completos solo en checkpoints; entre
  ellos se guardan transiciones. Reduce memoria y tamaño.
- **Fail-closed:** una capa ausente, un timestamp ambiguo o lineage roto no se
  rellena por intuición; produce rechazo canónico.
- **Separación de preguntas:** validez del setup, calidad científica y outcome
  del trade son campos diferentes.

## Condición de salida de esta auditoría

`PASS_DOCUMENTAL`: existe base suficiente para redactar contrato, SDD y plan.
No equivale a implementación, backtest, edge, certificación ni trading.
