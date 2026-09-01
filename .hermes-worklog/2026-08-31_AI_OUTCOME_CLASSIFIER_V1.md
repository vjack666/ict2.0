# Bitácora — IA de outcomes ICT v1

**Fecha:** 2026-08-31
**AGENTE:** Codex
**DEPARTAMENTO:** D3 IA, con D4 Datos, D5 Assurance y D1 Documentación
**TAREA:** Construir la primera capa de aprendizaje IA posterior al Funnel:
clasificar `continuation`, `reversal` y `failure` con trazabilidad, sin
convertir el resultado en edge, señal u orden.

## STATUS

**COMPLETED técnico / BLOCKED científico para entrenamiento real**

## EVIDENCIA

- Se reutiliza `TrainingPipeline` INF-4 para snapshot certificado, lineage y
  split temporal TRAIN/VALIDATION/TEST.
- Se implementó un baseline multinomial softmax determinista, con semilla fija
  y normalización aprendida exclusivamente en TRAIN.
- El artefacto registra snapshot, dataset hash, schema hash, commit de código,
  experimento, features, clases, semilla y métricas OOS.
- La inferencia expone lineage y pasa por INF-7; siempre devuelve
  `shadow_mode=true` y `can_trade=false`.
- El entrenador bloquea si no recibe `status=PASS` y
  `verdict=TRAINING_ELIGIBLE`, si el hash no coincide, si faltan filas o si
  alguna clase no tiene soporte mínimo.
- Verificación local: `402 passed`, compilación Python y `git diff --check`.
- No se entrenó con `data/raw/*.parquet`, no se mezclaron los planos Dukascopy
  y MT5, no se emitieron órdenes y no se hizo push.

## ARCHIVOS

- `runtime/ai_learning/outcome_classifier.py`
- `runtime/ai_learning/__init__.py`
- `tests/test_ai_learning_outcome_classifier.py`
- `docs/contratos/CONTRATO_AI_OUTCOME_CLASSIFIER_V1.md`
- `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md`
- `.hermes/plans/2026-08-31_AI_OUTCOME_CLASSIFIER_V1.md`
- `.hermes-index.md`

## RIESGOS Y LIMITACIONES

1. El experimento vigente `EXP-SEQ-CTX-01` tiene veredicto
   `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`; por tanto no autoriza
   `TRAINING_ELIGIBLE`.
2. El baseline todavía no está calibrado con INF-6 ni validado en dominio/drift
   con INF-8 sobre un modelo real.
3. La inferencia Shadow sobre MT5 queda pendiente de un artefacto entrenado y
   congelado con evidencia científica.

## SIGUIENTE ACCIÓN

Diseñar y pre-registrar un nuevo dataset de investigación con objetivo,
horizonte, población y potencia OOS suficientes; certificarlo de forma
independiente y recién entonces ejecutar el entrenamiento. Mantener MT5 como
plano operativo separado para la futura observación Shadow.
