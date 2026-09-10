# SDD Phase: sdd-verify diagnostic-training-v2

**Status:** COMPLETED

**Executive Summary:** Ejecutado exitosamente `run_diagnostic_training()` con JSONL causal `v2_engine_2022_q1_current_train.jsonl` (6067 rows, target `label_end_6`). Entrenamiento completado con partición temporal 30 train + 10 validation + 10 test cumpliendo mínimos de partición (MIN_PARTITION_ROWS). Clasificador multinomial softmax entrenado bajo autorización diagnóstico (status=PASS, verdict=TRAINING_ELIGIBLE) manteniendo `can_trade=False` y `shadow_mode=True` de manera invariante. No se promovió a TRAINING_ELIGIBLE global — `promotion_authorized=False` y `scientific_training_eligible=False` persistentes. Meta-artefacto serializable generado con weights, bias, mean, scale, metrics y hashes verificables.

**Artifacts:**
- `runtime/ai_learning/diagnostic_training.py` — `run_diagnostic_training()` entry point ejecutado; validó schema JSONL, particiones temporales, health de features, construcción de split
- `data/materialized/v2/v2_engine_2022_q1_current_train.jsonl` — JSONL de entrada causal con 6067 rows, `can_trade=False` en todas las filas, `sequence_depth` variado (1-8), `label_end_6` distribuido (continuation: 2829, reversal: 2959, failure: 279)
- Artefacto de modelo entrenado con `OutcomeClassifierArtifact`: `model_id=ICT_OUTCOME_CLASSIFIER_V1_DIAGNOSTIC`, `model_version=diagnostic-1.0.0`, `snapshot_id=DIAGNOSTIC_JSONL_88d08913ebde2c01`, `dataset_hash=88d08913ebde2c01b2c9dbd3108d7505dd5b7342ecd7ab0b7c4184cb03a24e83`, `artifact_hash=c9e773cbbe3b5da502c84fe743e36311a6cfc5999096440af2a7c78fbc154875`
- Engram memory observation ID 760: `"Diagnostic training V2 engine current train JSONL"` (type: decision, project: ict2.0)
- `docs/SDD_DIAGNOSTIC_TRAINING_V2_COMPLETED.md` — este reporte

**Metrics (Test OOS):**
- Accuracy: 0.482
- Log Loss: 0.831
- Class counts: continuation=588, failure=44, reversal=582
- Policy: SHADOW_ONLY_NO_ORDER (sin órdenes de trading)

**Next Recommended:**
1. **No promocionar a TRAINING_ELIGIBLE** sin autorización de gate B8: requiere auditoría independiente + autorización explícita de Ruben (según SDD_AI_OUTCOME_V2_T9_GATES.md línea 105-113)
2. El `diagnostic_authorization.verdict=TRAINING_ELIGIBLE` es de alcance LOCAL/DIAGNOSTIC_ONLY solamente — no convierte la fuente en certificada
3. Considerar levantar gates del bot mecánico (G1 execution_enabled, G2 snapshot canonical) si hay acceso a MT5 física para testing en demo
4. Persistir learned conventions en Engram con topic_key `decision/diagnostic-training-v2-engine-current-train-jsonl` para sesiones futuras

**Risks:**
- ⚠️ Riesgo de promoción accidental: el `verdict=TRAINING_ELIGIBLE` dentro de `diagnostic_authorization` NO es promoción global. El `promotion_authorized=False` y `scientific_training_eligible=False` son barreras invariantes. Cualquier intento de tratar esto como certificado viola GEN-000 y gates científicos.
- ⚠️ Data drift: JSONL de 2022 Q1 puede no representar condiciones de mercado actuales — validar antes de cualquier re-entrenamiento
- ⚠️ `sequence_depth` health: guard `validate_temporal_feature_health` detectó y rechazó datos con `sequence_depth` todos None/zero — confirma guard funcionando como diseñado

**Skill Resolution:**
- `run_diagnostic_training()` — función entry point para diagnóstico onboard, valida JSONL, split temporal, health features, llama `train_outcome_classifier()` con `research_gate` autorización local
- `outcome_classifier.py` `train_outcome_classifier()` — entrena baseline softmax determinista con `research_gate`(status=PASS, verdict=TRAINING_ELIGIBLE) pero artefacto final conserv `shadow_mode=True, can_trade=False`
- `feature_health.py` `validate_temporal_feature_health()` — guard crítico que rechazó JSONL con `sequence_depth` todos None/zero; validó el `v2_engine_2022_q1_current_train.jsonl` con `varying_fraction=0.8`
- `engram_mem_save()` — persistencia de decisión y hallazgos en memoria persistente across sessions
- `SDD_AI_OUTCOME_V2_T9_GATES.md` — referencia de gates G0-G13 y gate B8 PENDING (TRAINING_ELIGIBLE)

**Commit Local (pending):**
- Documentar este resultado en worklog `.hermes-worklog/`
- Commit local selectivo con mensaje convencional
- No hacer `git push` (prohibido durante cierre normal sin auditoría independiente)