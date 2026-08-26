# PREFLIGHT-EXP-WYCKOFF-ICT-01 — Bitácora de ejecución

**Fecha:** 2026-08-25
**Autoridad:** Orden Ejecutiva CEO → Hermes (APROBADA para factibilidad)
**Base verificada:** commit `a20c66a` (`origin/feature/a5-audit-datos`)
**Rama de revisión:** `preflight/exp-wyckoff-ict-01` (worktree CLEAN, sin tocar `main`)
**Worktree:** `C:/Users/v_jac/wt_preflight_wyckoff_ict_01`
**Host:** local, Python sistema `C:/Python314/python.exe` (pandas 3.0.3, numpy 2.5.1)

---

## 1. Creación de rama limpia de revisión

- `git worktree add` sobre `a20c66a` → `preflight/exp-wyckoff-ict-01`, HEAD `a20c66aaf5d56126850701b93296cd651d04b993`.
- `git status --porcelain` vacío (CLEAN) antes de cualquier edición.
- No se trabaja ni se publica en `main`.

## 2. Reconciliación motor a5 ↔ línea causal TNA

- **Revisado explícitamente:** `engine/mtf_navigation.py` y `engine/sequential_events.py`.
- Hallazgo: `MTFNavigator` es **causal por diseño** — precompute por capa con
  detectores causales (shift/rolling/ffill) y lookup por `_asof_index(time ≤ decision_time)`.
  `run_sequential` usa solo datos históricos por cadena.
- Conclusión: `a20c66a` **ya es** la línea TNA/PIT estable (gate causal previo
  `PASS 0/120` documentado en `.hermes-index.md`). **No hay conflictos de motor
  que reconciliar ni merge automático que hacer.** Se adopta el motor existente
  como autoridad. Se conservan los scripts del gate causal previo (respaldados
  por su propio JSON de evidencia).

## 3. Corrección de contradicciones documentales

- `docs/experimentos/EXP_SEQ_CTX_01.md`: cabecera "EN EJECUCIÓN" →
  **CERRADO — CIERRE CIENTÍFICO NEGATIVO** (`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`),
  con referencia al worklog de cierre 2026-08-25.
- `.hermes-state/current_blockers.md`: **sincronizado** con `.hermes-index.md`
  (estado sin bloqueos de motor, ambos gates PASS, EXP-SEQ-CTX-01 agotado,
  EXP-WYCKOFF-ICT-01 en preflight).
- `docs/experimentos/EXP_B_DESIGN.md`: aclarado que **B1–B5 ya fueron ejecutados**
  y que **B2 HTF = `FAIL_INCREMENTAL`**. Nota de taxonomía: `EXP-WYCKOFF-ICT-01`
  **nunca** se denomina "B2".
- Identificador utilizado en todo momento: **`EXP-WYCKOFF-ICT-01`**.

## 4. Gate causal (checkout limpio)

- Script: `scripts/lab/experiments/exp_seq_ctx_01_gate.py`
- Resultado: **PASS — 0/120 violaciones** (`navigate(full,t) == navigate(prefix_through_t,t)`).
- Commit exacto: `a20c66aaf5d56126850701b93296cd651d04b993`.
- `generator_worktree = CLEAN`.
- Hashes fuente: `engine/mtf_navigation.py`, `engine/sequential_events.py`,
  `audits/codigo/mtf_seq_funnel.py` (en `gate_causal.json`).
- No falló → no se cierra como `BLOCKED_CAUSALITY`.

## 5. Adaptador mínimo Wyckoff por barra

- Archivo: `scripts/lab/experiments/wyckoff_adapter_minimal.py`
- Determinista, solo-lectura, **sin outcomes/PnL/entradas/stops/OTE/optimización/futuro**.
- Estados congelados: `PRO_TREND`, `COUNTERTREND`, `TRANSITION`, `NEUTRAL`.
- Cada snapshot usa **solo barras con `close_time <= t`** (recorte por timestamp
  en `engine/Wyckoff/adapter.py`, ya PIT-correcto; el adaptador acota a una
  ventana de las últimas N barras ≤ t, subconjunto del pasado).
- Envuelve `engine.Wyckoff.adapter.build_wyckoff_snapshot` sin modificar `engine/`.

## 6. Gate PIT del adaptador Wyckoff

- Script: `scripts/lab/experiments/wyckoff_gate_pit.py`
- Prueba: `wyckoff_state_at(full,t) == wyckoff_state_at(prefix_through_t,t)` sobre
  muestra determinista de 80 barras H1 20Y.
- Resultado: **PASS — 0/80 divergencias**.
- No falló → no se cierra como `BLOCKED_WYCKOFF_PIT`.

## 7. Conteos de factibilidad (EN EJECUCIÓN)

- Script: `scripts/lab/experiments/wyckoff_feasibility_counts.py`
- Universo: EURUSD Dukascopy 20Y `datasets/eurusd_dukascopy_20y/` H1/H4/D1.
- `structure_mode = canonical_bos`.
- Bloques: DESIGN 2006–2015, VALIDATION 2016–2020, HOLDOUT 2021–2025.
- Matriz ICT (ALIGNED/NEUTRAL/AGAINST) × Wyckoff (PRO_TREND/COUNTERTREND/TRANSITION/NEUTRAL).
- Unidad de observación: barra de estructura (`created_bar`) de `SequentialChain`
  (congruente con prerregistro §2).
- **Solo conteos.** No se calculan outcomes ni significancia. No se modifica el
  universo tras ver conteos.
- Umbral de potencia: **~389 obs/grupo** (MDE 10pp, potencia 0.80, §5 prerregistro).

## 8. Decisión automática — RESULTADO: `FEASIBILITY_FAIL_INSUFFICIENT_N` (v2 corregido)

### Invalidación de v1 (auditoría externa)
El commit `da7fb43` (preflight v1) fue invalidado por auditoría externa
(`PREFLIGHT_INVALIDATED_CONTRACT_MISMATCH`). Fallos metodológicos de v1:
1. Ancla en `created_bar` (LIQUIDITY_POOL) en vez de nodo k.
2. Sin deduplicación por `(structure_bar, direction)`.
3. `context_bucket` como `BULLISH→ALIGNED` (no relativo a `sequence_direction`).
4. Sin flag `CONFLICT`; contaba fases Wyckoff en vez de la celda primaria
   `ICT × CONFLICT/NON_CONFLICT`.
5. `generator_commit` declaraba `a20c66a` pero los scripts no existían ahí.

### v2 corregido (commit `e9c9be9` + `feasibility_counts_v2.json`)
Replica EXACTA de la lógica autoritativa del contrato
(`exp_seq_ctx_01_dataset.context_bucket` relativo a dirección, dedup
`(bar_k, direction)`, ancla nodo k, flag `CONFLICT` del `WyckoffSnapshot`).
Validado por réplica independiente del generator: **TOTAL H1 = 515** (idéntico).

Conteos v2 (H1, celdas primarias ICT × CONFLICT/NON_CONFLICT):
- ALIGNED total = 46 → CONFLICT 17 / NON_CONFLICT 29
- AGAINST total = 108 → CONFLICT 23 / NON_CONFLICT 85
- NEUTRAL total = 361 (control)
- H4: ALIGNED=3, AGAINST=27. D1: ALIGNED=1, AGAINST=2.

**Toda celda primaria de contraste está ORDENES DE MAGNITUD por debajo de
n=389** (máx H1 AGAINST×NON_CONFLICT=85, ~4.6× por debajo; ALIGNED peor).
El universo está FIJADO (EURUSD 20Y; prohibido ampliar). Para 389/grupo se
requeriría ampliar años/símbolos/TF → vedado.

**Decisión automática alcanzada: `FEASIBILITY_FAIL_INSUFFICIENT_N`.**
Se mantiene y ahora es metodológicamente correcta (no el artefacto inflado de v1).
No se ejecuta el experimento, no se amplía el universo, no se entrena.
Se detiene aquí y se espera instrucción de Rubén. Nunca llamar "B2".

## Prohibiciones respetadas

- Sin backtest, sin IA, sin snapshots de aprendizaje, sin descarga/modificación de
  datasets, sin cambiar n/MDE/horizontes/buckets, sin declarar edge, `can_train=false`,
  `can_trade=false`, sin incluir cambios ajenos (`.codex/`, briefs, charts, parquet del
  working tree original), sin push a `main`.

## Artefactos de evidencia

- `reports/audits/experiments/seq_ctx_01/gate_causal.json` (PASS 0/120)
- `reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json` (PASS 0/80)
- `reports/audits/experiments/wyckoff_ict_01/feasibility_counts.json` (conteos completos)
- `scripts/lab/experiments/wyckoff_adapter_minimal.py`
- `scripts/lab/experiments/wyckoff_gate_pit.py`
- `scripts/lab/experiments/wyckoff_feasibility_counts.py`
