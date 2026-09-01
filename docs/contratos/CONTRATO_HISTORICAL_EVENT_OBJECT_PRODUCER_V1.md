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
