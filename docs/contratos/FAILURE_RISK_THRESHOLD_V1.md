# FAILURE_RISK_THRESHOLD_V1

**Fecha:** 2026-09-15  
**Estado:** ACTIVO COMO DIAGNOSTICO DE LABORATORIO  
**Modelo:** `failure_risk_v1`  
**Fuente de probabilidad:** `platt`  
**Threshold:** `0.25`  
**Fit split:** `VALIDATION`  
**Evaluation split:** `TEST_OOS`  
**Politica:** `can_trade=false`, `shadow_mode=true`, `automatic_fusion_allowed=false`

## 1. Proposito

Este contrato congela el primer umbral diagnostico aprobado para
`failure_risk_v1`.

El umbral sirve para clasificar una secuencia como:

```text
HIGH_FAILURE_RISK si platt_probability >= 0.25
LOW_FAILURE_RISK  si platt_probability < 0.25
```

Su uso autorizado es exclusivamente diagnostico y de laboratorio.

## 2. Regla causal

El threshold fue seleccionado usando solo `VALIDATION`.

`TEST_OOS` se uso una sola vez para evaluacion final y no se uso para ajustar,
redisenar ni elegir el threshold.

## 3. Minimos exigidos

```text
VALIDATION recall >= 0.50
VALIDATION precision >= 0.30
VALIDATION F1 >= 0.38
TEST_OOS recall >= 0.30
TEST_OOS precision >= 0.30
TEST_OOS F1 >= 0.40
```

## 4. Resultado VALIDATION

```text
recall = 0.5263
precision = 0.3846
F1 = 0.4444
false_positive_rate = 0.2078
false_negative_rate = 0.4737
coverage = 0.2708
confusion_matrix = [[61, 16], [9, 10]]
```

## 5. Resultado TEST_OOS

```text
recall = 0.3462
precision = 0.5000
F1 = 0.4091
false_positive_rate = 0.1800
false_negative_rate = 0.6538
coverage = 0.2368
confusion_matrix = [[41, 9], [17, 9]]
```

## 6. Veredicto

```text
THRESHOLD_STATUS = PASS_DIAGNOSTIC_THRESHOLD
SHADOW_FUSION_REVIEW_ELIGIBLE = true
AUTOMATIC_FUSION_ALLOWED = false
PRODUCTION_READY = false
CAN_TRADE = false
```

El threshold cumple los minimos definidos, pero conserva limitaciones
materiales: muestra OOS pequena, recall OOS bajo/moderado, y dependencia de un
modelo base con sobreajuste documentado.

## 7. Prohibiciones

Este contrato no autoriza:

- trading;
- DEMO;
- live signal;
- entrada, SL, TP o gestion de posiciones;
- fusion automatica con `tf_outcome_v1_003`;
- `meta_calibrator_shadow` sin dictamen independiente;
- cambio de `can_trade=false`.

## 8. Siguiente fase permitida

La unica fase posterior permitida por este contrato es:

```text
SHADOW_FUSION_REVIEW
```

Esa fase debe comparar:

```text
tf_outcome_v1_003 solo
vs
tf_outcome_v1_003 + failure_risk_threshold_state
```

Siempre en modo sombra, sin trading y con `can_trade=false`.
