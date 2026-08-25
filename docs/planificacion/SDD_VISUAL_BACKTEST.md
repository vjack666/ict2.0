# SDD — Exportador visual causal del motor ICT

Estado: nuevo componente implementado; consumidor observacional, sin autoridad de promoción.

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
