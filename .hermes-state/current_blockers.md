# Current Blockers — Pipeline Científico de Aprendizaje

**Última actualización:** 2026-08-25 19:40 UTC-5 (sincronizado con `.hermes-index.md`)

## ESTADO: SIN BLOQUEOS DE MOTOR — PREFLIGHT EXP-WYCKOFF-ICT-01 EN REVISIÓN (v2 corregido)

Estado derivado de `.hermes-index.md` y del preflight `PREFLIGHT-EXP-WYCKOFF-ICT-01`
(ejecutado en rama `preflight/exp-wyckoff-ict-01` desde `a20c66a`).

### Auditoría externa (ChatGPT) — PRIMER PREFLIGHT INVALIDADO
El commit `da7fb43` (preflight v1) fue invalidado por auditoría con veredicto
`PREFLIGHT_INVALIDATED_CONTRACT_MISMATCH`. Fallos corregidos en v2:
1. Ancla = nodo k (`nodes[k].bar`), no `created_bar` (LIQUIDITY_POOL).
2. Deduplicación por `(bar_k, direction)` (CONTRATO_DATASET_SEQ_CTX_01 §5).
3. `context_bucket` RELATIVO a `sequence_direction` (reusa `exp_seq_ctx_01_dataset.context_bucket`), no `BULLISH→ALIGNED`.
4. Contabiliza flag `CONFLICT` del WyckoffSnapshot y celda primaria `ICT × CONFLICT/NON_CONFLICT` (prerregistro §4).
5. Procedencia: el generador v2 se commitea (commit `e9c9be9`) y el conteo se
   ejecuta desde ese checkout; `generator_commit` del JSON es el commit REAL.

### Gates de causalidad — ambos PASS (se mantienen)
- **GATE CAUSAL (FULL==PREFIX MTFNavigator):** PASS 0/120 violaciones sobre H1 20Y
  (`reports/audits/experiments/seq_ctx_01/gate_causal.json`).
- **GATE WYCKOFF PIT (snapshot(full,t)==snapshot(prefix,t)):** PASS 0/80 divergencias
  (`reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json`).

### Estado de experimentos previos (reconciliado 2026-08-25)
- **B0 GATE 0:** PASS (baseline MEASURED, NO promocionado).
- **Grupo B (B1–B5):** EJECUTADO. B2 (Valor incremental filtro HTF) = `FAIL_INCREMENTAL`.
- **EXP-SEQ-CTX-01:** CERRADO con cierre científico negativo
  `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`. Sin snapshot ni entrenamiento.

### Siguiente decisión (pendiente de conteos v2 + autorización de Ruben)
- **EXP-WYCKOFF-ICT-01 — WYCKOFF × ICT CONFLICT:** preflight v2 corregido en ejecución
  (conteos por nodo k, dedup, bucket relativo, CONFLICT). Umbral: 389 obs/grupo.
  - Si n insuficiente → `FEASIBILITY_FAIL_INSUFFICIENT_N` (sin ampliar universo, sin IA).
  - Si n alcanza potencia → `FEASIBILITY_PASS_WAITING_FOR_RUBEN_GO` (detenerse).
- `can_train=false`, `can_trade=false` en todo momento.

## TRAZABILIDAD
- Worklog preflight: `.hermes-worklog/2026-08-25_PREFLIGHT_EXP_WYCKOFF_ICT_01.md`
- Generador v2: `scripts/lab/experiments/wyckoff_feasibility_counts.py` (commit `e9c9be9`)
