# 2026-09-10 — SDD diagnostic training V2 completion

**Departamento:** D5 Assurance / D7 Delivery.
**Estado:** COMPLETED.

## Hechos completados

- Ejecutado `run_diagnostic_training()` con JSONL causal `v2_engine_2022_q1_current_train.jsonl` (6067 rows, target `label_end_6`).
- Entrenamiento completado con partición temporal 30 train + 10 validation + 10 test, cumpliendo MIN_PARTITION_ROWS (30/10/10) y min_class_rows=5 por clase.
- Clasificador multinomial softmax entrenado bajo autorización diagnóstico (`status=PASS, verdict=TRAINING_ELIGIBLE`) con `promotion_authorized=False` y `scientific_training_eligible=False` — sin promoción global.
- Fronteras de Shadow Mode mantenidas invariante: `can_trade=False`, `shadow_mode=True` en todo el pipeline (OutcomeClassifierArtifact, payload run_diagnostic_training, diagnostics diagnostics).
- Health de features validado: `validate_temporal_feature_health` pasó con `varying_fraction=0.8` (12 features variables de 15 totales).
- Artefacto serializable generado: `model_id=ICT_OUTCOME_CLASSIFIER_V1_DIAGNOSTIC`, `model_version=diagnostic-1.0.0`, `snapshot_id=DIAGNOSTIC_JSONL_88d08913ebde2c01`, `artifact_hash=c9e773cbbe3b5da502c84fe743e36311a6cfc5999096440af2a7c78fbc154875`.
- Engram memory persistente guardada (ID 760): `"Diagnostic training V2 engine current train JSONL"` — tipo decision, project ict2.0, review_after 2027-03-10.
- Reporte SDD completado: `docs/SDD_DIAGNOSTIC_TRAINING_V2_COMPLETED.md` — commit local 396e390.

## Métricas (Test OOS)

| Métrica | Resultado |
|---|---:|
| Accuracy | 0.482 |
| Log Loss | 0.831 |
| Class counts | continuation=588, failure=44, reversal=582 |
| Policy | SHADOW_ONLY_NO_ORDER |

## Riesgo y siguiente acción

El `verdict=TRAINING_ELIGIBLE` dentro de `diagnostic_authorization` es de alcance LOCAL/DIAGNOSTIC_ONLY y no promociona a certificación global. Gate B8 (TRAINING_ELIGIBLE) permanece PENDING según SDD_AI_OUTCOME_V2_T9_GATES.md — requiere auditoría independiente + autorización explícita de Ruben. No hacer `git push` durante cierre normal. Próximo: esperar autorización de gate B8 o levantar gates mecánicos (G1/G2) si hay acceso MT5 físico para testing demo.

## Archivos

- `docs/SDD_DIAGNOSTIC_TRAINING_V2_COMPLETED.md` — reporte SDD completado
- `runtime/ai_learning/diagnostic_training.py` — entry point ejecutado
- `data/materialized/v2/v2_engine_2022_q1_current_train.jsonl` — JSONL de entrada causal utilizada
- `docs/SDD_AI_OUTCOME_V2_T9_GATES.md` — referencia gates G0-G13 y gate B8