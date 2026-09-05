# V2 canonical extractor — 2026-09-05

## STATUS

`WORKING / BLOCKED_PROVENANCE_PENDING` — no training or promotion executed.

## TAREA

Replace the heuristic M15-only training path with a diagnostic extractor backed by
the canonical engine snapshot, including D1/H4/H1/M15/M5/M1 and explicit
abstention/trade safety fields.

## EVIDENCIA

- Two-day smoke: `data/materialized/v2/_smoke_engine_2d.jsonl`, 118 rows and 6
  rejected rows without a label horizon.
- All smoke rows have `schema_group=engine_v2`, six timeframe source hashes,
  `can_trade=false`, `shadow_mode=true`, `diagnostic_only=true`, and available
  M5/M1 confirmation fields.
- Focused tests: `3 passed` in `tests/test_v2_extractor_engine.py`.
- The three-month run was started over 2022-Q1 and interrupted after sustained
  CPU use because serializing the full canonical snapshot per M15 bar is too
  expensive for this turn; it produced no partial corpus.

## CAMBIOS

- Added `scripts/lab/experiments/v2_extractor_engine.py`.
- Added fail-closed and no-trade-level tests.

## RIESGOS / BLOQUEOS

- Source license, acquisition chain, and generator provenance are still
  unaudited; manifests therefore set `training_eligible=false`.
- Canonical lineage is unavailable in the current engine feed and is represented
  explicitly as unavailable; the legacy trainer must not consume this corpus.
- Full snapshot serialization needs a bounded projection or checkpointing before
  a quarter-scale run.

## SIGUIENTE ACCIÓN

Add a compact canonical snapshot projection and a provenance manifest, rerun the
bounded quarter, then audit reproducible predictions before considering training.

## Intento de entrenamiento

- Ejecutado una sola vez con el runner contractual sobre el corpus Q1.
- Resultado: `BLOCKED`; el corpus JSONL no es todavía un `DatasetSnapshot`
  certificado y no existe `research_gate` elegible.
- No se creó modelo, registro ni checkpoint; se conserva `can_trade=false`.

## Ruta diagnóstica solicitada sin certificación

- Se añadió `label_end_6` al extractor; el runner productivo sigue protegido.
- Se ejecutó una sola muestra diagnóstica balanceada de 600 filas (200 por clase),
  360/120/120 en split temporal, `DIAGNOSTIC_ONLY_COMPLETED`.
- Métricas: TRAIN accuracy 0.486, VALIDATION 0.208, TEST/OOS accuracy 0.0 y
  log-loss 1.651; el OOS quedó compuesto solo por `failure`, por lo que no es
  evidencia de edge ni promoción.
- Artefacto: `runtime/ai_learning/artifacts/v2_engine_2022_q1_diag_sample.json`.

## Resultado de corrida Q1

- Finalizada en 1530.2 s (~25.5 min), returncode=0.
- 6,162 filas, 6 rechazadas por no_label_window; 6,162 episode_id únicos.
- Distribución: continuation=2,861; reversal=3,018; failure=283.
- Hash de salida verificado contra el manifiesto; 287,050,261 bytes.
- training_eligible=false por procedencia pendiente; no se ejecutó entrenamiento.

## Comparación diagnóstica cronológica

- Corrida única sobre las primeras 2.000 filas cronológicas, split 1.200/400/400.
- OOS accuracy del modelo: 0.4975; baseline mayoritario OOS: 0.4975.
- Diferencia: 0.0000 (sin mejora); log-loss OOS 0.95117.
- No se invirtió ni maquilló el signo del resultado: cambiar etiquetas o métricas para forzar positividad invalidaría la auditoría.

## Corrección de mapeo V2

- El extractor ahora expone `direction`, `sequence_depth`, conteos de zonas
  anidados, `regime_stack`, `bos_htf` y proximidad causal para que el clasificador
  no reciba columnas silenciosamente vacías.
- Repetición diagnóstica cronológica con ese mapeo: OOS accuracy `0.4975`, igual
  al baseline; diferencia `0.0000`. No hubo mejora positiva verificable.

## Perfil combinado diagnóstico

- Se ejecutó una sola corrida con el perfil registrado
  `WYCKOFF_ICT_COMBINED`, sin cambiar el OOS ni las etiquetas.
- Accuracy OOS: `0.4975`, igual al baseline (diferencia `0.0000`).
- Log-loss OOS: `0.91562`, frente a `0.95117` del perfil anterior: mejora
  descriptiva de `0.03555`, aún sin evidencia de edge ni calibración.
- Artefacto: `runtime/ai_learning/artifacts/v2_engine_2022_q1_chrono2000_combined_diagnostic.json`.
