# Dictamen — failure_risk_v1 thresholding v1

**Fecha:** 2026-09-15
**Estado:** `PASS_DIAGNOSTIC_THRESHOLD`
**Politica:** `can_trade=false`, `shadow_mode=true`, `merge_with_tf_outcome_v1_003=DEFERRED`

## Regla del loop

El loop puede redisenar candidatos usando solo `VALIDATION`. `TEST_OOS` se usa una sola vez para evaluacion final del candidato seleccionado. Si TEST_OOS falla, no se ajusta el umbral mirando OOS.

## Minimos

```text
VALIDATION recall >= 0.5
VALIDATION precision >= 0.3
VALIDATION F1 >= 0.38
TEST_OOS recall >= 0.3
TEST_OOS precision >= 0.3
TEST_OOS F1 >= 0.4
```

## Candidato seleccionado en VALIDATION

```json
{
  "loop_iteration": 3,
  "design": "binary_threshold",
  "probability_source": "platt",
  "threshold": 0.25,
  "low_threshold": null,
  "high_threshold": null
}
```

| Split | Recall | Precision | F1 | FPR | FNR | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| VALIDATION | 0.5263 | 0.3846 | 0.4444 | 0.2078 | 0.4737 | 0.2708 |
| TEST_OOS | 0.3462 | 0.5000 | 0.4091 | 0.1800 | 0.6538 | 0.2368 |

## Veredicto

El candidato cumple los minimos de VALIDATION y no colapsa en TEST_OOS. Queda aprobado solo como umbral diagnostico de laboratorio.

No autoriza trading ni fusion automatica. El siguiente paso es congelar contrato `FAILURE_RISK_THRESHOLD_V1` y abrir revision de fusion sombra.

## Artefactos

- `data\ml\tensorflow\failure_risk_v1\thresholding_v1.json`
- `reports\audits\experiments\ai\failure_risk_v1_thresholding_curve.png`

## Confirmaciones

- `can_trade=false` intacto.
- No se activo MT5, DEMO, paper ni produccion.
- No se fusiono con `tf_outcome_v1_003`.
- `TEST_OOS` no se uso para seleccionar ni redisenar umbrales.
