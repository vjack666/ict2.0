# OOS Q2 2022 — H4 solo frente a contexto completo

Estado: `REVIEW_INSUFFICIENT_RESOLVED_OOS`. Diagnóstico local; `can_trade=false`.

## Diseño congelado

La lógica se corrigió con Q1 2022. Esta evaluación usa Q2 2022, posterior a
esa corrección, con EURUSD M15 y un horizonte mecánico de 200 velas. Se
comparan los mismos datos y horizonte:

- Referencia: contexto H4 + M15 sellado.
- Tratamiento: D1/H4/H1/M15 sellados, con D1/H4/H1 como gate top-down.

## Resultado

| Métrica OOS | H4 + M15 | D1/H4/H1/M15 |
| --- | ---: | ---: |
| Señales/trades | 11 | 2 |
| TP resueltos | 2 | 0 |
| SL resueltos | 5 | 0 |
| OPEN tras H200 | 4 | 2 |
| Invalidaciones `DIRECTION_FLIP` | 23 | 0 |
| Anclas futuras o faltantes | 0 | 0 |

El contexto completo preservó D1/H4/H1/M15 en sus dos señales y eliminó los
cambios direccionales internos. Sin embargo, ambas siguen `OPEN` después de
200 velas: no se las cuenta como ganancia ni pérdida. Por ello no hay soporte
resuelto suficiente para afirmar que el filtro mejora o empeora el edge.

## Conclusión y siguiente acción

La mejora técnica de memoria contextual pasa OOS: no se perdió contexto ni se
usaron velas futuras. La hipótesis de edge queda en revisión. El siguiente
experimento debe ampliar periodos OOS sin modificar reglas y medir únicamente
outcomes cerrados por clase y dirección; después se puede materializar el
corpus completo para reentrenar el modelo.

El primer wrapper fue interrumpido por el cambio de sesión después de terminar
H4. El artefacto H4 se preservó y se ejecutó una sola recuperación del tramo
completo; no se repitió la referencia.
