# Enmienda previa — geometría del stop del experimento PASS_EDGE

**Estado:** `AMENDMENT_REQUIRED`  
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

## Regla de cierre

Antes de ejecutar DESIGN, VALIDATION o HOLDOUT, el manifest debe congelar una
de estas opciones:

1. `CAUSAL_AVG_RANGE_50`: conservar la autoridad actual del motor y renombrar
   la especificación económica para decir explícitamente “0,3 × rango medio
   causal de 50 velas”.
2. `TRUE_ATR`: implementar y verificar un ATR causal independiente, modificar
   la geometría de niveles y actualizar sus pruebas y hashes antes de correr el
   experimento.

El runner económico permanece `BLOCKED` hasta que una opción sea aprobada y
quede registrada en el preregistro y manifest. No se permite elegirla después
de observar resultados.
