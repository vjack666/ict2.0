# Corrección de Materialización SETUP_GRAMMAR_DATASET_V1_FIXED

**Fecha:** 2026-09-16

## Resumen

Este documento describe la corrección de materialización aplicada al dataset `setup_grammar_v1`.

### Problema original

La función `pd_array_zone()` en el materializador original etiquetaba `USABLE_UNGRADED` si había FVG/OB en la secuencia de stages, sin evaluar:

1. Zona correcta del dealing range (discount para long, premium para short).
2. Alineación con sesgo HTF confirmado.
3. Respaldo institucional (displacement + FVG/OB en M15).

Esto producía 219 falsos positivos según la auditoría semántica.

### Corrección aplicada

Se reemplazó `pd_array_zone()` y `retest_entry()` para que usen el detector semántico `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1` y evalúen las tres condiciones POI antes de etiquetar `USABLE_UNGRADED`.

### Resultados

- **TRAIN** (120 filas):
  - `USABLE_UNGRADED`: 2
  - `NO_ZONE`: 118
- **VALIDATION** (96 filas):
  - `USABLE_UNGRADED`: 0
  - `NO_ZONE`: 96
- **TEST_OOS** (76 filas):
  - `USABLE_UNGRADED`: 4
  - `NO_ZONE`: 72

### Hash del dataset corregido

- `train.jsonl`: `62cf541d1fb8e1e2ed821663de87768b8f6b0189afe27d9dcfb2655faf39f7df`
- `validation.jsonl`: `e83c6ef08bcfff71d27f90c0239934a3365c22e03a6bb4dd47ae43b377934479`
- `test_oos.jsonl`: `f3b982ab7a791450d8c5422fdf9f595db1b37f9752709c98ddcc75f82e876cab`
- `feature_schema.json`: `e5d9ca857f688a2d50d8fa8dc6a1858bf389fad58f0306c7d9fe7f5acd030352`

### Estado

- **Status:** READY_FOR_SETUP_QUALITY_TRAINING_REVIEW
- **Git commit:** `401cf6bd444e664065b92b8cef07149ac57c0d81`

### Notas

- Este dataset corregido se genera en `data/ml/tensorflow/setup_grammar_v1_fixed/`.
- No reemplaza el dataset original ni el materializador existente.
- Se usa para comparar y, si pasa auditoría, para reentrenamiento de `setup_quality_v1`.
- `can_trade=false`, `entry_authorized=false` durante toda la ejecución.
- Sin conexión a MT5, sin trading real.
- El detector semántico usado es `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1` (semantic_pd_array_eval_v1), que ya pasó 6/6 casos de juguete.