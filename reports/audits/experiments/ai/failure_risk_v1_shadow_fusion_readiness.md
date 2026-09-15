# Dictamen — failure_risk_v1 shadow fusion readiness

**Fecha:** 2026-09-15  
**Estado:** `READY_FOR_SHADOW_FUSION_REVIEW`  
**Base:** `FAILURE_RISK_THRESHOLD_V1`  
**Politica:** `can_trade=false`, `automatic_fusion_allowed=false`

## Resumen

El threshold diagnostico `platt >= 0.25` cumple los minimos definidos en
VALIDATION y no colapsa en TEST_OOS. Por eso `failure_risk_v1` queda habilitado
para una revision de fusion sombra, no para fusion automatica.

## Evidencia minima

| Split | Recall | Precision | F1 | Coverage |
| --- | ---: | ---: | ---: | ---: |
| VALIDATION | 0.5263 | 0.3846 | 0.4444 | 0.2708 |
| TEST_OOS | 0.3462 | 0.5000 | 0.4091 | 0.2368 |

## Interpretacion

La herramienta puede decir:

```text
Esta secuencia tiene riesgo diagnostico alto de fallo.
```

No puede decir:

```text
Opera.
Compra.
Vende.
Fusiona automaticamente.
```

## Condiciones para la siguiente fase

La revision de fusion sombra debe:

- mantener `can_trade=false`;
- no modificar `tf_outcome_v1_003`;
- no usar TEST_OOS para ajustar thresholds nuevos;
- comparar v1.003 solo vs v1.003 + estado de riesgo;
- emitir dictamen independiente antes de cualquier promocion de laboratorio.

## Veredicto

```text
READY_FOR_SHADOW_FUSION_REVIEW = true
AUTOMATIC_FUSION_ALLOWED = false
CAN_TRADE = false
```
