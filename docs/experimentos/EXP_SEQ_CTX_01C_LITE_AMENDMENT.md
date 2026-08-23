# EXP-SEQ-CTX-01C — enmienda exploratoria `structure_mode=lite`

**Estado:** preregistrado como exploración secundaria; no confirmatorio
**Antecedente:** EXP-SEQ-CTX-01B no amplió la muestra porque el stage
`STRUCTURE` solo aparece a partir de profundidad 4 en `run_sequential`.

## Protocolo congelado antes de la corrida

- usar `engine.sequential_events.run_sequential` con `structure_mode=lite`;
- mantener `min_depth=4`, la misma deduplicación por `structure_bar` y los mismos
  buckets, horizontes y snapshot Dukascopy 20Y;
- mantener gates causal FULL-vs-PREFIX y TNA behavioral/full-span en `PASS`;
- usar los mismos bloques DESIGN 2006–2015, VALIDATION 2016–2020 y HOLDOUT
  2021–2025, excluyendo outcomes que crucen cada límite;
- no cambiar umbrales, contexto, outcome, deduplicación ni horizonte después de
  ver resultados;
- no convertir la exploración en edge, señal, entrenamiento IA o autorización de
  backtest.

La variante `lite` cambia el detector de estructura y, por tanto, no puede
combinarse con el resultado `canonical_bos` ni presentarse como confirmación.
Si no alcanza `n>=30` en `ALIGNED` y `AGAINST`, el estado permanece
`INSUFFICIENT_N`. Si lo alcanza, el resultado solo es `PASS_SAMPLE_SUFFICIENT`
descriptivo: no es inferencia causal ni edge.

## Artefacto

`reports/audits/experiments/seq_ctx_01c_lite_oos/report.json` y `report.md`.
