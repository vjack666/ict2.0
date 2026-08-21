# Índice de Auditorías — ICT 2.0

**Propósito:** evitar confusiones sobre qué auditorías YA están corridas y versionadas,
cuáles faltan, y quién las ejecuta (Local vs Grok). Fuente de verdad: `reports/audits/`,
`.hermes/audit_state.json`, `.hermes-index.md`.

**Actualizado:** 2026-08-21

---

## 1. YA CORRIDAS Y VERSIONADAS (no repetir)

| Auditoría | Archivo local | Estado | Dónde corrió |
| --- | --- | --- | --- |
| A0 Data Integrity (stack) | `reports/audits/data/A0_A9_audit_stack.json` | PASS | repo (CI/local) |
| A0 real 20Y | `reports/audits/data/A0_real_20Y.json` | PASS | repo |
| A0–A9 stack completo | `reports/audits/data/A0_A9_audit_stack.json` + `.hermes/audit_state.json` | PASS score 1.0 | repo |
| A7 Funnel FVG/OB | `reports/audits/experiments/fvg_ob/fvg_ob_funnel.json`, `fvg_ob_funnel_20y_relation.json`, `fvg_ob_funnel_20y_strict.json` | PASS | repo |
| Funnel FVG/OB 20Y (seq+MTF) | `reports/audits/experiments/fvg_ob/mtf_seq_funnel.json` | PASS | repo |
| TNA integridad (trace) | `reports/audits/temporal/AUDITORIA_TEMPORAL_AHF_RESULT.json` | PASS_TRACE_INTEGRITY estratificado | repo |
| TNA full-span trace + behavioral | `reports/audits/temporal/tna_20y.json` | PASS — 124.377 barras; sin edge/PnL | repo |
| Sequence PIT reproducibility G0 | `reports/audits/pit/SEQUENCE_PIT_INTEGRITY_BOUNDED.json` + `...FULL_SPARSE.json` | PASS acotado — 0 violaciones | repo |
| AHF smoke H1 | `reports/audits/runtime/ahf_smoke_H1.json` | OK | repo |
| MTF nav smoke H1 | `reports/audits/runtime/mtf_navigation_smoke_H1.json` | OK | repo |
| Sequential canonical BOS H1 20Y | `reports/audits/experiments/sequential/sequential_canonical_bos_H1_20Y.json` | OK | repo |
| Sequential events H1 20Y | `reports/audits/experiments/sequential/sequential_events_H1_20Y.json` | OK | repo |
| Sequential expectancy COMPLETE H1 20Y | `reports/audits/experiments/sequential/sequential_expectancy_COMPLETE_H1_20Y.json` | OK | repo |
| FVG/OB forward strict vs rest H1 | `reports/audits/experiments/fvg_ob/fvg_ob_forward_strict_vs_rest_H1.json` | OK | repo |
| Multifactor structure/disp/liq HTF H1 | `reports/audits/experiments/sequential/multifactor_structure_disp_liq_htf_H1.json` | OK | repo |
| Benchmark PC (spayk 20c/16GB) | `reports/audits/infrastructure/benchmark_spayk.json` | evidencia | local (hoy) |

---

## 2. PENDIENTES — LOCAL (Hermes, liviano)

| Ítem | Bloqueador | Acción |
| --- | --- | --- |
| **A0-07** Ruta raw vs loader | OPEN | Edición de código, liviano |
| **A0-08** OTE residual | OPEN | grep + parche, liviano (OTE prohibido) |
| **AUDIT-CI-01** Evidencia CI stack A0-A9 | OPEN | Correr workflow y corregir hasta PASS |

---

## 3. PENDIENTES — GROK (nube, pesado)

| Auditoría | Driver | Por qué Grok |
| --- | --- | --- |
| **Backtest / Walk-forward (EXP-004b)** | por definir | Bloqueado hasta A0-A9 + Funnel + TNA |
| Experimentos pandas/sklearn grandes | por definir | Carga pesada |

---

## 4. División de ejecución (vigente)

- **Local (Hermes):** A0-07, A0-08, AUDIT-CI-01, smoke tests, commits, `git pull/push`.
- **Grok (nube):** backtest, walk-forward y cualquier revalidación pesada; TNA 20Y ya tiene artefacto full-span PASS.
- Ver `docs/EXECUTION_STRATEGY.md` para el procedimiento copy-paste a Grok.

---

## 5. Notas

- El benchmark histórico probó que el AHF (`run_timeline`) es **single-threaded por barra**.
  La corrida TNA full-span ya está versionada; 20 cores locales siguen sin ser una
  justificación para repetirla sin necesidad.
- AWS EC2 descartado (ver `docs/AWS_EXECUTION_HOST.md`).
- Orden de cuellos: TNA 20Y PASS → G0 Sequence PIT acotado → pre-registro B → D2 →
  resolver deuda PIT del motor → BACKTEST/WFA solo tras gates.
