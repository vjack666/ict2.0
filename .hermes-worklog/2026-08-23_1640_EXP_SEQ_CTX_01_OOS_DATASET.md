# Bitácora — EXP-SEQ-CTX-01: validación lite, OOS, contrato y dataset offline

**Fecha:** 2026-08-23 (UTC-5)
**Autor:** Hermes (CEO operativo bajo SDD aprobado)
**Rama:** `feature/a5-audit-datos`
**Base:** `C:/Users/v_jac/Desktop/ICT SYSTEM` (ruta de trabajo del Director)

## Decisión de CEO

El SDD `SDD_EXP_SEQ_CTX_01_OOS_DATASET.md` + addendum están aprobados; el
Director declara "ya eres el CEO". Se ejecutan los 4 trabajos sin más
instrucciones, bajo las reglas no negociables (local, sin nube, sin mezclar
modos, sin ajuste post-resultado, `can_trade=false`, sin declarar edge, sin
commit/push automático).

## Cierre de G0 en Desktop (fix de causalidad del motor)

- La raíz del leakage (gate INVALIDATED 31/120 previo) vivía en el MOTOR de
  `feature/a5-audit-datos`, no en la config del test. El fix existe en la rama
  `codex/tna-full-prefix-proof-20260822` (worktree f38c) y faltaba en Desktop.
- Aplicado a `engine/mtf_navigation.py` en Desktop:
  1. `_causal_swings` publica el swing en la **barra de confirmación (`conf`)**,
     no en `j` (ventana derecha ya cerrada).
  2. `_eq_pools` reescrito para no reescribir histórico (pools visibles solo en
     primer `min_touches`).
  3. Imports: `defaultdict`, `ceil`, `floor`.
- Gate causal reejecutado: **PASS 0/120**. G0 cumplido en Desktop.
- Gate TNA (`tna_streaming_prefix_2026-08-22.json`, 0 mismatches / 124377
  decisiones) traído de f38c a Desktop como evidencia G1. G1 cumplido.

## Trabajo 1 — Auditoría `lite` (COMPLETADO)

- Artefacto auditado: `reports/audits/experiments/seq_ctx_01c_lite_oos/report.json`
  (en f38c). Gates causal+TNA en PASS. `status=PASS_SAMPLE_SUFFICIENT`,
  `usable_for_inference=False`.
- 117 obs pooled (ALIGNED=40/AGAINST=66/NEUTRAL=11). HOLDOUT 7/7, ambos
  `mean_end_24` NEGATIVO → subpotenciado, sin edge.
- Entregable: `reports/audits/experiments/seq_ctx_01c_lite_audit.md`.

## Trabajo 2 — Ampliación OOS pre-registrada (COMPLETADO, pre-registro)

- Addendum `docs/planificacion/SDD_EXP_SEQ_CTX_01_OOS_ADDENDUM.md`: bloques
  DESIGN/VAL/HOLDOUT congelados, horizontes +6/12/24/48 fijos, criterio n>=30,
  tratamiento de negativos, anti-p-hacking. Sin ejecutar antes del registro.

## Trabajo 3 — Contrato de datos (COMPLETADO)

- `docs/contratos/CONTRATO_DATASET_SEQ_CTX_01.md`: schema de 18 campos, reglas
  de frontera causal, separación de modos, lineage, purga/embargo +48, política
  `can_trade=false`.

## Trabajo 4 — Dataset offline (COMPLETADO)

- `scripts/lab/experiments/exp_seq_ctx_01_dataset.py`: fábrica específica, fallo
  cerrado por gates/hash/split/can_trade. Generó:
  - `SEQ_CTX_01_CANONICAL_BOS`: 112 filas (DESIGN 40 / VAL 48 / HOLDOUT 24)
  - `SEQ_CTX_01_LITE`: 244 filas (DESIGN 116 / VAL 60 / HOLDOUT 68)
  - Total 356, `chain_id` único, `can_trade=false`.
- `scripts/lab/experiments/validate_seq_ctx_dataset.py`: validador de contrato.
  **PASS — 356 event_ids únicos, 0 errores, modos separados.**
- Manifest: `data/learning/seq_ctx_01/manifest.json` con hashes, splits,
  `status=WAITING_FOR_OOS_EVIDENCE` (HOLDOUT `canonical_bos`=24 <30; `lite`=68).
- Salida: `data/learning/seq_ctx_01/{manifest.json, SEQ_CTX_01_CANONICAL_BOS.jsonl, SEQ_CTX_01_LITE.jsonl}`.

## Resultado final (verificación)

- G0 causal: **PASS 0/120** (motor corregido en Desktop).
- G1 TNA: **PASS 0 mismatches**.
- G2: `canonical_bos` y `lite` en datasets SEPARADOS (no combinados).
- G3: OOS temporal reproducible; HOLDOUT `lite` 68 obs (suficiente descriptivo),
  `canonical_bos` 24 (subpotenciado). Resultados negativos conservados
  (HOLDOUT `lite` ALIGNED/AGAINST con `mean_end_24` negativo).
- G4: contrato validado, hashes + lineage completos (`chain_id`, `generator_commit`).
- G5: `can_trade=false` en todas las filas y el manifest.

**Estado del dataset:** `WAITING_FOR_OOS_EVIDENCE`. No es edge, no es modelo
operativo, no autoriza backtest ni entrenamiento IA.

## Integridad

- No se modificó `data/` fuente ni `datasets/`.
- Sin commit ni push (pendiente autorización del Director).
- Archivos nuevos sin commitear en `Desktop/ICT SYSTEM`.

## Guardas de integridad

- No se modificó `data/` fuente ni `datasets/`.
- No commit ni push (pendiente autorización del Director).
- Sin declaración de edge, backtest, entrenamiento IA ni promoción.

## Riesgos

- Dataset quedará `WAITING_FOR_OOS_EVIDENCE` (holdout subpotenciado 7/7): no es
  evidencia suficiente para edge ni modelo operativo.
- El fix del motor modifica infraestructura validada; se documenta aquí y en el
  commit (cuando el Director lo autorice).
