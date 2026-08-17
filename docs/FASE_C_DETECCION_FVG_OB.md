# FASE C — DETECCIÓN CANÓNICA FVG / ORDER BLOCK

**Fecha:** 2026-08-17  
**Estado:** `IN_PROGRESS / GATE_PENDING`  
**Precondición:** Gate B PASS  
**Alcance:** detección; no ejecución, scoring de entrada ni aprendizaje.

## Objetivo

Implementar detectores canónicos FVG y Order Block que sean causales, deterministas, compatibles con `MarketObject`, libres de look-ahead y observables por timestamp de creación, confirmación y tradabilidad.

## Implementación

- FVG: patrón de tres velas, con confirmación/tradabilidad al cierre de la tercera vela.
- OB: huella contraria con cuerpo mínimo configurable + follow-through cerrado que rompe el extremo de la huella.
- Tests de prefijo: añadir futuro no modifica señales ya confirmadas.

## Gate C

PASS sólo si los detectores, anti-look-ahead, suite completa y documentación quedan en verde. Si falla algo, corregir y repetir.

## Estado de ejecución

Los detectores y tests están implementados en `agent/fase-c-domain`. El workflow de Hermes se ejecuta ahora en cualquier rama para que cada iteración de fase tenga evidencia CI reproducible.
