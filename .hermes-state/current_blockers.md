# Current Blockers — Pipeline Científico de Aprendizaje

**Última actualización:** 2026-08-26 09:10 UTC-5 (sincronizado con `.hermes-index.md` — certificación independiente)

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

---

## CERTIFICACIÓN INDEPENDIENTE (2026-08-26) — `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`

Orden CEO: certificar/rechazar `FEASIBILITY_FAIL_INSUFFICIENT_N` sin ejecutar
backtests/entrenamiento/experimentos. Fuera de alcance: bug pandas 3.0 (rama propia).

### Revisores (3, independientes)
- **R1 — Reproducción limpia:** worktree `.hermes-cert/wyckoff-ict-e9c9be9` (HEAD `e9c9be9`,
  CLEAN). Ejecutó `wyckoff_feasibility_counts.py` desde cero (JSON previo borrado).
  Resultado: H1 TOTAL=515. Comparación determinista vs `cdf45f1`:
  `counts_identical=true`, `n_differing_fields=0`. Veredicto: **CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N**.
- **R2 — Metodología (6 puntos):** `reviewer2_methodology_audit.py` → OVERALL **PASS**.
  `nodes[k].bar` ✓; dedup `(bar_k,direction)` ✓; `context_bucket` relativo a
  `sequence_direction` ✓; caches keyed por `bar_k` (válido, snap Wyckoff solo de t) ✓;
  matriz ICT×Wyckoff + celda primaria ICT×CONFLICT ✓; separación DESIGN/VALIDATION/HOLDOUT ✓.
- **R3 — Estadística (3 puntos):** `reviewer3_statistical_audit.py` → OVERALL **PASS**.
  n calculado 384.6≅389 (MDE 10pp, potencia 0.80); H1 TOTAL=515<778; fallo **invariante**
  a redistribución de celdas (máx celda 361<<389).

### Evidencia preservada (no depende de temporales borrados)
`reports/audits/experiments/wyckoff_ict_01/certification/`
- `reviewer1_compare.py` + `reviewer1_comparison.json` (0 diffs)
- `reviewer1_reproduction.log` (log de la corrida limpia)
- `reproduction_feasibility_counts_v2.json` (regen desde `e9c9be9`)
- `reviewer2_methodology_audit.py` + `.json` (6/6 PASS)
- `reviewer3_statistical_audit.py` + `.json` (3/3 PASS)

### Dictamen
`FEASIBILITY_FAIL_INSUFFICIENT_N` **CONFIRMADO Y CERTIFICADO** como
`CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`. H1 TOTAL=515<778; máx celda primaria
361<<389; fallo estructural, no artefacto de distribución. En ningún caso se ejecutó
`EXP-WYCKOFF-ICT-01`. Rama `preflight/exp-wyckoff-ict-01` (sin merge a `main`).

### Siguiente acción (pendiente nueva autorización CEO)
Inventario + borrador de preregistro `EXP-004B-01 — Generalización temporal`
(`docs/experimentos/EXP_004B_01_TEMPORAL_GENERALIZATION_PREREGISTRATION.md`). NO ejecutar.
