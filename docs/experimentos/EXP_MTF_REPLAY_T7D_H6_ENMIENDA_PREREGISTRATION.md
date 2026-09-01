# Preregistro — Enmienda H6: BOS y displacement como evidencias hermanas

## Motivo

T7d (DAG de hermanos, commit `de24d68`) demostró con datos reales que el
displacement puede preceder al BOS confirmado. El caso del 2025-01-17 tiene
displacement a las 15:15 UTC y BOS confirmado a las 15:30 UTC. El productor
histórico v3 ya modela BOS/displacement/FVG como evidencias hermanas del mismo
POI que "pueden publicarse en cualquier orden", pero el Setup Builder
(`classify_eligibility`, gate H6 congelado de la Tesis 1) impone
`t_confirmation <= t_trigger` (BOS antes que displacement). Esa restricción
bloquea el setup con `orden causal violado (H6): trigger ocurre antes que
confirmation (15:15 < 15:30)`, eliminando la población completa.

Esta enmienda se registra ANTES de tocar código, conforme al protocolo de
cambios de contrato congelados.

## Cambio de contrato

Relajar el gate H6 para que BOS (confirmation) y displacement (trigger) sean
**evidencias hermanas** del mismo POI, sin imponer un orden entre ellas.

- Se mantiene el orden causal estricto de la cadena de anclaje:
  `t_POI <= t_REFINEMENT <= t_DECISION`.
- Se mantiene `t_POI <= t_TRIGGER`: el displacement es una evidencia del POI,
  así que no puede precederlo.
- Se ELIMINA la restricción `t_CONFIRMATION <= t_TRIGGER` (BOS antes que
  displacement). El displacement puede preceder al BOS (crea la estructura) o
  seguirlo (confirma la ruptura); ambos son válidos.
- Se mantiene point-in-time: el setup solo se compone cuando todas las
  evidencias están publicadas y causalmente disponibles en T. Ningún setup
  aparece antes de que existan POI, FVG, BOS y displacement visibles.
- No se relaja ningún otro gate: POI/FVG ACTIVE, contexto HTF alineado,
  relación FVG↔OB, lineage hijo→padre, FULL/PREFIX, determinismo.

## Justificación técnica

En la interpretación habitual de ICT, el displacement puede ser el movimiento
agresivo que atraviesa estructura y deja el FVG detrás; el BOS/MSS queda
confirmado cuando hay evidencia suficiente para declararlo. Imponer
`BOS → displacement` como secuencia necesaria es una restricción semántica
incorrecta que los datos reales refutan. El DAG de hermanos ya lo permite; el
gate H6 debe alinearse con el contrato del productor v3.

## Alcance

- `engine/setup_builder.py`: `classify_eligibility` — quitar el par
  `("confirmation", "trigger", ...)` de la cadena estricta H6.
- `tests/test_integridad_causal_h6_h9.py`: actualizar
  `test_H6_trigger_anterior_al_confirmation_bloqueado` para reflejar que
  displacement puede preceder a BOS (evidencias hermanas).
- `tests/test_setup_builder_integration.py`: actualizar el helper `_disp_m15`
  y cualquier caso que asuma `BOS → displacement`.
- `docs/contratos/CONTRATO_HISTORICAL_EVENT_OBJECT_PRODUCER_V1.md`: reflejar
  la relajación de H6.

## Gates tras el cambio

1. Determinismo e IDs estables.
2. Lineage causal correcto (padre existe, `parent_time <= child_time`, sin
   referencias a futuro).
3. Lifecycle correcto (POI/FVG ACTIVE en T).
4. FULL/PREFIX exacto en 25/50/75/90%.
5. Setups completos > 0, elegibles > 0, episodios > 0.
6. Ningún setup aparece antes de que todas sus evidencias estén disponibles.
7. Sin look-ahead: la frontera X/Y tiene pruebas automáticas.

Si T7d vuelve a dar 0 setups tras este cambio, se diagnostica el siguiente
gate sin relajar reglas para fabricar población.

## Prohibiciones

- No se mide edge, beneficio ni WR en esta etapa.
- No se optimiza sobre resultados.
- No se entrena IA todavía.
- No se opera MT5 ni se emiten órdenes.
- No se amplía la ventana ni se seleccionan meses por resultados.
