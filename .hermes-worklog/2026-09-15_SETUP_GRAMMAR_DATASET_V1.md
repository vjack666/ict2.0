# Setup Grammar Dataset v1

**Fecha:** 2026-09-15
**Estado:** `BLOCKED_MISSING_REQUIRED_SETUP_EVIDENCE`
**Politica:** `can_trade=false`

## Objetivo

Comenzar el plan `SETUP_GRAMMAR_SUPERVISION_V1` materializando etiquetas
intermedias desde la tesis ICT local.

## Entrega

- Script: `scripts/lab/experiments/materialize_setup_grammar_dataset_v1.py`
- Reporte: `reports/audits/experiments/ai/setup_grammar_dataset_v1.md`
- JSON: `reports/audits/experiments/ai/setup_grammar_dataset_v1.json`
- Tests: `tests/test_setup_grammar_dataset.py`
- Datos locales ignorados por Git: `data/ml/tensorflow/setup_grammar_v1/`

## Conteos

- TRAIN: 120
- VALIDATION: 96
- TEST_OOS: 76
- Total: 292

## Diagnosticos

- `EXEC_TF_REPLAY_NOT_MATERIALIZED`: 292
- `PD_ARRAY_ZONE_NOT_MATERIALIZED`: 73

Por decision del usuario, no se acepta `UNKNOWN` ni huecos como clases
entrenables. Los faltantes bloquean el entrenamiento; no se fabrican como
verdad ni se pasan a `setup_quality_v1`.

## Verificacion

```text
python -m pytest tests/test_setup_grammar_dataset.py tests/test_ai_outcome_dataset.py tests/test_mechanical_signal_assessment.py
18 passed
```

## Correccion estricta posterior

Se actualizo el materializador para:

- reemplazar etiquetas `UNKNOWN_*` por `MISSING_*` o `*_INCOMPLETE_EVIDENCE`;
- emitir `training_eligible=false`;
- emitir `unknown_labels_accepted=false`;
- devolver `BLOCKED_MISSING_REQUIRED_SETUP_EVIDENCE` mientras falte replay de
  exec TF o PD Array/retest completo.

## Siguiente accion

Materializar primero replay de exec TF y zona PD Array/retest completa. No
entrenar `setup_quality_v1` mientras existan faltantes bloqueantes.
