# Dictamen — Shadow Fusion Review v1

**Fecha:** 2026-09-15
**Estado:** `PASS_SHADOW_FUSION_DIAGNOSTIC`
**Politica:** `can_trade=false`, `automatic_fusion_allowed=false`

## Regla del loop

Los candidatos de fusion se seleccionan solo con `VALIDATION`. `TEST_OOS` se usa una sola vez para dictamen final. Si TEST_OOS falla, no se redisenia mirando OOS.

## Candidato seleccionado

```json
{
  "loop_iteration": 1,
  "design": "failure_boost",
  "risk_source": "raw",
  "alpha": 0.15,
  "threshold": 0.3,
  "multiplier": 1.0
}
```

| Split | Modelo | Failure recall | Failure precision | Failure F1 | Macro F1 | LogLoss |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| VALIDATION | v1.003 solo | 0.3684 | 0.3889 | 0.3784 | 0.6080 | 0.7756 |
| VALIDATION | fusion sombra | 0.5263 | 0.4000 | 0.4545 | 0.6290 | 0.7948 |
| TEST_OOS | v1.003 solo | 0.2308 | 0.3000 | 0.2609 | 0.4981 | 1.0199 |
| TEST_OOS | fusion sombra | 0.2692 | 0.2917 | 0.2800 | 0.5054 | 1.0052 |

## Veredicto

La fusion sombra cumple minimos de VALIDATION y sostiene beneficio diagnostico en TEST_OOS. Queda como diagnostico shadow, no operativo.

## Artefactos

- `data\ml\tensorflow\failure_risk_v1\shadow_fusion_v1.json`
- `reports\audits\experiments\ai\failure_risk_v1_shadow_fusion_review.png`

## Confirmaciones

- `can_trade=false` intacto.
- No se activo MT5, DEMO, paper ni produccion.
- No se cambio `tf_outcome_v1_003`.
- `TEST_OOS` no se uso para seleccionar candidatos.
