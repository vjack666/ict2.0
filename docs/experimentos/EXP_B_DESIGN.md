# EXP_B_DESIGN.md — Pre-registro del grupo B (incrementalidad HTF) y lote D

**Fecha de pre-registro:** 2026-08-21 19:46 UTC (congelado ANTES de cualquier ejecución de B)
**Estado:** PRE-REGISTRADO / NO EJECUTADO
**Autor del registro:** ox-alpha (reconstrucción autorizada por Ruben tras verificar que el diseño original nunca fue persistido a disco)

**Actualización 2026-08-21 21:30 UTC:** `scripts/lab/experiments/exp_b_runner.py` generó
preflight explícito para B1–B5. Los cinco gates quedaron `BLOCKED`: B1/B2/B4/B5
requieren la rama diagnóstica PIT-stable `engine-seq-v2-causal`; B3 además
requiere un snapshot EURUSD M15 Dukascopy canónico, inexistente en el inventario.
Además, el modo diagnóstico explícito produjo `EXP_B_DIAGNOSTIC_*` sobre la
rama científica: no es ejecución válida para promoción y no cambia el diseño.

---

## ⚠️ Caveat de reconstrucción (declaración de honestidad)

El diseño original de EXP_B1–B5 existió únicamente en el contexto conversacional
de una sesión anterior y **nunca fue persistido a disco** (verificado el
2026-08-21 en `docs/experimentos/`, `.hermes-index.md`, worklogs y
`EXP_MASTER_RECONCILIATION.json`). Este documento es una **RECONSTRUCCIÓN
POST-HOC relativa a los resultados de A/C**: se declara explícitamente para que
ningún lector atribuya a este diseño un estatus de pre-registro genuino previo
a A/C. El valor de este documento es congelar las hipótesis ANTES de ejecutar
B, no antes de conocer A/C.

## Contexto

- P1 (baseline edge): CONDITIONAL_PASS — EURUSD H1 depth≥4 (A1 PASS), sobrevive
  costes (C4) y GBPUSD (C1 provisional); falla en H4 (A3), XAUUSD (C2) y es
  temporalmente inestable (C5).
- P2 (HTF incremental value): BLOCKED — B válido en worktree PIT-stable nunca ejecutado; existe solo diagnóstico no-promotable.
- Pregunta central de B: **¿el contexto HTF (Context State vía MTFNavigator)
  aporta información incremental sobre la distribución de outcomes de las
  cadenas secuenciales depth≥4?**

## Protocolo compartido congelado (idéntico al lote A)

- Motor: `run_sequential(structure_mode="lite", max_active_chains=4096, swing_left=3)`
  sobre `engine/sequential_events.py`; outcomes R reales vía
  `engine/sequential_outcome.py`.
- SL: `min(mecha sweep, swing roto) − buffer(0.0001)`; TP: measured_projection
  (fallback sancionado, igual que A1 — B no introduce TP nuevo).
- Horizonte 200 barras, tie_policy=pessimistic, warmup 20.
- Bootstrap 2000 resamples, seed 42 (clúster chain_id); baseline seed 42;
  pairing seed 4242.
- **Gate mecánico uniforme:** PASS iff n_closed≥30 AND mean_r>0 AND bootstrap
  CI95 lower>0 (por brazo/bucket donde aplique). Sin excepciones ni criterios
  post-hoc.
- **Rama de ejecución:** `engine-seq-v2-causal` (PIT-stable) bajo Excepción Y
  aprobada — SOLO diagnóstico; ningún PASS de B declara edge operativo hasta
  revalidación del funnel en v2.
- **Modo de ejecución:** runners deterministas locales (patrón
  `exp_agentA_runner.py`). PROHIBIDO ejecutar B vía loop de agente LLM
  (fallos documentados: HTTP 429 ×1, max_iterations ×1).

## Experimentos pre-registrados

### B1 — Condicionamiento por Context State
- Hipótesis H_B1: la distribución de outcome (WR, meanR) de cadenas depth≥4
  difiere según bucket de Context State ALIGNED / AGAINST / NEUTRAL
  (StructureBias del MTFNavigator, contrato CONTRATO_CONTEXT_STATE.md).
- Gates: por bucket n_closed≥30; ΔWR(ALIGNED−AGAINST) con bootstrap CI95 que
  excluya 0. Si algún bucket tiene n<30 → ese bucket BLOCKED (sin pooling).

### B2 — Valor incremental del filtro HTF
- Hipótesis H_B2: filtrar a ALIGNED-only mejora el perfil frente al
  incondicional (baseline = A1 tratamiento completo).
- Gates: ΔWR CI95 lower>0 Y n≥30 en ambos brazos. Comparación contra los
  artefactos congelados de A1 (mismo rango/dataset), no re-corrida ad-hoc.

### B3 — Réplica en M15 (CONDICIONAL)
- Idéntico a B1 sobre M15. **Precondición:** existencia de dato canónico
  Dukascopy M15 (hoy ausente — ver D3 BLOCKED). Si la precondición no se
  cumple, B3 permanece BLOCKED sin sustitutos parquet.

### B4 — Componente location (EQ50)
- Hipótesis H_B4: el location favorable (EQ50, según contrato; OTE prohibido)
  añade información incremental sobre outcome.
- Gates: mismos umbrales mecánicos por bucket favorable/no-favorable.

### B5 — Ablación LTF-only vs HTF
- Hipótesis H_B5: el contexto HTF aporta MÁS allá del contexto LTF-only
  (misma maquinaria de buckets construida solo con estructura del TF de
  ejecución). Es el test directo de "incremental".
- Gate: ΔWR(HTF-model − LTF-only-model) CI95 lower>0.

## Non-goals (explícitos)

- No promoción de señales (`STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL`).
- Ningún parámetro se ajusta después de ver resultados.
- Un gate rojo no se convierte en verde cambiando el criterio.

---

## Anexo — Pre-registro del lote D (diagnóstico y consolidación)

Congelado el 2026-08-21 19:46 UTC, ANTES de ejecutar D1/D2.

| ID | Diseño | Gate |
|----|--------|------|
| D1 | Diagnóstico de estabilidad temporal del tratamiento A1 (n=211 cerrados): WR/meanR por año, ventanas rolling 12m, terciles de régimen ATR(14) percentil causal trailing-252, primera vs segunda mitad, pendiente OLS de meanR anual | **DESCRIPTIVO — sin gate PASS/FAIL** (pre-declarado: es diagnóstico, no confirmatorio). Prohibido usar sus salidas para relajar gates de otros experimentos |
| D2 | Replicación full-span era-OOS 2006-01-01→2018-12-31 de EXP_A1 (EURUSD H1 CSV canónico, mismo protocolo congelado, seeds idénticos). Era jamás tocada por este lab | Gate mecánico estándar (idéntico a A1), declarado aquí ANTES de ejecutar |
| D3 | Unificación canónica de datos (M15/GBPUSD/XAUUSD desde Dukascopy) | N/A — **BLOCKED**: inventario 2026-08-21 confirma que `datasets/eurusd_dukascopy_20y/` solo contiene EURUSD H1/H4/D1. No existe fuente canónica para los tres legs. No se fabrican datos |

Regla de trazabilidad: cada runner D escribe audit+raw JSON con hash de dataset,
HEAD de git, y referencia a este documento como fuente del pre-registro.
