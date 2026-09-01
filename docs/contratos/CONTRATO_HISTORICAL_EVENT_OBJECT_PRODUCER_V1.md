# Contrato — Historical Event Object Producer v3

## Autoridades reutilizadas

- BOS: `engine.bos.structure.detect_market_structure`, columna causal `bos_dir`.
- Displacement: `detectors.displacement.detect_displacement`.
- POI/refinement: detectores canónicos OB H4 y FVG M15.

No se usa `bos_real` para crear eventos porque su quality score contiene una
etiqueta posterior. No se redefinen detectores dentro de backtest.

## Lineage y tiempo

DAG: `OB H4 → {FVG M15, BOS M15, displacement M15}`. Los tres eventos M15
son evidencias hermanas del mismo POI y pueden publicarse en cualquier orden;
el Setup Builder solo compone cuando todos son visibles. Esto cubre el caso
observado donde el displacement causa la ruptura y el BOS se confirma después,
sin crear referencias a objetos futuros. Ventana congelada POI→hijo: 120 h.
Se elige el padre previo más reciente, ACTIVE en su
temporalidad de autoridad y compatible en dirección; FVG además debe solapar el
POI.

IDs BOS/displacement se derivan de tipo, TF, timestamp UTC y dirección. Todos
los eventos nacen, se confirman y se vuelven tradables al cierre de su vela.
BOS/displacement son evidencia publicada inmutable; no pasan por mitigation de
FVG/OB.

## Gates

- determinismo e IDs estables;
- padre existente y `parent_time <= child_time`;
- sin referencias padre→hijo futuro;
- FULL/PREFIX exacto en varios cortes;
- setups completos solo mediante `engine.setup_builder`;
- T7d no mide edge, no crea SL/TP, no entrena IA y no opera MT5. Solo habilita
  materializar el corpus cuando produce setups completos reales.

## Orden causal de los componentes del setup (enmienda H6)

El Setup Builder compone un setup completo cuando POI, FVG, BOS y displacement
están publicados y causalmente disponibles en T. La cadena de anclaje mantiene
el orden estricto `t_POI <= t_REFINEMENT <= t_DECISION`.

BOS (confirmation) y displacement (trigger) son **evidencias hermanas** del
mismo POI: pueden publicarse en cualquier orden entre ellas. El displacement
puede preceder al BOS (crea la estructura y deja el FVG) o seguirlo (confirma
la ruptura); ambos son válidos. No se impone `BOS → displacement`. El
displacement no puede preceder al POI (`t_POI <= t_TRIGGER`): es una evidencia
del POI.

Esta enmienda alinea el Setup Builder con el DAG de hermanos del productor v3
y con el caso real del 2025-01-17 (displacement 15:15, BOS 15:30). Ver
`docs/experimentos/EXP_MTF_REPLAY_T7D_H6_ENMIENDA_PREREGISTRATION.md`.

## Frontera PIT estricta (enmienda PIT)

`tradable_time` es el timestamp de la vela de CONFIRMACIÓN del evento. La vela
de confirmación se observa exactamente en ese timestamp y es la vela que CREA
el objeto; por lo tanto NO se evalúa contra el propio objeto (auto-mitigación):
el FVG bull define `zone_low = third.low`, así que su tercera vela siempre toca
la zona; el OB se confirma con la vela de followthrough que recorre la zona del
source candle. La guarda PIT del lifecycle es estricta: solo velas con
`bar_time > tradable_time` transicionan el objeto. Toda vela posterior se
evalúa con normalidad. Ver
`docs/experimentos/EXP_MTF_REPLAY_T7D_CONFIRMATION_BAR_PREREGISTRATION.md`.
