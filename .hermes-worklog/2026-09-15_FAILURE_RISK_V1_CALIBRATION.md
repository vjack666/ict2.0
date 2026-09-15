# Worklog — failure_risk_v1 calibration v1

**Fecha:** 2026-09-15  
**Agente:** Codex  
**Departamento:** D3 CAIO / D5 Assurance  
**Estado:** COMPLETED_REVIEW  
**Modo:** LOCAL_ONLY  
**Politica:** `can_trade=false`

## Objetivo

Calibrar probabilidades del modelo `failure_risk_v1` sin reentrenar el modelo
base y sin usar `TEST_OOS` para ajustar decisiones.

## Reglas

- Ajustar calibradores solo con `VALIDATION`.
- Evaluar `TEST_OOS` solo al final.
- No modificar `model.keras`.
- No fusionar con `tf_outcome_v1_003`.
- No activar MT5, DEMO, paper ni trading.

## Artefactos esperados

- `scripts/lab/experiments/calibrate_failure_risk_v1.py`
- `data/ml/tensorflow/failure_risk_v1/calibration_v1.json`
- `reports/audits/experiments/ai/failure_risk_v1_calibration.md`
- `reports/audits/experiments/ai/failure_risk_v1_calibration_curve.png`

## Estado

Ejecutado.

## Resultado

Se ejecuto:

```text
.venv\Scripts\python.exe scripts\lab\experiments\calibrate_failure_risk_v1.py
```

Calibradores evaluados:

- `raw`
- `platt`
- `isotonic`
- `temperature`

Seleccion por VALIDATION:

```text
selected_calibrator = isotonic
selection_rule = minimum VALIDATION ECE, tie by Brier then log_loss
```

Resultado TEST_OOS seleccionado vs raw:

```text
delta_ECE = -0.0270
delta_Brier = -0.0032
delta_LogLoss = +0.2776
delta_failure_recall = -0.3462
delta_failure_f1 = -0.4091
```

## Dictamen

`isotonic` mejora calibracion ECE/Brier y ranking levemente, pero colapsa el
clasificador binario a threshold 0.5: failure recall cae a `0.0000`. Por eso el
estado queda `REVIEW_CALIBRATION_DIAGNOSTIC`, no PASS.

## Artefactos

- `scripts/lab/experiments/calibrate_failure_risk_v1.py`
- `data/ml/tensorflow/failure_risk_v1/calibration_v1.json`
- `reports/audits/experiments/ai/failure_risk_v1_calibration.md`
- `reports/audits/experiments/ai/failure_risk_v1_calibration_curve.png`

## Siguiente accion

No fusionar. Abrir una fase separada de thresholding/abstencion usando
VALIDATION o un holdout nuevo, nunca TEST_OOS para ajustar.
