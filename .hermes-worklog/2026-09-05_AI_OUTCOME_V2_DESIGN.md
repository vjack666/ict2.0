# Worklog — 2026-09-05 AI_OUTCOME_V2_DESIGN

- **AGENTE**: sdd-design (executor) — big-pickle
- **DEPARTAMENTO**: CAIO / IA (capa 3) + laboratorio (research) — diseño técnico
- **TAREA**: Diseño técnico de `ai-outcome-v2` (retrain del Outcome Classifier sobre el funnel canónico del motor, con variables de engine nuevas)
- **STATUS**: COMPLETED
- **EVIDENCIA**:
  - `.hermes/plans/2026-09-05_AI_OUTCOME_V2_DESIGN.md` (artefacto de diseño)
  - Revisados: proposal, spec, `runtime/ai_learning/outcome_classifier.py`, `training_pipeline.py`, `diagnostic_training.py`, `engine/episodes.py`, `engine/mtf_navigation.py`, `engine/setup_builder.py`, `engine/market_object.py`, `engine/mt5_operational_snapshot.py`, `engine/bos/structure.py`, materializadores v1 (`ai_outcome_dataset.py`, `ai_outcome_batch_materializer.py`, `ai_outcome_funnel_bridge.py`), baseline `wyckoff_intraday_diagnostic_train.py`, tests `test_ai_outcome_*` y `test_ai_learning_outcome_classifier.py`
- **ARCHIVOS**:
  - Nuevo: `scripts/lab/experiments/ai_outcome_v2_adapter.py` (diseñado)
  - Nuevo: `scripts/lab/experiments/ai_outcome_v2_dataset.py` (diseñado)
  - Nuevo: `scripts/lab/experiments/ai_outcome_v2_ablation.py` (diseñado)
  - Nuevo: `scripts/lab/experiments/ai_outcome_v2_eval.py` (diseñado)
  - Modificado (aditivo): `runtime/ai_learning/outcome_classifier.py` (registry v2 + dispatch), `runtime/ai_learning/diagnostic_training.py` (acepta tuplas v2)
  - Tests nuevos: `tests/test_ai_outcome_v2_{tristate,causality,schema,repro,adapter}.py` + adiciones al test del clasificador
- **RIESGOS**:
  - Crecimiento de dimensiones (A→F ~70+ one-hot sobre 48 baseline) con N por segmento reducido por el funnel estricto.
  - Reducción de filas del funnel frente a baseline 53,761 (aceptado: calidad sobre cantidad; celdas N<30 se reportan, no se inventan).
  - Provenance: el adapter recomputa context-state causalmente; debe ligar `funnel_checksum` + hashes de frames para G0/G7/G11 auditable.
  - Regresión tri-state: cualquier reintroducción de `bool(None)->False` rompería G6; mitigado por test obligatorio + guard `sum==1` en el trainer.
- **SIGUIENTE ACCIÓN**: sdd-tasks descomponga los pasos de §10 (orden de ejecución) en tareas implementables. No ejecutar código — diseño únicamente.

## Actualización — R3 reliability audit (APPROVE_WITH_FIXES)

La auditoría independiente devolvió **APPROVE_WITH_FIXES** (2 CRITICAL + 3 WARNING). El contenido se acepta; se corrigieron los 5 hallazgos en el diseño (`2026-09-05_AI_OUTCOME_V2_DESIGN.md`), se actualizó el worklog y se persistió a Engram (#715, mismo topic `sdd/ai-outcome-v2/design`):

- **F1 CRITICAL** — v2 rows deben pasar `load_causal_jsonl`. Resuelto **Option A**: relajación schema-versionada (`schema_group="engine_v2"`), v1 intacto, patch exacto + test en §4.1.
- **F2 CRITICAL** — V2_A computable desde payload v2. Resuelto: dispatch v2-first a `_v2_features` para TODOS los tuplas v2 + bloque de origen `intraday_v2` + test de paridad en §5.3.
- **F3 WARNING** — Claim `sum==1` anti-collapse era FALSO (`None->False` suma 1 y pasa). Corregido en §3.3: el `sum==1` solo es invariant de well-formedness; el guard REAL es el test funcional `test_v2_tristate_null_survives_chain` (mandatorio, G6).
- **F4 WARNING** — Encoding flat no especificado. Tabla columna→source-path→regla para TODAS las columnas A–F en §5.4, con comparaciones explícitas `is True/is False/is None`.
- **F5 WARNING** — Frames sin pin. Resuelto en §5.5: frames canónicos `data/raw/EURUSD/EURUSD_{M1,M5,M15,H1,H4,D1}.parquet` vía `engine.data_feed.load_frames`, sha256 streaming (`_source_artifacts`), FULL-vs-PREFIX (`_frame_prefix`), sin MT5.

`STATUS`: COMPLETED (con fixes de auditoría). `ARCHIVOS` añadidos al diseño: §4.1, §5.3, §5.4, §5.5, sección Auditoría; fila de `diagnostic_training.py` ampliada; 2 tests nuevos añadidos al plan de tests (§8).
