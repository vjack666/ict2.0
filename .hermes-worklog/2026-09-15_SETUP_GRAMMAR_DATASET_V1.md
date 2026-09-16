# Setup Grammar Dataset v1

**Fecha:** 2026-09-15  
**Estado:** `READY_FOR_SETUP_QUALITY_TRAINING_REVIEW`  
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

Estos faltantes no se fabricaron como verdad. Se conservaron como etiquetas
explicitas para que la red aprenda la diferencia entre evidencia presente y
evidencia aun no materializada.

## Verificacion

```text
python -m pytest tests/test_setup_grammar_dataset.py tests/test_ai_outcome_dataset.py tests/test_mechanical_signal_assessment.py
18 passed
```

## Siguiente accion

Revisar si se entrena `setup_quality_v1` con clases `UNKNOWN` /
`IMPLEMENTATION_REQUIRED` o si primero se materializa replay de exec TF y zona
PD Array/retest completa.
