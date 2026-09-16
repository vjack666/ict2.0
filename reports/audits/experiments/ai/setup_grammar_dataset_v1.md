# Setup Grammar Dataset v1

**Fecha:** 2026-09-15
**Estado:** `BLOCKED_MISSING_REQUIRED_SETUP_EVIDENCE`
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

La materializacion queda bloqueada para entrenamiento estricto porque el usuario no acepta `UNKNOWN` ni huecos como clases entrenables. El corpus actual no trae replay de exec TF y no trae PD Array/retest completos para todas las filas. Eso queda como evidencia faltante, no como etiqueta aceptada.

## Artefactos

- `data\ml\tensorflow\setup_grammar_v1\dataset_test_oos.jsonl` sha256 `7aeb146e20ac55e7a74a9b43ef6eaea6721f354579b5519d83eac22d78518a0e`
- `data\ml\tensorflow\setup_grammar_v1\dataset_train.jsonl` sha256 `86532a92788d327a14cf28ca314a69102f8a40f32dc56d47145cf6ee5954c29d`
- `data\ml\tensorflow\setup_grammar_v1\dataset_validation.jsonl` sha256 `3fbca6ae92f50c9ea9624af2167baab658ee7520a5efaf8ce133d324336976f6`
- `data\ml\tensorflow\setup_grammar_v1\feature_schema.json` sha256 `98f2954a8397f08fc0da3d9a3b1d8d263e87beae4ce758cbde04652b6008f01e`

## Siguiente paso

Materializar primero replay de exec TF y zona PD Array/retest completa. No entrenar `setup_quality_v1` mientras existan faltantes bloqueantes.
