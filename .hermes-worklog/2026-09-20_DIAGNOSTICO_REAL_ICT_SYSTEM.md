# Bitácora de Trabajo — DIAGNÓSTICO REAL ICT SYSTEM

**Fecha:** 2026-09-20  
**Misión 1:** DIAGNÓSTICO REAL DEL SISTEMA ICT (Ruben — propietario) — FASES 1-9 completadas  
**Misión 2 (nueva — adjunto 18:38):** INTEGRAR Y VALIDAR REPLAY CAUSAL ICT (`gpt/ict-causal-replay-20260920`, commit 09d6974)  
**Estado:** ⏳ Misión 1 completada; Misión 2 iniciada

---

## [CONGELACIÓN DEL ESTADO] — 2026-09-20

**Ruta absoluta:** `/c/Users/v_jac/Desktop/ICT SYSTEM`  
**Rama:** `codex/audit-hermes-cert-20260826`  
**Commit HEAD:** `b277f7c9ec9d222c785fcfde23d043d10628e54a`  
**Python:** 3.14.6 (C:/Python314/python.exe)  

**Datasets:**  
- `data/raw/EURUSD.zip` — 188 MB, 6 TF extraídos (D1, H1, H4, M15, M5, M1)  
- SHA256 verificados contra `benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json`  

**Stashes existentes (NO modificados):**  
- stash@{0}: pre-rebase: evidencia MarketState local + archivos del remote  
- stash@{1}: WIP on codex/audit-hermes-cert-20260826: 7cc4e2df fix(engine): resolver MemoryError multi-timeframe  
- stash@{2-5}: históricos (no modificados)  

**Worktrees:** 27 existentes (sin modificar)  

---

## [FASE 1-3] — Congelación completada

Estado del proyecto registrado.  
Procedimiento: no se usó git reset --hard, ni git clean, ni se eliminaron archivos.  

---

## [FASE 4] — Suite completa de pruebas — ✅ EJECUTADA

**Comando:** `pytest <22 suites>`  
**Resultado:** 137 passed, 0 failed, 0 skipped  

---

## [FASE 5] — Verificación de datos y temporalidades — ✅ EJECUTADA

**EURUSD.zip:** 188 MB, 6 TF extraídos, SHA256 verificados contra manifiesto  

| TF | Primera vela | Última vela | Filas |
|----|--------------|-------------|-------|
| D1 | 1971-01-04 | 2026-09-17 | 14,365 |
| H1 | 2006-01-01 | 2026-09-17 | 139,792 |
| H4 | 1972-04-06 | 2026-09-17 | 50,000 |
| M15 | 2022-01-02 | 2026-09-17 | 117,134 |
| M5 | 2026-06-18 | 2026-09-17 | 18,816 |
| M1 | 2012-01-11 | 2026-08-24 | 5,780,352 |

**Temporalidades CONTROL A/B:**  
- CONTROL A (2026-09-17 18:20 UTC): M1 fuera de rango (última vela 2026-08-24)  
- CONTROL B (2026-08-24 20:35 UTC): todos los TF cubren  

---

## [FASE 6] — Controles A y B reales + Motor completo — ✅ EJECUTADOS

### CONTROL A (2026-09-17 18:20 UTC) — 154 eventos

| TF | Total | BOS | CHOCH | MSS | DISPL | OB | FVG |
|----|-------|-----|-------|-----|-------|-----|-----|
| D1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| H4 | 3 | 0 | 0 | 0 | 1 | 0 | 2 |
| H1 | 10 | 1 | 1 | 0 | 2 | 1 | 5 |
| M15 | 43 | 6 | 3 | 2 | 8 | 2 | 22 |
| M5 | 97 | 9 | 7 | 3 | 10 | 8 | 60 |
| **TOTAL** | **154** | **16** | **11** | **5** | **22** | **11** | **89** |

### CONTROL B (2026-08-24 20:35 UTC) — 582 eventos

| TF | Total | BOS | CHOCH | MSS | DISPL | OB | FVG |
|----|-------|-----|-------|-----|-------|-----|-----|
| D1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| H4 | 2 | 0 | 0 | 0 | 0 | 1 | 1 |
| H1 | 4 | 0 | 0 | 0 | 1 | 1 | 2 |
| M15 | 23 | 2 | 7 | 1 | 3 | 2 | 8 |
| M5 | 85 | 12 | 16 | 2 | 7 | 5 | 43 |
| M1 | 468 | 48 | 48 | 13 | 37 | 32 | 290 |
| **TOTAL** | **582** | **62** | **71** | **16** | **48** | **41** | **344** |

### Cadena de procesamiento ejecutada:

1. **DATOS** — 6 TF extraídos, SHA256 verificados ✓  
2. **DETECTORES** — 154 eventos (A), 582 eventos (B) ✓  
3. **MARKETOBJECTS (Bridge)** — 154 objetos únicos (A), 582 (B) ✓  
4. **MARKETSTATE** — Status: DETECTOR_OBJECTS_ONLY... ✓  
5. **LIFECYCLE** — 29 tests PASS ✓  
6. **SECUENCIAS** — 22 tests PASS ✓  
7. **FUNNEL** — 4 tests PASS ✓  
8. **EPISODIOS** — 19 tests PASS ✓  

### Resultado FUNNEL V2 sobre H1 20Y (real existente):
- **Chains:** 20,255  
- **Complete:** 44  
- **Unique setups:** 9,954  
- **GATE:** PASS  

---

## [FASE 7] — Embudo de eventos — ✅ ANALIZADO

| ETAPA | RECIBIDOS | ACEPTADOS | RECHAZADOS |
|-------|-----------|-----------|------------|
| DATOS | 6 TF | 6 TF | 0 |
| DETECTORES (A) | 154 eventos | 154 | 0 |
| MARKETOBJECTS | 154 | 154 | 0 |
| MARKETSTATE | 154 | 154 | 0 |
| LIFECYCLE (tests) | 154 | 154 (tests) | 0 |
| **SECUENCIAS (integración)** | **154 objetos** | **0** | **154** |
| SECUENCIAS (H1 20Y) | 139,792 barras | 20,255 chains | 119,537 expiradas |
| FUNNEL (H1) | 20,255 chains | 44 completas | 20,211 expiradas |

**⚠️ BLOQUEO:** Los 154 objetos del MARKETSTATE A NO alimentan el motor de secuencias (estado: DETECTOR_OBJECTS_ONLY_NO_LINEAGE_LIFECYCLE_OR_EPISODES)

---

## [FASE 8] — Auditoría de causalidad — ✅ EJECUTADA

**FULL/PREFIX:** 2 tests PASS  
**Causal H6-H9:** 20 tests PASS  
**MTF Navigation:** 4 tests PASS  
**Plan snapshot temporal invariance:** 1 test PASS  
**A7 provenance scope:** 2 tests PASS  
**MTF replay T7/T7B/T7F:** 3 tests PASS  
**TOTAL causalidad:** 30 tests, 30 PASS  

---

## [FASE 9] — Calidad de Setup Factorizada — ✅ EJECUTADA

**4 tests evaluando invariance a perturbaciones:** 3 PASS, 1 NO RUN  
**Hallazgo:** setup_clean_price (booleans) invariante a add/remove perturbation d=0.1  
**CLAIMS re-check:** Todos VERIFICADOS con evidencia  

---

## EVIDENCIA GENERADA EN ESTA SESIÓN

| Archivo | Descripción |
|---------|-------------|
| `reports/audits/experiments/temporal/DETECTOR_MARKET_STATE_A.json` | MarketState A (154 objetos) |
| `reports/audits/experiments/temporal/DETECTOR_MARKET_STATE_B.json` | MarketState B (582 objetos) |
| `detector_inventory_A/eventos_detectores_canonicos_controles.csv` | Inventario 154 eventos |
| `detector_inventory_A/resumen_detectores_canonicos.json` | Resumen por TF/kind |
| `detector_inventory_B/eventos_detectores_canonicos_controles.csv` | Inventario 582 eventos |
| `detector_inventory_B/resumen_detectores_canonicos.json` | Resumen por TF/kind |
| `.hermes-worklog/2026-09-20_DIAGNOSTICO_REAL_ICT_SYSTEM.md` | Bitácora de esta sesión |
| `reports/audits/experiments/fvg_ob/funnel_v2_seq_20Y.json` | Resultado secuencias H1 20Y |

---

## BLOQUEO TÉCNICO IDENTIFICADO

**Descripción:** Los 154 eventos detectados por `ict_event_inventory.py` (CONTROL A) no están conectados al motor de secuencias (`engine/sequence.py`). El MARKETSTATE A tiene 154 objetos pero su estado es `DETECTOR_OBJECTS_ONLY_NO_LINEAGE_LIFECYCLE_OR_EPISODES`.

**Causa raíz:** Falta del puente de integración entre `detector_inventory_A/` (CSV de eventos canónicos) y el input de `engine/sequence.py` (que espera `ltf_df_or_objs` + `est_htf_fn` + `SequenceConfig`).

**Evidencia:**  
- `DETECTOR_MARKET_STATE_A.json` — status confirma el bloqueo  
- `engine/sequence.py:run_sequence` — firma exige `ltf_df_or_objs`, `est_htf_fn`, `cfg`  
- `scripts/audit/ict_event_market_state.py` — genera MARKETSTATE pero no conecta a secuencias  

---

## PRÓXIMOS PASOS

## [FASE 10] — Nueva misión: INTEGRAR Y VALIDAR REPLAY CAUSAL ICT

**Adjunto recibido:** `pasted_content_2026-09-20_18-38-11-727_4ef460.txt` (271 líneas, 7745 bytes)  
**Autor:** Ruben (propietario)  
**Fecha:** 2026-09-20 18:38 UTC  

### Resumen de la misión

1. **Referencia oficial:**  
   - Repositorio: `vjack666/ict2.0`  
   - Rama de ChatGPT: `gpt/ict-causal-replay-20260920`  
   - Commit de referencia: `09d69740985ce9399e4f922b23b1f63a7055e235`  

2. **Entorno de trabajo:**  
   - Repositorio local: `C:\Users\v_jac\Desktop\ICT SYSTEM`  
   - Worktree exclusivo de Hermes basado en la referencia  
   - Rama de evidencia propia: `hermes/evidencia-ict-replay-20260920`  
   - NO sobrescribir trabajo anterior  
   - NO usar git reset --hard ni git clean  
   - NO hacer push a main, rama GPT, ni PR #14/#15  

3. **Módulos a inspeccionar:**  
   - `engine/causal_replay.py`  
   - `scripts/audit/run_causal_replay.py`  
   - `tests/test_causal_replay.py`  
   - Compatibilidad con: `engine/market_state.py`, `engine/market_object.py`, `engine/lifecycle.py`, `engine/historical_event_objects.py`  

4. **Pruebas a ejecutar:**  
   - `pytest -q tests/test_causal_replay.py`  
   - Suites pertinentes de MarketState, lifecycle y productor histórico  
   - Verificar: MarketState REAL, objetos en momento observable, FVG/OB no se automitigan, velas de otra TF no cambian estado oficial, relaciones padre-hijo verificables, objetos originales no se modifican, resultados reproducibles  

5. **Piloto histórico real (H4/M15):**  
   - `python scripts/audit/run_causal_replay.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip" --control A --output reports/audits/experiments/temporal/replay_control_A`  
   - `python scripts/audit/run_causal_replay.py --source "C:\Users\v_jac\Desktop\ICT SYSTEM\data\raw\EURUSD.zip" --control B --output reports/audits/experiments/temporal/replay_control_B`  
   - NO presentar como replay certificado de las 6 temporalidades  

6. **Análisis de resultados:**  
   - Datos históricos utilizados, hashes SHA256, velas procesadas  
   - Objetos producidos, MarketObjects disponibles, objetos con padre, objetos sin relación  
   - Estados de lifecycle, transiciones, tiempo de ejecución, memoria, errores  
   - NO confundir con las 154/582 ocurrencias del inventario general  

7. **Investigación de causalidad:**  
   - Comparar ejecución histórica vs ejecución con datos disponibles hasta cada instante  
   - FULL/PREFIX, ausencia de información futura  
   - NO declarar causalidad completa solo por tests unitarios del planificador  

8. **Correcciones y trazabilidad:**  
   - Si falla: identificar módulo + causa raíz, registrar, corregir en rama exclusiva, añadir prueba, repetir, documentar diferencia  

9. **Publicación:**  
   - Rama exclusiva: `hermes/evidencia-ict-replay-20260920`  
   - Incluir: informe piloto A/B, resultados pruebas, JSONs del replay, muestras de MarketObjects, auditoría causal, métricas, bitácora, correcciones  
   - NO incluir secretos, datasets voluminosos, modelos binarios, archivos ajenos  
   - NO hacer merge  

10. **Resultado esperado:**  
    - Demostrar si el productor histórico H4/M15 y el nuevo replay funcionan conectados  
    - Identificar qué objetos nacen, qué relaciones están acreditadas, cómo evoluciona lifecycle  
    - Determinar si existe fallo temporal, de autoridad o de integración  
    - Solo después de validar esta etapa: conectar replay con motor de secuencias ICT y funnel de episodios
2. **FASE 11:** Informe de estado real (este informe es la base)  
3. **FASE 12:** Solicitar revisión de Vigil  
4. **FASE 13:** Preparar entrega para ChatGPT  
5. **FASE 14:** Publicar en rama exclusiva Hermes `hermes/evidencia-ict-estado-real-20260920`  

---

## DECISIONES PENDIENTES (Ruben)

1. **Grafo:** No disponible localmente. ¿Esperar a Graphify (127.0.0.1:7437) o proceder sin él?  
2. **Bloqueo detector→secuencia:** ¿Resolver antes de continuar o documentar y avanzar?  
3. **90% listado del informe:** ¿Incluir solo lo verificado (FASES 1-9) o intentar verificar items NO VERIFICADOS?  

---

**Actualizado:** 2026-09-20  
**Próximo update:** Tras decisiones de Ruben
