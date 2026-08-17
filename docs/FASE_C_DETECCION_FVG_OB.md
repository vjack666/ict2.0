# FASE C — DETECCIÓN CANÓNICA FVG / ORDER BLOCK

**Fecha:** 2026-08-17  
**Estado:** `IN_PROGRESS / GATE_PENDING`  
**Precondición:** Gate B PASS  
**Alcance:** detección; no ejecución, scoring de entrada ni aprendizaje.

## Objetivo

Implementar detectores canónicos FVG y Order Block que sean:

- causales;
- deterministas;
- compatibles con `MarketObject`;
- libres de look-ahead;
- observables por timestamp de creación, confirmación y tradabilidad.

## FVG canónico

Se utiliza el patrón de tres velas:

- bullish: `low[i] > high[i-2]`;
- bearish: `high[i] < low[i-2]`.

La detección queda confirmada y tradable al cierre de la tercera vela `i`. No se consulta ninguna vela posterior.

## Order Block canónico

Se implementa el contrato de `docs/ict/04_ORDER_BLOCKS.md`:

- bullish OB: vela de huella bajista con cuerpo mínimo configurable, seguida por una vela bullish cuyo cierre rompe el high de la huella;
- bearish OB: vela de huella alcista con cuerpo mínimo configurable, seguida por una vela bearish cuyo cierre rompe el low de la huella;
- la entrada/tradabilidad ocurre sólo después del cierre del follow-through.

`min_body_ratio=0.60` es un parámetro explícito del detector, no una verdad de estrategia congelada; debe poder evaluarse posteriormente por experimento/ablación.

## Anti-look-ahead

El contrato de C exige invariancia por prefijo: añadir velas futuras no puede modificar las señales ya confirmadas dentro del prefijo histórico.

Los tests comprueban:

- FVG no disponible antes de la tercera vela;
- OB no disponible en la huella sin follow-through cerrado;
- señales históricas invariantes al añadir futuro;
- compatibilidad temporal de `MarketObject`.

## Fuera de alcance

- Breaker como detector de cambio de estructura;
- BPR/composites;
- entrada/SL/TP;
- scoring de setup;
- aprendizaje y ablación;
- validación M5.

## Gate C

PASS sólo si:

1. detectores FVG y OB pasan sus tests;
2. anti-look-ahead pasa al 100% en las pruebas diseñadas;
3. la suite completa pasa;
4. no se introduce OTE/Fibonacci;
5. índice Hermes y worklog reflejan la evidencia real.

Si falla algo, corregir y repetir hasta PASS.
