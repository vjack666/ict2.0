# Auditoría EXP-SEQ-CTX-01C — validación `structure_mode=lite`

**Fecha:** 2026-08-23
**Auditor:** Hermes (Dirección de Laboratorio)
**Base auditada:** `C:/Users/v_jac/.codex/worktrees/f38c/ICT SYSTEM`
**Artefacto:** `reports/audits/experiments/seq_ctx_01c_lite_oos/report.json` + `report.md`
**Contrato:** `docs/experimentos/EXP_SEQ_CTX_01C_LITE_AMENDMENT.md`

---

## 1. Verificación de gates (hecho verificado)

| Gate | Fuente en artefacto | Resultado |
|---|---|---|
| Causal FULL-vs-PREFIX | `reports/audits/experiments/seq_ctx_01/gate_causal.json` | **PASS** (0/120, `precompute_sequences=False`) |
| TNA behavioral/full-span | `reports/audits/tna_streaming_prefix_2026-08-22.json` | **PASS** (0 mismatches) |

Ambos gates referenciados en `report.json["gates"]` están en PASS. El gate
causal usa `precompute_sequences=False` (partición por timestamp `time <= t`),
que es la configuración que cierra el leakage de `_causal_swings` de la capa H1.

## 2. Configuración verificada (hecho verificado)

- `engine.sequential_events.run_sequential` con `structure_mode="lite"`.
- `min_depth=4`, deduplicación por `structure_bar`, mismos buckets/horizontes.
- Dataset: EURUSD Dukascopy 20Y (H1 124.377 barras).
- Bloques temporales: DESIGN 2006–2015, VALIDATION 2016–2020, HOLDOUT 2021–2025.
- `+48` obligatoriamente dentro del bloque (embargo en límites).

## 3. Población y separación (hecho verificado)

- **Variante `lite` (pooled):** 117 observaciones elegibles.
  - `ALIGNED=40`, `AGAINST=66`, `NEUTRAL=11`.
  - `status = PASS_SAMPLE_SUFFICIENT` (descriptivo), `usable_for_inference = False`.
- **Población `canonical_bos` (matriz primaria, artefacto hermano):**
  - 53 observaciones; `ALIGNED=13`, `AGAINST=33`, `NEUTRAL=7`; `status = INSUFFICIENT_N`.
- **Separación:** los dos modos se reportan en filas distintas y datasets
  distintos. NO se combinan (regla de oro del amendment).

## 4. Interpretación (solo descriptiva)

- `PASS_SAMPLE_SUFFICIENT` significa que `lite` alcanzó `n>=30` en ALIGNED y
  AGAINST (40 y 66). NO es inferencia causal ni edge.
- `usable_for_inference = False` está escrito explícitamente en el artefacto.

## 5. Qué queda validado

- El pipeline `lite` corre localmente, pasa gates causal+TNA, y produce n>=30
  por bucket principal. Eso cierra la *validación de ejecución* de `lite`.
- La separación `canonical_bos` vs `lite` está documentada y respetada.

## 6. Qué NO queda validado

- **Edge:** no hay evidencia de efecto consistente. En HOLDOUT (2021–2025),
  `ALIGNED=7` con `mean_end_24 = -0.0015` y `AGAINST=7` con `mean_end_24 =
  -0.0044` — ambos NEGATIVOS. El holdout no muestra la dirección favorable.
- **Robustez OOS:** HOLDOUT tiene solo 7/7 en ALIGNED/AGAINST (subpotenciado,
  <30). No se puede declarar estabilidad.
- **Causalidad:** `lite` cambia el detector de estructura; es exploración
  secundaria, no confirmación de `canonical_bos`.

## 7. Riesgos de selección de variante

- `lite` es una *ablación* del detector STRUCTURE. Si se reportara como
  confirmación de la tesis ICT, sería un error de selección de variante.
- El amendment lo prohíbe explícitamente. El artefacto lo respeta
  (`usable_for_inference=False`).

## 8. Limitaciones del holdout

- n=7/7 por bucket → subpotenciado; IC amplísimo; cualquier diferencia es ruido.
- No se ajustaron umbrales ni horizontes tras ver resultados (protocolo congelado).

## 9. Conclusión del auditor

La variante `lite` está **validada como ejecutable y separada**, con muestra
descriptiva suficiente, pero **NO como edge ni como confirmación**. El holdout
es subpotenciado y de signo negativo. No se convierte `PASS_SAMPLE_SUFFICIENT`
en PASS de edge.

**Veredicto:** `PASS_SAMPLE_SUFFICIENT` (descriptivo) — se interpreta solo como
descriptivo, conforme al amendment y a las reglas no negociables.
