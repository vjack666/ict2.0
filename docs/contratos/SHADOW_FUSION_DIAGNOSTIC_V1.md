# SHADOW_FUSION_DIAGNOSTIC_V1

**Fecha:** 2026-09-15  
**Estado:** ACTIVO COMO DIAGNOSTICO SOMBRA DE LABORATORIO  
**Base:** `tf_outcome_v1_003` + `failure_risk_v1`  
**Politica:** `can_trade=false`, `automatic_fusion_allowed=false`

## 1. Proposito

Este contrato congela el primer diagnostico sombra combinado entre:

```text
tf_outcome_v1_003
failure_risk_v1
```

El objetivo es evaluar si el estado de riesgo de fallo ayuda al clasificador de
outcome a reconocer mejor `failure`.

## 2. Candidato aprobado

```text
design = failure_boost
risk_source = raw
threshold = 0.30
alpha = 0.15
```

Regla conceptual:

```text
si raw_failure_risk >= 0.30
entonces aumentar moderadamente la probabilidad de failure en tf_outcome_v1_003
```

## 3. Regla causal

El candidato fue seleccionado con `VALIDATION`.

`TEST_OOS` se uso una sola vez para dictamen final. No se uso TEST_OOS para
redisenar ni elegir candidatos.

## 4. Evidencia VALIDATION

| Modelo | Failure recall | Failure precision | Failure F1 | Macro F1 | LogLoss |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1.003 solo | 0.3684 | 0.3889 | 0.3784 | 0.6080 | 0.7756 |
| fusion sombra | 0.5263 | 0.4000 | 0.4545 | 0.6290 | 0.7948 |

## 5. Evidencia TEST_OOS

| Modelo | Failure recall | Failure precision | Failure F1 | Macro F1 | LogLoss |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1.003 solo | 0.2308 | 0.3000 | 0.2609 | 0.4981 | 1.0199 |
| fusion sombra | 0.2692 | 0.2917 | 0.2800 | 0.5054 | 1.0052 |

## 6. Veredicto

```text
SHADOW_FUSION_STATUS = PASS_SHADOW_FUSION_DIAGNOSTIC
AUTOMATIC_FUSION_ALLOWED = false
PRODUCTION_READY = false
CAN_TRADE = false
```

La mejora OOS es positiva pero modesta. Este contrato no declara edge, no
declara robustez productiva y no habilita trading.

## 7. Prohibiciones

Este contrato no autoriza:

- trading;
- DEMO;
- live signal;
- entrada, SL, TP o gestion de posiciones;
- produccion;
- cambio de `can_trade=false`;
- uso operativo sin auditoria independiente.

## 8. Siguiente fase permitida

La siguiente fase permitida es:

```text
AI_M15_SHADOW_CONFIRMATION_V1
```

Debe operar solo como confirmacion diagnostica de temporalidad menor, con
`can_trade=false`.
