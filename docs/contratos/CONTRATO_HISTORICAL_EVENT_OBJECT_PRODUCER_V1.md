# Contrato — Historical Event Object Producer v2

## Autoridades reutilizadas

- BOS: `engine.bos.structure.detect_market_structure`, columna causal `bos_dir`.
- Displacement: `detectors.displacement.detect_displacement`.
- POI/refinement: detectores canónicos OB H4 y FVG M15.

No se usa `bos_real` para crear eventos porque su quality score contiene una
etiqueta posterior. No se redefinen detectores dentro de backtest.

## Lineage y tiempo

DAG: `OB H4 → FVG M15`, `OB H4 → BOS M15` y
`BOS M15 → displacement M15`. El FVG puede publicarse antes, durante o
después del displacement; no se crea una referencia a un objeto futuro. Todos
los hijos conservan referencia al POI H4. Ventanas congeladas: POI→hijo 120 h
y BOS→displacement 24 h. Se elige el padre previo más reciente, ACTIVE en su
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
- T7c no mide edge, no crea SL/TP, no entrena IA y no opera MT5. Solo habilita
  materializar el corpus cuando produce setups completos reales.
