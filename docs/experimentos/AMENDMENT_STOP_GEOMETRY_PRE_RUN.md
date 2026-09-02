# Enmienda previa — geometría del stop del experimento PASS_EDGE

**Estado:** `APPROVED_CAUSAL_AVG_RANGE_50`  
**Fecha:** 2026-09-02  
**No aplica a:** resultados ya generados; la prueba de humo queda excluida de
cualquier conclusión confirmatoria.

## Conflicto identificado

El preregistro de `EXP_PASS_EDGE_INTRADIA_01` describe el buffer como `0,3 ATR`.
El motor canónico, sin embargo, prohíbe indicadores ATR y usa una serie causal
de rango medio `high-low` de 50 velas, exportada por compatibilidad con el
nombre `atr`. `engine.execution.fine_execution` aplica `0,3` sobre esa serie.

Estas dos definiciones no son equivalentes y no pueden mezclarse sin declarar
una enmienda previa.

## Decisión adoptada

Se adopta `CAUSAL_AVG_RANGE_50`: conservar la autoridad actual del motor y
definir el buffer como `0,3 × rango medio causal high-low de 50 velas`. Esta
decisión se registra antes de cualquier corrida confirmatoria y no depende de
los resultados de la prueba de humo.

La opción `TRUE_ATR` queda descartada para este SDD: implementarla cambiaría la
restricción vigente de no usar indicadores en `engine/` y requeriría otro
experimento.

Las opciones consideradas fueron:

1. `CAUSAL_AVG_RANGE_50` — **adoptada**.
2. `TRUE_ATR` — descartada para este SDD.

El manifest final debe declarar que la columna histórica `atr` del motor es un
nombre de compatibilidad para el rango medio causal, no ATR clásico.
