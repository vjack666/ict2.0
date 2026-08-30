# Bitácora — Cierre Episodes / Funnel causal v1

**Fecha:** 2026-08-30
**Agente:** Hermes (director de D2) con revisión D5 independiente
**Departamentos:** D1 Documentación, D2 Ingeniería, D5 Assurance, D7 Delivery
**Estado:** COMPLETED — Episodes/Funnel v1 implementado, auditado y con gates E0–E7 PASS (documental/ejecución). Commit local, **sin push**.
**Plan:** `.hermes/plans/2026-08-30_EPISODES_FUNNEL_V1.md` (T0–T4).
**Contrato:** `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`
**SDD:** `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md`

## Resumen

Se implementó la capa Episodes/Funnel v1 como la única capa nueva de composición
(`engine/episodes.py`), consumiendo `build_setups_at(ms, T, ctx)` (que usa
`projection_at(T)`, sin look-ahead). El funnel no recalcula Lifecycle, MarketState,
AHF/FVG/OB ni Setup Builder; no muta objetos; no usa futuro.

## T0 — Verificación base

- Working tree limpio; rama `codex/audit-hermes-cert-20260826`; HEAD `cdc6bc0`.
- No existe `engine/episodes.py` canónico previo.
- Stash `pre-episodes-funnel-local-generated-work-2026-08-30` NO contiene código
  de episodes/funnel (solo data/reports/docs) → no hay autoridad duplicada.
- Suite focal previa: **94 passed** (Lifecycle, MarketObject, MarketState, Setup Builder).

## T1.7 — Revisión independiente D5 (gate previo a código)

Se contrastó el contrato/SDD contra la API real de `engine/` y se reconciliaron
5 discrepancias documentales (worklog `2026-08-30_AUDITORIA_D5_CONTRATO_EPISODES.md`):
1. Interfaz de entrada y campo `observation_time` → corregido a `build_setups_at` + `decision_time=T`.
2. Identidad con componentes `None` → sentinel `"NONE"`.
3. Mapeo `SetupEligibility` → estados del Episode (ELIGIBLE/SUPERSEDED/BLOCKED/OUT_OF_CONTEXT).
4. `available_time` → `candidate_time`; orden temporal sobre `MarketObject`.
5. Ambigüedad E2/FULL-PREFIX → E2 es determinismo causal del funnel (distinto de G7).

## T2 — Implementación

`engine/episodes.py` (17.7 KB, lint OK) implementa:
- `Episode` y `FunnelRecord` (etapas SNAPSHOT/SETUP/TEMPORAL/LINEAGE/IDENTITY/DEDUPLICATION/EPISODE).
- `build_episodes(ms, decisions_T, ctx, *, config, candidates=None)`:
  - consume `build_setups_at` por T (o `candidates` override para audit/tests);
  - validación fail-closed: temporal (`FUTURE_DATA`/`TEMPORAL_ORDER`), autoridad (`INVALID_AUTHORITY`), lineage (`MISSING_LINEAGE`);
  - identidad `episode_id = EP_<sha256(canonical_key)[0:24]>` con sentinel NONE;
  - dedupe idempotente (`seen_keys` → `DUPLICATE_SETUP`);
  - estado derivado de `SetupEligibility` (sin reimplementar elegibilidad);
  - artefacto JSON con records/episodes/rejections/aggregates/gates/checksum.
- `candidates` override añadido dentro del write set cerrado (el cálculo de
  candidatos sigue siendo responsabilidad de `setup_builder`/caller).

## T3 — Tests y auditoría

`tests/test_episodes.py` (13 tests, todos PASS):
- aceptación (ELIGIBLE→ACCEPTED) e integración real vía `build_setups_at` (cadena OB+FVG+BOS+DISPLACEMENT);
- mapeo SUPERSEDED/BLOCKED/OUT_OF_CONTEXT;
- negativos: FUTURE_DATA, INVALID_AUTHORITY, MISSING_LINEAGE, TEMPORAL_ORDER, DUPLICATE_SETUP, no-mutación;
- determinismo y checksum estable.

`audits/codigo/episodes.py`: runner determinista que genera
`reports/audits/episodes/episodes_audit_20260830.json`:
- 3 decisiones T, TF H4/M15, dirección ±1;
- resultado `aggregated_status = PASS`;
- `full_prefix.prefix_matches_full = True` (gate E2, FULL/PREFIX literal);
- checksum reproducible entre dos corridas (`da1008f8...`).

## T4 — Cierre

- `pytest tests/` completo: **388 passed** (gate E6).
- Reporte de auditoría generado con commit, config, provenance, aggregates, rejections, lineage y checksum.
- Worklog de cierre, plan con checklist actualizado, contrato/SDD reconciliados.
- `git diff --check` limpio sobre el write set.
- Commit local selectivo (sin push, según política del proyecto).

## Gates E0–E7

| Gate | Estado |
|---|---|
| E0 Contrato+SDD presentes/enlazados | PASS |
| E1 Entrada exclusiva `projection_at(T)` | PASS |
| E2 FULL/PREFIX literal | PASS (`prefix_matches_full=True`) |
| E3 Identidad estable/idempotencia | PASS (sha256 + NONE + dedupe) |
| E4 Rechazos/lineage/tiempos completos | PASS |
| E5 Determinismo/checksum reproducible | PASS (corridas idénticas iguales) |
| E6 Suite focal/completa verde | PASS (388 passed) |
| E7 Bitácora/índice/graphify/commit | PASS (commit local, sin push) |

## Riesgos

- El corpus del runner es sintético (sin datos reales): valida el contrato del funnel, no la frecuencia de setups en mercado real. No es edge ni backtest.
- `engine/episodes.py` depende de que los `MarketObject` de entrada tengan ids estables (requisito del detector); el runner de auditoría usa ids deterministas para cumplir E5.
- PUSH permanece bloqueado: requiere auditoría independiente de Codex + GO explícito de Ruben.

## Siguiente acción

La capa Episodes/Funnel v1 está completa y auditada localmente. La siguiente
fase autorizable (cuando Ruben lo indique) es consumir estos Episodes desde un
visor o desde `backtest/` (aislado), o avanzar otro contrato del roadmap. No
hay promoción, edge ni producción en este cierre.
