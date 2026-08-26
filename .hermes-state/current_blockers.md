# Current Blockers — Pipeline Científico de Aprendizaje

**Última actualización:** 2026-08-25 22:40 UTC-5 (sincronizado con `.hermes-index.md`)

## ESTADO: SIN BLOQUEOS DE MOTOR — FACTIBILIDAD EXP-WYCKOFF-ICT-01 EN CURSO

Estado derivado de `.hermes-index.md` y del preflight `PREFLIGHT-EXP-WYCKOFF-ICT-01`
(ejecutado en rama `preflight/exp-wyckoff-ict-01` desde `a20c66a`, worktree CLEAN).

### Gates de causalidad — ambos PASS
- **GATE CAUSAL (FULL==PREFIX MTFNavigator):** PASS 0/120 violaciones sobre H1 20Y
  (`reports/audits/experiments/seq_ctx_01/gate_causal.json`).
- **GATE WYCKOFF PIT (snapshot(full,t)==snapshot(prefix,t)):** PASS 0/80 divergencias
  (`reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json`).

### Estado de experimentos previos (reconciliado 2026-08-25)
- **B0 GATE 0:** PASS (baseline MEASURED, NO promocionado).
- **Grupo B (B1–B5):** EJECUTADO. B2 (Valor incremental filtro HTF) = `FAIL_INCREMENTAL`.
  Ver `.hermes-index.md` y worklogs 2026-08-21/2026-08-22.
- **EXP-SEQ-CTX-01:** CERRADO con cierre científico negativo
  `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE` (3/6 celdas < n≥30;
  canonical `19/110/23`, lite `24/177/44`). Sin snapshot ni entrenamiento.
  Cabecera histórica "EN EJECUCIÓN" corregida a cierre negativo.

### Siguiente decisión (pendiente de autorización de Ruben)
- **EXP-WYCKOFF-ICT-01 — WYCKOFF × ICT CONFLICT:** en preflight de factibilidad.
  Conteos de matriz ICT × Wyckoff por bloque (DESIGN/VALIDATION/HOLDOUT) en curso.
  Umbral: ~389 obs/grupo (MDE 10pp, potencia 0.80).
  - Si n insuficiente → `FEASIBILITY_FAIL_INSUFFICIENT_N` (sin ampliar universo, sin IA).
  - Si n alcanza potencia → `FEASIBILITY_PASS_WAITING_FOR_RUBEN_GO` (detenerse).
- `can_train=false`, `can_trade=false` en todo momento.

## TRAZABILIDAD
- Artefactos: `data/learning/experiments/BASELINE-001/{manifest,metrics,dataset_stats,environment}.json`
- Worklog preflight: `.hermes-worklog/2026-08-25_PREFLIGHT_EXP_WYCKOFF_ICT_01.md`
