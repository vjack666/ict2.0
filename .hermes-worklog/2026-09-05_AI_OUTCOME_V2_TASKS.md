# AI Outcome V2 — Task Breakdown (SDD tasks phase)

AGENTE: sdd-tasks executor
DEPARTAMENTO: D1 (PMO) / D3 (CAIO)
TAREA: Decompose `ai-outcome-v2` design §10 into dependency-ordered implementation tasks
STATUS: COMPLETED

## Resultado

Escrito `.hermes/plans/2026-09-05_AI_OUTCOME_V2_TASKS.md` con 9 tareas (T1–T9)
ordenadas por dependencia, TDD estricto (RED→GREEN), verification commands
(`python -m pytest` — `.venv` prohibido) y Forecast de carga de revisión:
~2,300–2,400 líneas estimadas, riesgo 400-line HIGH, `Chained PRs: No` (repo sin
push; se usan commit units locales CU-1…CU-9), `Decision needed before apply: Yes`.

- First safe batch (paralelo, write sets disjuntos): T1 (relajación
  `load_causal_jsonl` schema-versioned) ∥ T2 (registro `V2_FEATURE_PROFILES` +
  `_v2_features` + encoder tri-state + dispatch).
- Cadena posterior: T3 (adapter causal + frames pinning) → T4 (materializer) →
  T5 (wiring DIAGNOSTIC_ONLY) → T6 (test G6 mandatorio chain NULL) → T7
  (ablation A→F) → T8 (eval OOS) → T9 (gates G0–G13 + docs + worklog + commits
  locales, sin push).
- Respetadas las resoluciones R3: Option A schema-versioned, dispatch v2-first,
  `intraday_v2` nativo, registries separados, tri-state `is True/is False/is None`
  + guard `sum==1` secundario con `test_v2_tristate_null_survives_chain` como
  guarda autoritativa, frames fijados con sha256 y FULL-vs-PREFIX.

## Riesgos detectados

- `data/raw/EURUSD/EURUSD_M1.parquet` y `EURUSD_M5.parquet` aparecen MODIFICADOS
  en `git status` — el manifest de v2 debe fijar los bytes reales en disco y
  root-causear la desviación antes de emitir evidencia G7/G11.
- Posible reducción de filas del funnel de motor vs baseline 53,761; celdas con
  N<30 se reportan, no se fabrican.

## Verificación

- 9 tareas con acceptance criteria ligadas a test names del design §8 (G0–G13).
- No se implementó nada: fase de tareas solamente.

## Siguiente acción

Revisar Forecast (decisión de commit-unit plan antes de apply) → sdd-apply
empieza por el first batch T1 ∥ T2 (RED primero).