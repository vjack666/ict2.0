# Setup Grammar NO_ZONE Audit v1

**Estado:** `REVIEW`
**Trading:** `can_trade=false`

## Pregunta

Verificar si las filas `NO_ZONE` son errores de lectura de mercado o si realmente no habia PD Array causal disponible en la tesis/materializacion.

## Reglas de tesis usadas

- `21_POI.md`: un POI valido debe ser un PD Array, como OB/FVG/BPR, en contexto correcto; no cualquier geometria suelta.
- `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`: lectura top-down; HTF da sesgo, ITF marca zona, exec TF dispara.
- No se inventa zona: si la secuencia causal no trae PD Array, se mantiene `NO_ZONE` salvo que otra evidencia local cerrada lo marque para revision.

## Conteos

- Total filas: `292`
- NO_ZONE: `73` (`25.00%`)
- TEST_OOS: `19`
- TRAIN: `30`
- VALIDATION: `24`

## Dictamen por categoria

- `REVIEW_M15_DIRECTIONAL_GEOMETRY_PRESENT`: `73`

## Lectura

- Filas `NO_ZONE` cuya secuencia fuente ya tenia FVG/OB/BPR/etc.: `0`.
- Filas `NO_ZONE` donde la misma cadena tuvo zona despues: `73`. Eso no puede usarse para cambiar la etiqueta en el tiempo de decision porque seria futuro.
- Filas con geometria M15 direccional reciente que requieren revision semantica: `73`.
- Filas con cualquier geometria M15 reciente: `73`.

## Conclusión

El auditor no promueve ninguna fila `NO_ZONE` a zona valida. Cuando detecta geometria M15, la marca como `REVIEW`, porque la tesis exige contexto, sesgo, zona correcta y respaldo institucional. La siguiente correccion segura es materializar PD Arrays semanticos M15/ITF y compararlos contra estas filas.
