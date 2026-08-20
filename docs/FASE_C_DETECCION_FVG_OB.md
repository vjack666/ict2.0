# FASE C — DETECCIÓN CANÓNICA FVG / ORDER BLOCK

**Estado:** `PASS — GATE C CERRADO`

## Objetivo

Implementar detectores causales FVG/OB compatibles con `MarketObject` y seguros contra look-ahead.

## FVG

Bullish: `low[i] > high[i-2]`. Bearish: `high[i] < low[i-2]`. La zona queda confirmada/tradable al cierre de la tercera vela `i`.

## Order Block

Última vela contraria (huella) con cuerpo mínimo configurable, seguida por follow-through cerrado cuyo cierre rompe el extremo de la huella. La tradabilidad comienza en el cierre del follow-through.

## Anti-look-ahead

Se exige invariancia por prefijo: añadir velas futuras no modifica señales ya confirmadas. No se permite entrada en la huella sin follow-through cerrado.

## Evidencia

GitHub Actions `Hermes Tests` run `#69` / `32082868430`: **20 passed in 0.05s**.

## Decisión

Fase C queda cerrada. Fase D queda habilitada para resolver relaciones causales y lineage entre estructura, displacement y PD Arrays.

## Fuera de alcance

Breaker/BPR como detectores, ejecución, scoring, aprendizaje, M5 y OTE/Fibonacci.
