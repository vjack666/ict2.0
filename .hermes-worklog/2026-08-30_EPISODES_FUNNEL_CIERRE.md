# Bitácora — Cierre Episodes / Funnel causal v1 (revisión de certificación)

**Fecha:** 2026-08-30 (revisión post-dictamen Ruben)
**Agente:** Hermes (director de D2) con revisión D5 independiente
**Departamentos:** D1 Documentación, D2 Ingeniería, D5 Assurance, D7 Delivery
**Estado:** `READY_FOR_INDEPENDENT_AUDIT` — las 7 fallas del dictamen fueron corregidas y reverificadas. Commit local, **sin push**.
**Plan:** `.hermes/plans/2026-08-30_EPISODES_FUNNEL_V1.md` (T0–T4).
**Contrato:** `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`
**SDD:** `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md`

## Resumen

Se implementó `engine/episodes.py` (única capa nueva) consumiendo `build_setups_at`
sobre `projection_at(T)` (sin look-ahead). Tras el cierre inicial, Ruben dictaminó
`NEEDS REVISION` por 7 fallas de la evidencia. Todas fueron corregidas y reverificadas
contra el código/evidencia real (no por afirmación).

## Dictamen original (Ruben) y corrección

| # | Falla | Corrección aplicada | Evidencia |
|---|-------|---------------------|-----------|
| 1 | `generator_commit=cdc6bc0` en reporte, código en `b9c345d` | Reporte regenerado desde el commit correcto; `_git_commit()` ya tomaba HEAD real | reporte ahora `generator_commit=b9c345d...` |
| 2 | Reporte con UUID aleatorios | El runner usa ids deterministas (`_mo` asigna `id` estable); el reporte guardado previo era de una corrida anterior con uuid | 0 UUID en el reporte regenerado |
| 3 | Checksum guardado no coincide con recálculo | `checksum` se excluye del payload (antes incluía el valor previo → dependencia circular) en `_checksum` y `_rechecksum` | recálculo == guardado (`8feab9ec...`) |
| 4 | Checksum calculado antes de añadir `generator_commit`/`full_prefix`/`aggregated_status` | `_rechecksum` se ejecuta AL FINAL, cubriendo todos los campos | alterar `generator_commit` cambia el checksum |
| 5 | FULL/PREFIX solo comparaba `episodes`/`rejections` | `run_full_prefix` ahora compara records/episodes/rejections/aggregates/gates por T (conteos), más lineage/razones/orden | `mismatches=[]`, `prefix_matches_full=True` |
| 6 | `candidates=` permitía saltarse `projection_at(T)` en producción | Renombrado a `_candidates` (privado); lineage ahora recibe `ms,T` y rechaza componentes fuera del snapshot en T (FUTURE_DATA/TEMPORAL o INVALID_LINEAGE) | test `test_candidate_outside_projection_rejected` |
| 7 | `_check_lineage` no detectaba huérfanos/ciclos/refs fuera de snapshot | `_check_lineage(setup, ms, T)` ahora: (a) refs fuera de `projection_at(T)`→INVALID_LINEAGE; (b) BFS alcanzabilidad desde POI→MISSING_LINEAGE si huérfano; (c) DFS ciclos (confirmation/trigger tratados como hojas)→INVALID_LINEAGE | tests `test_lineage_orphan/cycle/out_of_snapshot_rejected` |

## Cambios de código

- `engine/episodes.py`:
  - `build_episodes(..., _candidates=None)` (privado).
  - `_check_lineage(setup, ms, T)` con snapshot membership + BFS alcanzabilidad + DFS ciclos (hojas = CONFIRMATION/EXECUTION).
  - `_checksum`/`_rechecksum` excluyen `generated_at` y `checksum`.
  - importa `Role` y tipos `typing`.
- `audits/codigo/episodes.py`:
  - `_rechecksum` final (cubre provenance del repo).
  - `run_full_prefix` compara artefacto completo por T.
  - `_mo` usa ids deterministas.
- `tests/test_episodes.py`: 17 tests (agregados lineage defensivo + integración con `build_setup` factory).

## T3 — Tests y auditoría (revisados)

- `tests/test_episodes.py`: **17 passed** (aceptación, mapeo elegibilidad, negativos
  futuro/autoridad/lineage/huérfano/ciclo/out-of-snapshot, dedupe, no-mutación,
  determinismo, integración real vía `build_setups_at`/`build_setup`).
- `audits/codigo/episodes.py` → `reports/audits/episodes/episodes_audit_20260830.json`:
  - `aggregated_status = PASS`, `episodes = 4`.
  - `full_prefix.prefix_matches_full = True`, `mismatches = []`.
  - `generator_commit = b9c345d...`, `checksum = 8feab9ec...` (reproducible en 2 corridas).
  - 0 UUID; checksum estable y auto-consistente.

## T4 — Cierre

- `pytest tests/`: **392 passed** (gate E6).
- `git diff --check`: solo warnings CRLF de config de repo (no errores).
- Worklog, plan (checklist T2/T3/T4 `[x]`), índice y graphify actualizados.
- Commit local selectivo (sin push).

## Gates E0–E7

| Gate | Estado |
|---|---|
| E0 Contrato+SDD presentes/enlazados | PASS |
| E1 Entrada exclusiva `projection_at(T)` | PASS (y `_candidates` no puede saltarla) |
| E2 FULL/PREFIX literal (artefacto completo) | PASS (`mismatches=[]`) |
| E3 Identidad estable/idempotencia | PASS (sha256 + NONE + dedupe) |
| E4 Rechazos/lineage/tiempos completos | PASS (incl. huérfanos/ciclos/out-of-snapshot) |
| E5 Determinismo/checksum reproducible | PASS (2 corridas idénticas; checksum auto-consistente) |
| E6 Suite focal/completa verde | PASS (392 passed) |
| E7 Bitácora/índice/graphify/commit | PASS (commit local, sin push) |

## Riesgos

- El corpus del runner es sintético: valida el contrato del funnel, no la frecuencia
  de setups en mercado real. No es edge ni backtest.
- `engine/episodes.py` depende de ids de `MarketObject` estables (requisito del
  detector); el runner usa ids deterministas para cumplir E5.
- PUSH bloqueado: requiere auditoría independiente de Codex + GO explícito de Ruben.
- `backtest/` sigue fuera de alcance (consumidor futuro, no autoridad), según dictamen.

## Siguiente acción

`READY_FOR_INDEPENDENT_AUDIT`. Tras GO + auditoría de Codex: push, o consumir Episodes
desde visor / `backtest/` aislado. No hay promoción, edge ni producción en este cierre.
