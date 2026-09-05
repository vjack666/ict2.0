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
