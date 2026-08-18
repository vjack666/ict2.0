# FASE C — DETECCIÓN CANÓNICA FVG / ORDER BLOCK

**Estado:** `IN_PROGRESS / GATE_PENDING`

## Objetivo
Implementar detectores causales FVG/OB compatibles con `MarketObject` y seguros contra look-ahead.

## FVG
Bullish: `low[i] > high[i-2]`. Bearish: `high[i] < low[i-2]`. La zona queda confirmada/tradable al cierre de la tercera vela `i`.

## Order Block
Última vela contraria (huella) con cuerpo mínimo configurable, seguida por follow-through cerrado cuyo cierre rompe el extremo de la huella. La tradabilidad comienza en el cierre del follow-through.

## Anti-look-ahead
Se exige invariancia por prefijo: añadir velas futuras no modifica señales ya confirmadas.

## Fuera de alcance
Breaker/BPR como detectores, ejecución, scoring, aprendizaje, M5 y OTE/Fibonacci.

## Gate C
PASS sólo con detectores + tests anti-look-ahead + suite completa en verde y documentación sincronizada. Ante fallo: corregir y repetir.
