# Worklog — B0 Pipeline Científico (regresión detectada)

**Fecha:** 2026-08-20 14:10 UTC-5
**Autor:** Hermes (autónomo, bajo directiva del usuario)
**Plan:** `.hermes/plans/2026-08-16_1510_PIPELINE_APRENDIZAJE_CIENTIFICO.md` (vigente `648fb15`)
**Commit trabajo:** `648fb154ae4be5fb7e099e544acd2cb8f2407e22`

---

## [INICIO]
- Tarea: ejecutar pipeline científico de forma autónoma, empezando por B0 (baseline inmutable).
- git status al inicio: main detrás de origin/main (pull aplicado 7e2273c→648fb15). audit_state.json modificado localmente (preservado).

## [FASE B0 — BASELINE INMUTABLE]
### Descubrimiento
- `learning_pipeline.py::block0_baseline()` NO ejecuta el pipeline: vuelca números **hardcodeados**
  (ROC 0.80, test_bce 0.559, choch_events=2125). Viola la Regla de Oro del plan (medir real).
- Pipeline real = 2 etapas:
  1. `scripts/gen_choch_dataset.py` → `data/learning/choch/full/features.jsonl`
  2. `scripts/train_choch_full.py` → ROC-AUC (split aleatorio, random_state=42).

### Ejecución real
- Regeneré `features.jsonl` con el código vigente (CHOCH_IA_DISABLE=1).
- Resultado generador: **36 CHOCH reales** (M5=35, H4=1, D1=0).
  - Anterior (16-ago, mismo script): **2125 CHOCH**. ⇒ regresión −98%.
- Métricas medidas en `scripts/b0_baseline_measure.py` (replica exacta del trainer + PR-AUC/Brier/confusión):
  - n_total=36, label_ep rate=5.6%, label_peak=11.1%, label_dir=27.8%.
  - n_test≈9 por label ⇒ **INCONCLUSIVE por regla del plan (n<30)**. No se declara edge.
- Artefactos grabados: `data/learning/experiments/BASELINE-001/{manifest,metrics,dataset_stats,environment}.json` + `STATE.json` (verdict=INCONCLUSIVE).

### Hallazgo raíz (dos métodos independientes)
1. `git diff 7576826..HEAD scripts/gen_choch_dataset.py`: único cambio relevante = fix 2026-08-17
   `is_unique` (commit `a91d055`): filtra BOS y CHOCH por `e.extra.get("is_unique") is True`.
2. Diagnóstico no destructivo (`scripts/_diag_choch_filter.py`, ventana 40000 velas M5):
   - CHOCH totales (sin is_unique): **572**
   - CHOCH únicos (con is_unique): **0**  ⇒ is_unique los anula 100%.
   - CHOCH real pre-filtro: 0 (gate `choch_real = after_bos AND lvl_present` en `choch_quality.py:279` también en 0).
- Conclusión: el tesis-merger de `tools/bos_filter.py` marca los CHOCH como no-únicos
  (fusionados/perdedores), dejando 0 representantes. El generador vigente es **inviable para el dataset**.

## [DECISIÓN — OPCIÓN A APROBADA]
Ruben eligió **A**: anti-flood `is_unique` SOLO en BOS, NO en CHOCH; relajar el filtro
destructivo sobre CHOCH; re-medir baseline.

### Cambio aplicado (mínimo, en `scripts/data/gen_choch_dataset.py`)
- Se mantuvo `boe = [e for e in boe if e.extra.get("is_unique") is True]` (anti-flood BOS).
- Se ELIMINÓ `che = filter_bos_thesis(out, che, ...)` + filtro `is_unique` sobre CHOCH.
  Causa del 0/572: `filter_bos_thesis` aplica reglas de tesis BOS (HTF align / confirm)
  que anulaban CHOCH (0 pasaban `thesis_valid`).
- CHOCH ahora conservan geometría + `choch_real` de `mark_choch_quality`.
- Nota repo: hubo reorg (commit `6a1152e`) que movió generadores a `scripts/data/`;
  `scripts/gen_choch_dataset.py` es entrypoint de compatibilidad (runpy → `scripts/data/`).

### Re-ejecución (Opción A aplicada)
- Cambio 1: eliminado `filter_bos_thesis` + filtro `is_unique` sobre CHOCH en `gen_choch_dataset.py`.
- Cambio 2: eliminado `if not c.extra.get("choch_real"): continue` → se incluye TODO CHOCH
  detectado; `choch_real` queda como flag/feature para B1 auditar.
- Resultado generador: **4833 CHOCH** (M5=4666, H4=143, D1=24). Recuperado volumen masivo.
- Baseline medido (`b0_baseline_measure.py`, n=4833, split 25%/42):
  - label_ep  : RF ROC=**0.721** PR=0.304 Brier=0.129 (n_pos=819, base_rate 0.17)
  - label_peak: RF ROC=**0.758** PR=0.521 Brier=0.173 (n_pos=1493, base_rate 0.31)
  - label_dir : ROC≈0.51 (sanity, sin leakage direccional espurio)
- **Veredicto B0: MEASURED** (no INCONCLUSIVE). Señal débil pero real en label_ep/peak.
- Artefactos en `data/learning/experiments/BASELINE-001/` regrabados con métricas reales.
- commit de medición: `b3ab065` (en origin/main, post-reorg 6a1152e).

## [VERIFICACIÓN]
- `git ls-tree origin/main` del plan: blob `1046f5c` (vigente).
- Baseline grabado con sha256 dataset `a0ccbdb7…`, commit `b3ab065`.
- Regresión confirmada (2125→36) y resuelta por Opción A (→4833).
- Métricas medidas de verdad (no hardcodeadas).

## [CONCLUSIÓN B0]
- B0 GATE 0: **PASS** (baseline reproducible grabado con métricas reales).
- Veredicto: **MEASURED**. label_ep ROC=0.721, label_peak ROC=0.758.
- NO promocionado a producción (falta B1–B8 + gates).
- Siguiente: B1 (label audit) autónomo.
