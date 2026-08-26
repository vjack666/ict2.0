# Índice de Auditorías — ICT 2.0

**Propósito:** evitar confusiones sobre qué auditorías YA están corridas y versionadas,
cuáles faltan, y quién las ejecuta localmente. Fuente de verdad: `reports/audits/`,
`.hermes/audit_state.json`, `.hermes-index.md`.

**Actualizado:** 2026-08-19

**Clasificación vigente:** este documento conserva resultados anteriores. Toda
referencia a ejecuciones fuera del checkout es `EVIDENCIA HISTÓRICA — NO
OPERATIVA`; desde 2026-08-26 el único modo válido es `LOCAL_ONLY`.

---

## 1. YA CORRIDAS Y VERSIONADAS (no repetir)

| Auditoría | Archivo local | Estado | Dónde corrió |
| --- | --- | --- | --- |
| A0 Data Integrity (stack) | `reports/audits/data/A0_A9_audit_stack.json` | PASS | checkout local |
| A0 real 20Y | `reports/audits/data/A0_real_20Y.json` | PASS | repo |
| A0–A9 stack completo | `reports/audits/data/A0_A9_audit_stack.json` + `.hermes/audit_state.json` | PASS score 1.0 | repo |
| A7 Funnel FVG/OB | `reports/audits/experiments/fvg_ob/fvg_ob_funnel.json`, `fvg_ob_funnel_20y_relation.json`, `fvg_ob_funnel_20y_strict.json` | PASS | repo |
| Funnel FVG/OB 20Y (seq+MTF) | `reports/audits/experiments/fvg_ob/mtf_seq_funnel.json` | PASS | repo |
| TNA integridad (trace) | `reports/audits/temporal/AUDITORIA_TEMPORAL_AHF_RESULT.json` | PASS_TRACE_INTEGRITY | repo |
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
| **AUDIT-CI-01** Automatización externa histórica | RETIRADA | GitHub Actions `enabled=false`; validar exclusivamente en el checkout local |

---

## 3. PENDIENTES — LOCAL (incluye cargas pesadas)

| Auditoría | Driver local | Control |
| --- | --- | --- |
| **TNA-BEHAVIORAL** (gate separado de integridad) | `scripts/audit/tna_audit_runner.py` | Solo ejecutar con permiso y recursos locales |
| **Backtest / Walk-forward (EXP-004b)** | por definir | Bloqueado hasta A0-A9 + Funnel + TNA |
| Experimentos pandas/sklearn grandes | por definir | `WAITING/BLOCKED` si el PC no puede completarlos |

---

## 4. División de ejecución (vigente)

- **Local (Hermes/Codex):** A0-07, A0-08, gates, smoke tests, auditorías, commits y trabajos autorizados.
- **Sin destino externo:** si el PC no puede completar una tarea, el estado es `WAITING/BLOCKED`; no se migra automáticamente.
- Ver `docs/EXECUTION_STRATEGY.md` para el procedimiento local.

---

## 5. Notas

- El benchmark hoy probó que el AHF (`run_timeline`) es **single-threaded por barra**
  → la carga se ejecuta en el equipo local; si no termina, queda `WAITING/BLOCKED`.
- Los destinos externos de ejecución están retirados; `workflow run`, `workflow_dispatch`, runner y cloud no forman parte del modelo vigente.
- Orden de cuellos: BOS PIT (HECHO) → TNA 20Y local → validar navegación →
  Funnel 20Y local → SEQUENCE×CONTEXT → BACKTEST local autorizado.
