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


## Lectura honesta

La materializacion usa ventanas M15 cerradas para eliminar `UNKNOWN` como clase entrenable. `NO_ZONE` queda como clase negativa valida; solo se bloquea si falta fuente M15, split o causalidad.

## Artefactos

- `data\ml\tensorflow\setup_grammar_v1\dataset_test_oos.jsonl` sha256 `2ab1c4529ad3ab37c7903579a3146156a5c50c4d2531bcbb515a79d03c56b008`
- `data\ml\tensorflow\setup_grammar_v1\dataset_train.jsonl` sha256 `8efea9fc81d4a12c62d7565f0b26b77ce392a84107519ca6afdef60538e505f3`
- `data\ml\tensorflow\setup_grammar_v1\dataset_validation.jsonl` sha256 `1b928aa7b7e3ea15c7c39c238f06dcc542cb622523aac6d277fb345a5154018d`
- `data\ml\tensorflow\setup_grammar_v1\feature_schema.json` sha256 `0c4dfe5d15f09dc603deece89ba409707f4fecfa8f090d05b2bb9392ea8dc5cf`

## Siguiente paso

Revisar si los faltantes bloqueantes bajaron a cero. Solo entonces entrenar `setup_quality_v1`; si quedan faltantes, ampliar la ventana/ensamblador causal y repetir.
