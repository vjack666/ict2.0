# Current Blockers — Pipeline Científico de Aprendizaje

**Última actualización:** 2026-08-20 20:10 UTC-5

## ESTADO: SIN BLOQUEOS (B0 resuelto)

- **B0 GATE 0: PASS** — baseline medido con métricas REALES.
  - n=4833 CHOCH (recuperado tras Opción A; era 36 por regresión is_unique).
  - label_ep: RF ROC=0.721, PR=0.304, Brier=0.129
  - label_peak: RF ROC=0.758, PR=0.521, Brier=0.173
  - label_dir: ROC≈0.51 (sanity, sin leakage)
  - Veredicto: **MEASURED**. NO promocionado.
- Artefactos: `data/learning/experiments/BASELINE-001/{manifest,metrics,dataset_stats,environment}.json`

## HALLAZGO RESUELTO — Regresión del generador
- Causa: fix `is_unique` (a91d055) + filtro `choch_real` anulaban CHOCH (2125→36).
- Resuelto por Opción A (Ruben): anti-flood solo en BOS; CHOCH conserva geometría.
- Cambio en `scripts/data/gen_choch_dataset.py` (sin commitear, pendiente de commit).

## AVANCE
- B0 completo. En curso: B1 (label audit).
- Worklog: `.hermes-worklog/2026-08-20_1410_PIPELINE_B0_REGRESION.md`

---

## CERTIFICACIÓN INDEPENDIENTE (2026-08-26) — `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`

EXP-WYCKOFF-ICT-01 certificado independientemente como `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`.
3 revisores: R1 reprodujo H1 TOTAL=515 desde worktree limpio `e9c9be9` (0 diffs vs `cdf45f1`);
R2 metodología 6/6 PASS; R3 estadística 3/3 PASS (n calculado 384.6≅389; H1 515<778;
fallo invariante a redistribución, máx celda 361<<389).

Evidencia preservada (sin temporales borrados):
`reports/audits/experiments/wyckoff_ict_01/certification/`
(reviewer1_compare.py+json, reviewer1_reproduction.log, reproduction_feasibility_counts_v2.json,
reviewer2_methodology_audit.py+json, reviewer3_statistical_audit.py+json, CERTIFICATION_VERDICT.md).

Esta fusión es QUIRÚRGICA: solo evidencia de certificación + docs científicos + índice/blockers/worklog.
NO incluye motor (`engine/`), datos (`data/`, `datasets/`), gráficos (`reports/charts/`) ni briefs.
Fuera de alcance: bug pandas 3.0 (rama separada). No se ejecutó EXP-WYCKOFF-ICT-01.

Siguiente acción (pendiente autorización CEO): borrador preregistro `EXP-004B-01 — Generalización
temporal` (`docs/experimentos/EXP_004B_01_TEMPORAL_GENERALIZATION_PREREGISTRATION.md`). NO ejecutar.
