# CERTIFICACIÓN INDEPENDIENTE — PREFLIGHT EXP-WYCKOFF-ICT-01

**Fecha:** 2026-08-26
**Responsable:** Hermes (CEO cert order)
**Rama congelada:** `preflight/exp-wyckoff-ict-01` (tip `cdf45f1`)
**Commits auditados:** `e9c9be9` (generador v2), `cdf45f1` (veredicto + JSON)
**Alcance:** SOLO certificación. Sin backtests/entrenamiento/experimentos/descargas.
**Corrección de flujo aplicada:** NO se creó carpeta fuera del proyecto; los worktrees
de certificación viven en `.hermes-cert/` (dentro del repo).

---

## [INICIO]
- Tarea: certificar/rechazar `FEASIBILITY_FAIL_INSUFFICIENT_N` de forma independiente.
- Plan aprobado: SÍ (Orden CEO).
- git status al inicio: rama `codex/pandas3-...` con DIRTY legítimo (parquet M1/M5,
  charts, briefs, `.codex/`). NO se tocó ese árbol.
- Objetivos: (1) reproducir counts desde worktree limpio en `e9c9be9`; (2) auditar
  metodología 6 puntos; (3) confirmar estadística; (4) preservar evidencia;
  (5) reconciliar índice/blockers/SDD; (6) Engram + Graphify; (7) commit+push solo en
  rama preflight, sin fusionar a `main`.

## [FASE 1] REVIEWER 1 — Reproducción independiente
- Worktree limpio: `.hermes-cert/wyckoff-ict-e9c9be9` (HEAD `e9c9be9`, CLEAN).
- Datos: `datasets/eurusd_dukascopy_20y/*.csv` TRACKED en `e9c9be9` (no los stubs parquet).
- Motor + `engine.Wyckoff.adapter` + `exp_seq_ctx_01_dataset` importan OK en pandas 3.0.3.
- Ejecutado `scripts/lab/experiments/wyckoff_feasibility_counts.py` desde cero
  (`feasibility_counts_v2.json` previo eliminado antes de correr).
- Resultado: `reproduction_feasibility_counts_v2.json` → **H1 TOTAL = 515**.
- Comparación determinista vs `cdf45f1` (`reviewer1_comparison.json`):
  `counts_identical = true`, `n_differing_fields = 0`, `regen_worktree_state = CLEAN`.
- Veredicto R1: **CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N**.

## [FASE 2] REVIEWER 2 — Auditoría de metodología
Script: `reviewer2_methodology_audit.py` (lee fuente commiteado en `e9c9be9` + JSON
auditado en `cdf45f1`). Resultado `reviewer2_methodology_audit.json`: **OVERALL PASS**.
- P1 `nodes[k].bar`: PASS.
- P2 dedup `(bar_k, direction)`: PASS.
- P3 `context_bucket` relativo a `sequence_direction` (reusa `exp_seq_ctx_01_dataset.context_bucket`): PASS.
- P4 claves de caché: las caches `ict_cache`/`wyck_cache` están keyed por `bar_k` (NO por
  `(bar_k, direction)`). Hallazgo METODOLÓGICO documentado: es internamente válido porque
  el snapshot Wyckoff y `navigate(t)` en t son funciones SOLO de la barra t, no de la
  dirección del nodo k; la dirección solo afecta al bucket vía `context_bucket`. No hay
  contaminación entre direcciones. PASS (sin defecto).
- P5 clasificación Wyckoff vs dirección ICT: matriz `ICT × WYCKOFF phase` + celda primaria
  `ICT × CONFLICT/NON_CONFLICT` presentes. PASS.
- P6 separación DESIGN/VALIDATION/HOLDOUT: definida en generador y en JSON. PASS.

## [FASE 3] REVIEWER 3 — Auditoría estadística
Script: `reviewer3_statistical_audit.py` (sobre `feasibility_counts_v2.json`).
Resultado `reviewer3_statistical_audit.json`: **OVERALL PASS**.
- R3.1 potencia: n calculado para MDE 10pp / potencia 0.80 / α 0.05 = 384.6 (sin
  corrección) / 394.6 (con corrección de continuidad). Congruente con 389 del JSON. PASS.
- R3.2 H1 TOTAL = 515 < 778 (= 2 × 389, mínimo para un diseño de 2 grupos a 389/grupo). PASS.
- R3.3 invarianza a redistribución: con total 515 < 778 es IMPOSIBLE llenar dos celdas a
  389 cada una, cualquiera sea la distribución. Celda primaria máxima observada = 361 << 389.
  El fallo es estructural, no artefacto de distribución. PASS.

## [FASE 4] Reconciliación documental
- `.hermes-index.md`: fila `EXP-WYCKOFF-ICT-01` marcada como **CERTIFICADA INDEPENDIENTE**
  (`CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`, 2026-08-26) con enlace a esta bitácora y
  a la carpeta `certification/`.
- `.hermes-state/current_blockers.md`: añadido bloque de certificación independiente
  (3 revisores PASS; evidencia en `certification/`).
- SDD/prerregistro `EXP_WYCKOFF_ICT_01_PREREGISTRATION.md`: sin cambios sustantivos
  (el veredicto confirma el cierre previsto por insuficiencia de n).
- Deuda técnica registrada: bug pandas 3.0 SEPARADO (fuera de alcance, rama propia).

## [FASE 5] Engram + Graphify
- Engram local (127.0.0.1:7437, proyecto `ict2.0`): guardado dictamen final
  (3 revisores PASS, `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`, sin secretos).
- Graphify: grafo existente en `graphify-out/graph.json` (construido 2026-08-26);
  el cierre es documental, NO cambia código → no se reconstruye el grafo (regla:
  docs-only no mueve el grafo). Se registra el nodo de certificación vía worklog/índice.

## [VERIFICACIÓN FINAL]
- Reproducción limpia: 515 = 515 (0 diffs). ✓
- Metodología: 6/6 PASS. ✓
- Estadística: 3/3 PASS. ✓
- Evidencia preservada en `reports/audits/experiments/wyckoff_ict_01/certification/`
  (scripts + JSON + log de reproducción; no depende de temporales borrados). ✓
- Reconciliación índice + blockers + worklog. ✓
- Commit en rama `preflight/exp-wyckoff-ict-01` únicamente; sin merge a `main`. ✓

## [CONCLUSIÓN]
- Veredicto final: **CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N**.
- H1 TOTAL=515 < 778; máx celda primaria 361 << 389; fallo estructural invariante a
  redistribución de celdas.
- Criterio de salida: reproducción confirma 515 observaciones (menor de 778) →
  `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`.
- En ningún caso se ejecutó `EXP-WYCKOFF-ICT-01`.
- Siguiente acción (pendiente nueva autorización CEO): inventario + borrador de
  preregistro `EXP-004B-01 — Generalización temporal` (ya preparado en
  `docs/experimentos/EXP_004B_01_TEMPORAL_GENERALIZATION_PREREGISTRATION.md`, NO ejecutar).
