# Bitácora 2026-08-19 — Optimización motor TNA + Integración Grok + Deuda

**Fecha:** 2026-08-19 18:59 UTC-5
**Responsable:** Hermes (ejecutor) bajo directiva de Ruben
**Rama:** main (local en `fc40317`; origin/main adelantado 3 commits de Grok)
**Git status al inicio:** main limpio en `fc40317`, M1/M5 ya en LFS.

---

## [INICIO]

- **Tarea:** (1) Responder "¿mi compu puede correr rápido el TNA?" → optimizar motor local.
  (2) Grok ejecutó EXP SEQUENCE × CONTEXT STATE (pendiente previo).
  (3) Descartar AWS definitivamente, seguir estrategia Grok/local.
- **Plan aprobado:** SÍ (directiva del día: pesados→Grok, livianos→local; AWS fuera).
- **Objetivos:** motor O(n) para TNA 20Y local; validar bit-exactitud; integrar trabajo de Grok.

---

## [FASE 1 — DIAGNÓSTICO DE RENDIMIENTO]

### Hallazgos (evidencia, no suposición)
- Perfil `navigate` sobre N=50 barras H1: **1957 ms/barra** → para 139.982 barras ≈ **75 horas**.
- `engine/mtf_navigation.py` `_snapshot` (líneas 409-476): recalcula `detect_bos(prefix)`
  + `detect_displacement(prefix)` sobre el prefix completo **en cada barra** → O(n²).
- `detectors/bos.py` y `tools/displacement.py` leídos: **ambos causales** (shift/rolling/ffill,
  sin futuro). Son funciones puras point-in-time ⇒ precomputables sin romper causalidad.
- Medición aislada del init original:
  - `precompute_sequences=False`: **0.1s**
  - `precompute_sequences=True`: **74.4s** (run_sequential H1, una sola vez, ya existía)
  - `navigate` viejo: **1954 ms/barra**
- **Conclusión:** DOS cuellos confirmados — loop navigate O(n²) + init run_sequential 74s.

### Decisión de arquitectura
- Atacar el loop con **precompute por capa** (arrays vectorizados una sola vez, lookup O(1) en `_snapshot`).
- Mantener `run_sequential` (74s, ineludible, paralelizable después).
- Firma pública (`navigate`, `navigate_series`, `sequence_depth_at`) queda idéntica ⇒ no rompe AHF.

---

## [FASE 2 — PARCHE v1 (FALLIDO)]

- Aplicado precompute en `__init__` + `_precompute_layer` + `_snapshot` O(1).
- **BUG:** en el loop de bias reconstruía `_structure_bias_from_swings(sh[:last_sh_idx+1], ...)`
  **dentro del loop de 139k barras** ⇒ slice de lista de miles de swings × 139k = O(n×swings).
- Síntoma: init colgado **>61 min** (matado). El init original era 74s ⇒ mi v1 lo rompió.
- **Acción:** `git checkout -- engine/mtf_navigation.py` (revertir a original importable).

---

## [FASE 3 — PARCHE v2 (CORREGIDO, en validación)]

- Reescrito `_precompute_layer`:
  - Swings vectorizados (`_swing_points`), BOS/displacement full-frame pandas (O(n)).
  - **Bias:** computado **solo en barras de swing** (pocas, ~hundreds) vía
    `swing_bars = sorted(set(sh_bars+sl_bars))`; luego **fill-forward** del resultado.
    ⇒ `_structure_bias_from_swings` se llama ~swings veces, NO 139k. O(swings) real.
  - Dealing range ventana O(n); eq_zones una vez sobre swings; `bisect_right_bar` para lookup.
- `_snapshot` ahora: lookup O(1) en cache + `bisect_right_bar` para zonas EQ.
- `_snapshot_slow` conservado como fallback (código viejo idéntico) para diff debugging.
- **Test de regresión** `scripts/regression_nav.py`: compara 200 snapshots viejos (baseline
  guardado en `reports/audits/_baseline_nav_old.json`) vs nueva versión → exige bit-exact
  (bias, regime, zones, bos, displacement, constraints.direction_hint). **CORRIENDO al cierre.**

---

## [FASE 4 — GROK: EXP SEQUENCE × CONTEXT STATE]

- Grok ejecutó (commits `0a0dba9`, `c847768`, `dd36d0a` en origin/main, NO en mi local aún):
  - `docs/CONTRATO_CONTEXT_STATE.md` (normativo, **sin EMA** — cumple índice Hermes).
  - `docs/EXP_SEQUENCE_X_CONTEXT_STATE.md` (diseño + buckets ALIGNED/AGAINST/NEUTRAL).
  - `scripts/exp_sequence_x_context_state.py` (driver).
  - `reports/audits/exp_sequence_x_context_state_H1_20Y.{json,md}`.
- **Resultado honesto:** gate **INSUFFICIENT_N**.
  - ALL_DEPTH4 n=24; CTX_ALIGNED n=5; CTX_AGAINST n=11; CTX_NEUTRAL n=8.
  - Δ ALIGNED−AGAINST @+24 = −5.45 pp (ruido, n bajo).
  - depth≥4 con `canonical_bos` produce pocas cadenas.
- **Veredicto sobre la hipótesis de máxima prioridad del SDD:**
  "¿misma secuencia rinde distinto según Context State?" → **ABIERTA**, no contrastada por n insuficiente.
  Pipeline validado de punta a punta; NO hay edge ni autorización de entry.

---

## [HALLAZGOS]

- — MOTOR: `navigate` era O(n²) por recálculo de BOS/disp por barra (confirmado por perfil).
- — MOTOR: `run_sequential` H1 init = 74s (una vez, preexistente, no era el cuello del loop).
- — BUG v1: slice de lista por barra en loop de bias → O(n×swings) → colgado 61min.
- — GROK: EXP SEQUENCE×CONTEXT STATE correcto en diseño, limitado por n=24 (depth≥4).
- — GROK: contrato Context State SIN EMA (cumple regla normativa del índice).

## [ANOMALÍAS / DEUDA]

- — Mi parche v2 NO está en GitHub (local sin commit). Grok trabajó sin él.
- — `scripts/` tiene archivos de perfil temporales (`profile_ahf.py`, `perf_*.py`,
  `baseline_nav_old.py`, `regression_nav.py`) sin commitear → limpiar antes de push.
- — EXP necesita n mayor (depth≥3 o structure_mode=lite) para responder la hipótesis.

---

## [PRÓXIMOS PASOS]

1. **Confirmar test de regresión** (bit-exact + velocidad). Si PASS → parche v2 validado.
2. `git pull` (traer 3 commits de Grok; no tocan `mtf_navigation.py` ⇒ sin conflicto).
3. `git add engine/mtf_navigation.py` + commit semántico + `git push`.
4. **FASE 3 TNA 20Y local** con motor rápido → emitir TNA-TRACE-INTEGRITY + TNA-BEHAVIORAL.
5. (Opcional, liviano ya) Re-correr EXP con depth≥3 usando motor rápido para subir n.

---

## [ESTADO AL CIERRE]

- **Tests:** 52/52 pasan (histórico); test de regresión navegación **en curso**.
- **Git local:** `fc40317` + parche `mtf_navigation.py` sin commit; origin/main 3 commits adelante (Grok).
- **Bit-exactitud parche:** PENDIENTE de confirmar (test corriendo).
- **AWS:** DESCARTADO (estrategia Grok/local vigente).
- **Hipótesis máxima prioridad SDD:** ABIERTA (n insuficiente en EXP de Grok).
