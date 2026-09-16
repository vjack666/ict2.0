# Setup Quality v1 Training

**Fecha:** 2026-09-16
**Estado:** `REVIEW`
**Politica:** `can_trade=false`, `shadow_mode=true`

## Objetivo

Continuar el loop solicitado por el usuario: no aceptar `UNKNOWN`, materializar
la evidencia faltante y entrenar una primera red que aprenda la gramatica del
setup desde la tesis local.

## Cambios

- `SETUP_GRAMMAR_DATASET_V1` ya no trata `NO_ZONE` como hueco desconocido.
- `NO_ZONE` queda como clase negativa confirmada.
- Se agrega ventana M15 OHLC causal cerrada para `exec_tf_integrity`.
- Se agregan fuentes locales M15 parquet y CSV mensual para cubrir TRAIN,
  VALIDATION y TEST_OOS.
- `setup_quality_v1` se entrena con TensorFlow 2.21.0 en `.venv-tf311`.

## Artefactos

- `scripts/lab/experiments/train_setup_quality_v1.py`
- `reports/audits/experiments/ai/setup_quality_v1_training.md`
- `reports/audits/experiments/ai/setup_quality_v1_training.json`
- `data/ml/tensorflow/setup_quality_v1/model.keras` (local, ignorado)
- `data/ml/tensorflow/setup_quality_v1/training_record.json` (local, ignorado)
- `data/ml/tensorflow/setup_quality_v1/predictions.json` (local, ignorado)

## Metricas

- VALIDATION setup_decision accuracy: `0.9167`
- VALIDATION weak_link accuracy: `0.8854`
- TEST_OOS setup_decision accuracy: `0.8421`
- TEST_OOS weak_link accuracy: `0.8684`
- TEST_OOS failure_risk balanced_accuracy: `0.4992`

## Verificacion

```powershell
python -m pytest tests/test_setup_grammar_dataset.py tests/test_ai_outcome_dataset.py tests/test_mechanical_signal_assessment.py
```

Resultado: `18 passed`.

## Dictamen

`setup_quality_v1` aprendio a clasificar construccion de setup y eslabon debil
con senal util en OOS, pero la cabeza `failure_risk` sigue debil. Estado
`REVIEW`; no se fusiona con el motor ni se habilita trading.

## Siguiente accion

Usar `setup_quality_v1` solo en shadow diagnostics y evaluar fusion tardia con
`failure_risk_v1` en funnel/backtest diagnostico. Si falla en OOS economico, el
loop debe redisenar features M15 semanticas y reentrenar.
