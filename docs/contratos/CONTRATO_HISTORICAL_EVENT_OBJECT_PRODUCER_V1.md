# Contrato — Historical Event Object Producer v1

## Autoridades reutilizadas

- BOS: `engine.bos.structure.detect_market_structure`, columna causal `bos_dir`.
- Displacement: `detectors.displacement.detect_displacement`.
- POI/refinement: detectores canónicos OB H4 y FVG M15.

No se usa `bos_real` para crear eventos porque su quality score contiene una
etiqueta posterior. No se redefinen detectores dentro de backtest.

## Lineage y tiempo

Cadena: `OB H4 → FVG M15 → BOS H4 → displacement M15`. Cada hijo solo puede
referenciar padres ya publicados. Los padres nunca reciben referencias a hijos
futuros. Ventanas congeladas de composición: 120 h, 72 h y 24 h respectivamente.
Se elige el padre previo más reciente compatible en dirección y geometría.

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
- T7b no mide edge, no crea SL/TP, no entrena IA y no opera MT5.
