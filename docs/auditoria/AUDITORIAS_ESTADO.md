# Índice de Auditorías — ICT 2.0

**Propósito:** evitar confusiones sobre qué auditorías YA están corridas y versionadas,
cuáles faltan, y qué evidencia las respalda. Todos los jobs se ejecutan localmente.
Fuente de verdad: `reports/audits/`,
`.hermes/audit_state.json`, `.hermes-index.md`.

**Actualizado:** 2026-08-23

---

## 1. YA CORRIDAS Y VERSIONADAS (no repetir)

| Auditoría | Archivo local | Estado | Dónde corrió |
| --- | --- | --- | --- |
| A0 Data Integrity (stack) | `reports/audits/A0_A9_audit_stack.json` | PASS | repo (CI/local) |
| A0 real 20Y | `reports/audits/A0_real_20Y.json` | PASS | repo |
| A0–A9 stack completo | `reports/audits/A0_A9_audit_stack.json` + `.hermes/audit_state.json` | PASS score 1.0 | repo |
| A7 Funnel FVG/OB | `reports/audits/fvg_ob_funnel.json`, `fvg_ob_funnel_20y_relation.json`, `fvg_ob_funnel_20y_strict.json` | PASS | repo |
| Funnel FVG/OB 20Y (seq+MTF) | `reports/audits/mtf_seq_funnel.json` | PASS | repo |
| TNA integridad (trace) | `reports/audits/AUDITORIA_TEMPORAL_AHF_RESULT.json` | PASS_TRACE_INTEGRITY | repo |
| AHF smoke H1 | `reports/audits/ahf_smoke_H1.json` | OK | repo |
| MTF nav smoke H1 | `reports/audits/mtf_navigation_smoke_H1.json` | OK | repo |
| Sequential canonical BOS H1 20Y | `reports/audits/sequential_canonical_bos_H1_20Y.json` | OK | repo |
| Sequential events H1 20Y | `reports/audits/sequential_events_H1_20Y.json` | OK | repo |
| Sequential expectancy COMPLETE H1 20Y | `reports/audits/sequential_expectancy_COMPLETE_H1_20Y.json` | OK | repo |
| FVG/OB forward strict vs rest H1 | `reports/audits/fvg_ob_forward_strict_vs_rest_H1.json` | OK | repo |
| Multifactor structure/disp/liq HTF H1 | `reports/audits/multifactor_structure_disp_liq_htf_H1.json` | OK | repo |
| Benchmark PC (spayk 20c/16GB) | `reports/audits/benchmark_spayk.json` | evidencia | local (hoy) |

---

## 2. PENDIENTES — LOCAL (Hermes, liviano)

| Ítem | Bloqueador | Acción |
| --- | --- | --- |
| **A0-07** Ruta raw vs loader | OPEN | Edición de código, liviano |
| **A0-08** OTE residual | OPEN | grep + parche, liviano (OTE prohibido) |
| **AUDIT-CI-01** Evidencia CI stack A0-A9 | OPEN | Correr workflow y corregir hasta PASS |

---

## 3. PENDIENTES — LOCAL (PC de Ruben)

| Auditoría | Driver | Estado |
| --- | --- | --- |
| **EXP-SEQ-CTX-01 gate causal** | `scripts/lab/experiments/exp_seq_ctx_01_gate.py` | PASS 0/120 |
| **EXP-SEQ-CTX-01 matriz** | `scripts/lab/experiments/exp_seq_ctx_01.py` | INSUFFICIENT_N; 53 obs., no inferencia |
| **EXP-SEQ-CTX-01B expansión canonical** | `scripts/lab/experiments/exp_seq_ctx_01b_oos.py` | INSUFFICIENT_N; no amplió población |
| **EXP-SEQ-CTX-01C enmienda lite** | `scripts/lab/experiments/exp_seq_ctx_01b_oos.py` | PASS_SAMPLE_SUFFICIENT descriptivo; 117 obs. |
| **Backtest / Walk-forward (EXP-004b)** | por definir | Requiere decisión explícita del cliente |

---

## 4. Política de ejecución (vigente)

- Todos los experimentos, tests, auditorías, backtests, walk-forwards,
  descargas y jobs de laboratorio se ejecutan en el PC local.
- GitHub queda limitado a repositorio, historial, revisión y sincronización
  explícitamente autorizada; no es host de ejecución.
- Ver `.hermes-state/execution_host_policy.md`.

---

## 5. Notas

- El benchmark histórico probó que el AHF (`run_timeline`) es **single-threaded por barra**;
  esto afecta el tiempo local, pero no autoriza migrar el trabajo a la nube.
- AWS EC2 descartado (ver `docs/AWS_EXECUTION_HOST.md`).
- Orden vigente: gate causal EXP-SEQ-CTX-01 → matriz canonical → expansiones
  separadas y OOS → decisión explícita para backtest, siempre en el PC local.
