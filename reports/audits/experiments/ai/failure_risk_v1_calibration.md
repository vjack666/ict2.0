# Dictamen — failure_risk_v1 calibration v1

**Fecha:** 2026-09-15
**Estado:** `REVIEW_CALIBRATION_DIAGNOSTIC`
**Modelo fuente:** `failure_risk_v1`
**Calibrador seleccionado por VALIDATION:** `isotonic`
**Uso autorizado:** diagnostico de calibracion; no usar como clasificador binario a threshold 0.5
**Politica:** `can_trade=false`, `shadow_mode=true`, `merge_with_tf_outcome_v1_003=DEFERRED`

## Regla de calibracion

Los calibradores se ajustaron exclusivamente con `VALIDATION`. `TEST_OOS` se uso solo para evaluacion final.
No se modifico `model.keras`, no se reentreno el modelo y no se ajustaron thresholds usando OOS.

## VALIDATION

| Metodo | ECE | Brier | LogLoss | Recall | Precision | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| raw | 0.1535 | 0.1925 | 0.5597 | 0.4737 | 0.3600 | 0.4091 |
| platt | 0.0384 | 0.1504 | 0.4685 | 0.0000 | 0.0000 | 0.0000 |
| isotonic | 0.0000 | 0.1417 | 0.4340 | 0.1053 | 0.5000 | 0.1739 |
| temperature | 0.0386 | 0.1504 | 0.4685 | 0.0000 | 0.0000 | 0.0000 |

## TEST_OOS

| Metodo | ECE | Brier | LogLoss | Recall | Precision | F1 | ROC-AUC | PR-AUC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| raw | 0.1952 | 0.2443 | 0.6995 | 0.3462 | 0.5000 | 0.4091 | 0.6108 | 0.4122 |
| platt | 0.1712 | 0.2428 | 0.6976 | 0.0000 | 0.0000 | 0.0000 | 0.6108 | 0.4122 |
| isotonic | 0.1683 | 0.2411 | 0.9771 | 0.0000 | 0.0000 | 0.0000 | 0.6323 | 0.4273 |
| temperature | 0.1741 | 0.2427 | 0.6976 | 0.0000 | 0.0000 | 0.0000 | 0.6108 | 0.4122 |

## Veredicto

El calibrador `isotonic` fue seleccionado por VALIDATION. En TEST_OOS, frente a raw:

```text
delta_ECE = -0.0270
delta_Brier = -0.0032
delta_LogLoss = 0.2776
delta_failure_recall = -0.3462
delta_failure_f1 = -0.4091
```

Interpretacion:

- `isotonic` mejora ECE en TEST_OOS de `0.1952` a `0.1683`.
- `isotonic` mejora Brier en TEST_OOS de `0.2443` a `0.2411`.
- `isotonic` mejora ranking global levemente: ROC-AUC `0.6108` -> `0.6323`
  y PR-AUC `0.4122` -> `0.4273`.
- Pero a threshold fijo `0.5` colapsa la deteccion de failure: recall `0.3462`
  -> `0.0000`.
- LogLoss empeora materialmente: `0.6995` -> `0.9771`.

Por tanto, la calibracion queda en `REVIEW_CALIBRATION_DIAGNOSTIC`. No se
aprueba como clasificador binario, no se aprueba como input de fusion, no se
aprueba para `meta_calibrator_shadow` y no cambia ningun gate operativo.

## Decision

```text
CALIBRATION_STATUS = REVIEW_CALIBRATION_DIAGNOSTIC
BEST_VALIDATION_ECE = isotonic
OOS_BINARY_THRESHOLD_0_5 = FAIL_COLLAPSES_FAILURE_RECALL
FUSION_ELIGIBLE = false
CAN_TRADE = false
```

La siguiente iteracion no debe optimizar thresholds con TEST_OOS. Si se desea
usar probabilidades calibradas, hay que abrir una fase separada de thresholding
con VALIDATION o un holdout nuevo, y documentar cobertura/abstencion.

## Artefactos

- `data\ml\tensorflow\failure_risk_v1\calibration_v1.json`
- `reports\audits\experiments\ai\failure_risk_v1_calibration_curve.png`

## Confirmaciones

- `can_trade=false` intacto.
- No se activo MT5, DEMO, paper ni produccion.
- No se fusiono con `tf_outcome_v1_003`.
- `TEST_OOS` no se uso para seleccionar calibrador.
