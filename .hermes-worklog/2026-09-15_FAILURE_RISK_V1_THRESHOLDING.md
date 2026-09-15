# Worklog — failure_risk_v1 thresholding v1

**Fecha:** 2026-09-15  
**Agente:** Codex  
**Departamento:** D3 CAIO / D5 Assurance  
**Estado:** COMPLETED_PASS_DIAGNOSTIC  
**Modo:** LOCAL_ONLY  
**Politica:** `can_trade=false`

## Objetivo

Implementar el plan de thresholding y abstencion para `failure_risk_v1`, con
loop de rediseno controlado si falla.

## Reglas

- Elegir candidatos usando solo `VALIDATION`.
- Evaluar `TEST_OOS` una sola vez al final.
- Si falla TEST_OOS, no ajustar usando TEST_OOS.
- No fusionar con `tf_outcome_v1_003`.
- No activar MT5, DEMO, paper, live signal ni trading.

## Artefactos esperados

- `scripts/lab/experiments/evaluate_failure_risk_v1_thresholds.py`
- `data/ml/tensorflow/failure_risk_v1/thresholding_v1.json`
- `reports/audits/experiments/ai/failure_risk_v1_thresholding.md`
- `reports/audits/experiments/ai/failure_risk_v1_thresholding_curve.png`

## Estado

Ejecutado.

## Resultado

Se ejecuto:

```text
.venv\Scripts\python.exe scripts\lab\experiments\evaluate_failure_risk_v1_thresholds.py
```

El loop selecciono en VALIDATION:

```text
probability_source = platt
threshold = 0.25
design = binary_threshold
```

Metricas:

| Split | Recall | Precision | F1 | FPR | FNR | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| VALIDATION | 0.5263 | 0.3846 | 0.4444 | 0.2078 | 0.4737 | 0.2708 |
| TEST_OOS | 0.3462 | 0.5000 | 0.4091 | 0.1800 | 0.6538 | 0.2368 |

## Dictamen

```text
THRESHOLDING_STATUS = PASS_DIAGNOSTIC_THRESHOLD
SHADOW_FUSION_REVIEW_ELIGIBLE = true
AUTOMATIC_FUSION_ALLOWED = false
CAN_TRADE = false
```

## Artefactos

- `scripts/lab/experiments/evaluate_failure_risk_v1_thresholds.py`
- `data/ml/tensorflow/failure_risk_v1/thresholding_v1.json`
- `reports/audits/experiments/ai/failure_risk_v1_thresholding.md`
- `reports/audits/experiments/ai/failure_risk_v1_thresholding_curve.png`
- `docs/contratos/FAILURE_RISK_THRESHOLD_V1.md`
- `reports/audits/experiments/ai/failure_risk_v1_shadow_fusion_readiness.md`

## Siguiente accion

Abrir revision de fusion sombra. No ejecutar fusion automatica.
