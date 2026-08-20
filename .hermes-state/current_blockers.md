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
