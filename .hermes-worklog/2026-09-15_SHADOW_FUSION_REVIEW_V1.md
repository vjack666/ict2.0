# Worklog — Shadow Fusion Review v1

**Fecha:** 2026-09-15  
**Agente:** Codex  
**Departamento:** D3 CAIO / D5 Assurance  
**Estado:** COMPLETED_PASS_DIAGNOSTIC  
**Modo:** LOCAL_ONLY  
**Politica:** `can_trade=false`

## Objetivo

Comparar `tf_outcome_v1_003` solo contra `tf_outcome_v1_003` combinado con
`failure_risk_v1` en modo sombra.

## Reglas

- Seleccionar candidatos solo con `VALIDATION`.
- Evaluar `TEST_OOS` una sola vez al final.
- Si falla TEST_OOS, no redisenar usando TEST_OOS.
- No modificar modelos base.
- No activar trading, MT5, DEMO, paper ni produccion.

## Artefactos esperados

- `scripts/lab/experiments/evaluate_shadow_fusion_v1.py`
- `data/ml/tensorflow/failure_risk_v1/shadow_fusion_v1.json`
- `reports/audits/experiments/ai/failure_risk_v1_shadow_fusion_review.md`
- `reports/audits/experiments/ai/failure_risk_v1_shadow_fusion_review.png`

## Estado

Ejecutado.

## Resultado

Se ejecuto:

```text
.venv\Scripts\python.exe scripts\lab\experiments\evaluate_shadow_fusion_v1.py
```

Candidato seleccionado en VALIDATION:

```text
design = failure_boost
risk_source = raw
threshold = 0.30
alpha = 0.15
```

VALIDATION:

| Modelo | Failure recall | Failure precision | Failure F1 | Macro F1 | LogLoss |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1.003 solo | 0.3684 | 0.3889 | 0.3784 | 0.6080 | 0.7756 |
| fusion sombra | 0.5263 | 0.4000 | 0.4545 | 0.6290 | 0.7948 |

TEST_OOS:

| Modelo | Failure recall | Failure precision | Failure F1 | Macro F1 | LogLoss |
| --- | ---: | ---: | ---: | ---: | ---: |
| v1.003 solo | 0.2308 | 0.3000 | 0.2609 | 0.4981 | 1.0199 |
| fusion sombra | 0.2692 | 0.2917 | 0.2800 | 0.5054 | 1.0052 |

## Dictamen

```text
SHADOW_FUSION_STATUS = PASS_SHADOW_FUSION_DIAGNOSTIC
AUTOMATIC_FUSION_ALLOWED = false
CAN_TRADE = false
```

La mejora en TEST_OOS es real pero modesta. Queda aprobada solo como
diagnostico sombra de laboratorio.

## Artefactos

- `scripts/lab/experiments/evaluate_shadow_fusion_v1.py`
- `data/ml/tensorflow/failure_risk_v1/shadow_fusion_v1.json`
- `reports/audits/experiments/ai/failure_risk_v1_shadow_fusion_review.md`
- `reports/audits/experiments/ai/failure_risk_v1_shadow_fusion_review.png`
- `docs/contratos/SHADOW_FUSION_DIAGNOSTIC_V1.md`

## Siguiente accion

Abrir `AI_M15_SHADOW_CONFIRMATION_V1`, solo como confirmacion diagnostica,
sin trading.
