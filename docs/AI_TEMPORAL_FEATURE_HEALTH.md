# Protección contra entrenamiento de una sola vela

El fallo recurrente es que el corpus puede contener muchas filas, pero cada fila
representa solo una vela y sus columnas resultan constantes. Eso hace que el
modelo produzca probabilidades casi idénticas y no aprenda secuencias ICT.

## Comportamiento automático

`runtime.ai_learning.feature_health.validate_temporal_feature_health` se ejecuta
antes del ajuste diagnóstico. Falla cerrado cuando:

- `features_at_t` falta o está vacío.
- `sequence_depth` es siempre cero.
- menos del 10% de los campos varía entre filas.

El error incluye la reparación: reconstruir una ventana de velas cerradas en el
motor canónico y transportar esa ventana al funnel y al backtest. La guarda no
rellena eventos, no invierte métricas y no modifica código por sí misma.

## Contrato de reparación

El extractor debe emitir una secuencia causal (mínimo profundidad y estado por
vela), el funnel debe conservarla sin resumirla a una sola vela y el backtest
debe consumir el mismo snapshot. Cualquier etapa que pierda la secuencia debe
detenerse antes de entrenar y registrar `TEMPORAL_FEATURES_NEAR_CONSTANT` o
`TEMPORAL_SEQUENCE_DEPTH_ZERO`.

El extractor canónico calcula ahora `sequence_depth` desde una ventana M15
cerrada de hasta ocho velas, contando la continuidad direccional reciente. El
smoke de dos días produjo profundidades de 1 a 8, en lugar de cero constante.
