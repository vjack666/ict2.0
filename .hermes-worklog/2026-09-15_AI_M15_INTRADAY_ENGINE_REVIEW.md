# AI + M15 Intraday Engine Review

**Fecha:** 2026-09-15  
**Estado:** `REVIEW_READY_FOR_SHADOW_DATASET`  
**Autoridad:** local diagnostica, `can_trade=false`

## Objetivo

Continuar desde la fusion sombra IA y preparar el motor M15 para una linea de
aprendizaje intradia Londres-NY sin habilitar trading.

## Cambios

- `engine/mechanical_signal_assessment.py`
  - Agrega lectura de evidencia M15 booleana y rica `{present,time,source}`.
  - Mantiene fallos cerrados y codigos explicitos.
- `tests/test_mechanical_signal_assessment.py`
  - Cubre evidencia rica completa como `CANDIDATE_SETUP`.
  - Cubre retest rico ausente como `WAIT_RETEST`.
- `docs/contratos/AI_M15_SHADOW_CONFIRMATION_V1.md`
  - Congela frontera IA/motor: IA sombra, motor determinista, sin autoridad de trade.
- `reports/audits/experiments/ai_m15_intraday_engine_review.md`
  - Reporte tecnico y simple del avance.
- `reports/audits/experiments/ai_m15_intraday_engine_review.json`
  - Evidencia estructurada del dictamen.

## Verificacion

```text
python -m pytest tests/test_mechanical_signal_assessment.py
6 passed

python -m pytest tests/test_poi_stoch_evaluator.py tests/test_poi_stoch_evaluator_integration.py
106 passed
```

## Resultado

`PASS_BRIDGE_MECHANICS`: el evaluador mecanico acepta el formato rico del
ensamblador M15 sin romper compatibilidad con el formato booleano anterior.

`REVIEW_DATASET_REQUIRED`: falta materializar `M15_INTRADAY_SHADOW_DATASET_V1`
para medir si la IA mejora la seleccion de candidatos entre Londres y NY.

## Riesgos

- El snapshot operativo local existe, pero su `asof_time` observado es
  `2026-09-11T00:00:00+00:00`; no es prueba viva de setup actual.
- `CANDIDATE_SETUP` es diagnostico, no permiso de entrada.
- La fusion IA sigue en sombra y no modifica el motor.

## Siguiente accion

Construir `M15_INTRADAY_SHADOW_DATASET_V1`:

```text
decision_time -> M15 chain -> POI+Stoch status -> AI shadow scores -> outcome
```

Seleccionar thresholds en VALIDATION y evaluar TEST_OOS una sola vez.
