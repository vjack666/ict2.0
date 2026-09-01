# SDD — Exportador visual causal del motor ICT

Estado: nuevo componente implementado; consumidor observacional, sin autoridad de promoción.

## Extensión MTF Replay 2.0 (2026-09-01)

El schema 1.0 permanece compatible para el exportador visual simple. La próxima
salida normativa multitemporal será schema 2.0, definida por
`CONTRATO_MTF_REPLAY_ORCHESTRATOR_V1.md` y
`SDD_MTF_REPLAY_ORCHESTRATOR_V1.md`.

El visor React/Vite existente en el worktree
`codex/visual-replay-wyckoff-v1-1` es candidato a portarse como interfaz. Sus
schemas 1.1/1.2 y su proyección histórica son compatibilidad, no autoridad del
motor. El port debe conservar el cursor causal y los carriles TF, eliminar toda
reconstrucción de decisiones y consumir exclusivamente el artefacto 2.0.

La extensión 2.0 fue implementada el 2026-09-01. La UI vigente vive en
`backtest/viewer/`, conserva compatibilidad histórica rotulada y filtra por
`observation_time`. Su aceptación técnica M7 está en
`reports/audits/mtf_replay/mtf_replay_audit.json`. Esto no autoriza una corrida
científica ni una operación real.

## Objetivo

Producir un visual_backtest.json para ICT Structure Lab usando exclusivamente
las decisiones emitidas por el motor canónico vigente. El visor debe poder
avanzar vela por vela sin leer Swing/BOS/CHOCH simplificados ni reconstruir
operaciones por su cuenta.

## Alcance

- backtest/ contiene solo schema, replay adapter y serialización.
- scripts/export_visual_backtest.py carga los parquet actuales y ejecuta el
  replay nuevo.
- La autoridad de estructura es engine.bos.structure.
- La autoridad de features es engine.market_features.
- La autoridad de secuencia/contrato es engine.sequence.run_sequence.
- La autoridad de desenlace OHLC es engine.sequential_outcome.resolve_outcome.

No se usa ict_backtest/, no se añade una segunda implementación de detector y
no se autoriza trading o promoción.

## Contrato causal

Cada evento tiene index y confirmed_index. El índice de publicación nunca
precede a la confirmación del motor. parent_id solo puede apuntar a un evento
ya emitido. Los trades contienen entry_index; result_confirmed_index solo
aparece cuando el scan posterior encuentra SL o TP.

Las anotaciones que el motor calcula mirando la trayectoria posterior —por
ejemplo un estado retrospectivo o una calidad que cambia con follow-through—
no se exponen como si hubiesen estado disponibles en la vela de decisión.

## Verificación

- El schema rechaza eventos fuera del rango, padres futuros, índices no
  contiguos y salidas anteriores a la entrada.
- La prueba de prefijo compara el replay completo con un replay truncado y
  exige identidad para todos los eventos publicados antes del corte.
- La suite inspecciona que el paquete nuevo no importe ict_backtest.
- El export real queda separado de los tests sintéticos y no se ejecuta como
  backtest científico durante esta implementación.
