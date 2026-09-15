# Dictamen — Failure Anatomy v1 materialization

**Fecha:** 2026-09-15  
**Estado:** `READY_FOR_TRAINING_REVIEW`  
**Linea:** `failure_anatomy_v1`  
**Contrato:** `docs/contratos/FAILURE_TAXONOMY_V1.md`  
**Politica:** `can_trade=false`, `shadow_mode=true`

## Objetivo

Materializar una matriz diagnostica para que Hermes aprenda riesgo de fallo
desde datos existentes e inmutables de `SEQ_CTX_01`.

La salida no es una senal de trading. Es un dataset de laboratorio para una red
futura `failure_risk_v1`.

## Artefactos esperados

```text
data/ml/tensorflow/failure_anatomy_v1/
  dataset_train.jsonl
  dataset_validation.jsonl
  dataset_test_oos.jsonl
  feature_schema.json
  split_manifest.json
  source_manifest.json
  failure_driver_manifest.json
  audit.json
  report.md
```

## Drivers

La taxonomia v1 habilita:

- `HTF_CONFLICT`
- `ADVERSE_CONTEXT`
- `IMMATURE_SEQUENCE`
- `CONSTRAINT_CONTRADICTION`
- `WEAK_STRUCTURE`
- `LOW_SUPPORT_REGIME`
- `DIRECTIONAL_AMBIGUITY`
- `UNKNOWN`

## Criterio

La materializacion queda lista para entrenamiento solo si:

```text
source_data_modified = false
features_use_future_outcomes = false
can_trade = false
splits = TRAIN / VALIDATION / TEST_OOS
```

## Resultado ejecutado

El materializador se ejecuto con:

```text
.venv\Scripts\python.exe scripts\lab\experiments\materialize_failure_anatomy_v1.py
```

Conteos generados:

| Split | Filas | Failure | Non-failure | Dataset hash |
| --- | ---: | ---: | ---: | --- |
| TRAIN | 120 | 25 | 95 | `f34cc94cb50be5652ede901ba18e9a9c519834b8717be0750906bb51cf708863` |
| VALIDATION | 96 | 19 | 77 | `58e7ea4cc88b772c5734bb77c6096aec6545f46bec6aa5fbd281c9d76604b3ad` |
| TEST_OOS | 76 | 26 | 50 | `68e6b1e7a1792d93c6fe49ba49fbf113589d54a3c15c5d4f02ba90b5e3d11695` |

Driver counts globales:

```text
ADVERSE_CONTEXT = 82
CONSTRAINT_CONTRADICTION = 132
DIRECTIONAL_AMBIGUITY = 277
HTF_CONFLICT = 174
LOW_SUPPORT_REGIME = 195
```

`IMMATURE_SEQUENCE`, `WEAK_STRUCTURE` y `UNKNOWN` no aparecen en esta
materializacion porque las filas disponibles tienen secuencias maduras con
`DISPLACEMENT` y `STRUCTURE`.

## Veredicto

```text
MATERIALIZATION = COMPLETED
STATUS = READY_FOR_TRAINING_REVIEW
SOURCE_DATA_MODIFIED = false
FEATURES_USE_FUTURE_OUTCOMES = false
MERGE_WITH_V1_003 = DEFERRED
CAN_TRADE = false
```

El entrenamiento queda como siguiente fase; no se ejecuta por este dictamen.
