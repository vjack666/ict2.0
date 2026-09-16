# Setup Grammar Dataset v1

**Fecha:** 2026-09-15
**Estado:** `READY_FOR_SETUP_QUALITY_TRAINING_REVIEW`
**Trading:** `can_trade=false`

## Que se materializo

Se convirtio la tesis ICT en etiquetas intermedias para que la red aprenda la construccion del setup, no solo el outcome final.

## Conteos

- Total filas: `292`
- TEST_OOS: `76`
- TRAIN: `120`
- VALIDATION: `96`

## Diagnosticos importantes

- `EXEC_TF_REPLAY_NOT_MATERIALIZED`: `292`
- `PD_ARRAY_ZONE_NOT_MATERIALIZED`: `73`

## Lectura honesta

La materializacion queda lista para revisar entrenamiento de `setup_quality_v1`, pero muestra los huecos esperados: el corpus actual no trae replay de exec TF ni PD Array/retest completos para todas las filas. Eso queda etiquetado, no inventado.

## Artefactos

- `data\ml\tensorflow\setup_grammar_v1\dataset_test_oos.jsonl` sha256 `80f6cfb443ead77d20e224a8185c3bb9ca83c5679d1af423bc47a20ed2cdd0a9`
- `data\ml\tensorflow\setup_grammar_v1\dataset_train.jsonl` sha256 `8836411f2ac52b4702186c68b607fbc4adcac6d9b01668fdfea6cee6e51cf727`
- `data\ml\tensorflow\setup_grammar_v1\dataset_validation.jsonl` sha256 `71b330b8ae15f62ca39659696a9dfd055fb8db17e937288f91eebf06e6f9f9c9`
- `data\ml\tensorflow\setup_grammar_v1\feature_schema.json` sha256 `98f2954a8397f08fc0da3d9a3b1d8d263e87beae4ce758cbde04652b6008f01e`

## Siguiente paso

Entrenar una primera red `setup_quality_v1` solo si se acepta que las etiquetas faltantes sean clases explicitas (`UNKNOWN` / `IMPLEMENTATION_REQUIRED`) y no verdades inventadas.
