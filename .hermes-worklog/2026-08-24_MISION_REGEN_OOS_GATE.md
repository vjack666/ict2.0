# Bitácora — Misión autónoma: regeneración corregida + Gate OOS EXP-SEQ-CTX-01

**Fecha:** 2026-08-24 (UTC-5)
**Agente:** Hermes (CEO operativo, misión autónoma delegada por el Director)
**Rama:** `feature/a5-audit-datos` (worktree DIRTY, sin commit/push)
**Base:** `C:/Users/v_jac/Desktop/ICT SYSTEM`

## Objetivo de la misión

Determinar con evidencia reproducible si EXP-SEQ-CTX-01 supera el Gate 4 de
suficiencia OOS después de corregir la semántica de `context_bucket`
(seq_dir + D1 bias + H4 location + H1 alignment relativos a la dirección de
secuencia). Sin preguntas entre fases. Principio: descubrir la verdad, no un PASS.

## Qué se hizo (FASE 1→5)

1. **FASE 1 — Verificación previa.** `context_bucket` usa explícitamente
   `sequence_direction`, `d1_bias`, `h4_location`, `h1_alignment` (fábrica
   líneas 190–227). 5 pruebas focales PASAN. Gates G0 causal (0/120) y G1 TNA
   (0 mismatches) en PASS. `git diff --check` limpio (solo warnings CRLF).
2. **FASE 2 — Regeneración.** Fábrica corregida ejecutada localmente
   (sin worktree, sin nube, sin descargar datos). `canonical_bos`: 100 filas;
   `lite`: 192 filas. Mismas exclusiones que antes (dedup 12/48, purge +48 0/4).
   Splits temporales congelados DESIGN/VAL/HOLDOUT. Modos separados.
3. **FASE 3 — Auditoría doble vía.** (a) Validador oficial fail-closed: PASS
   (hash MATCH, 292 filas, 292 event_ids únicos, modos separados,
   can_trade=false, buckets reconstruibles). (b) Auditoría independiente
   stdlib (`_audit_independent.py`, réplica de la lógica de bucket, hash
   recalculado desde cero): PASS — 0 duplicados, 0 can_trade!=false, 0
   context_inputs faltantes, 0 bucket no reconstruible, 0 leakage.
4. **FASE 4 — Comparación científica.** ANTES vs DESPUÉS (backup
   `manifest_before.json`). La corrección NO cambió el total de observaciones
   (sigue 292) ni las exclusiones. Solo redistribuyó la clasificación de buckets:
   el contexto opuesto (AGAINST) pasó de casi silenciado (1–4 obs) a poblado
   (3–10 obs). Esto prueba que parte del bloqueo previo era clasificación
   defectuosa, PERO la escasez real de eventos persiste.
5. **FASE 5 — Gate OOS.** Criterio pre-registrado `n >= 30` por celda
   `(variante × context_bucket × HOLDOUT)`, sin agrupar, sin mover splits.
   - canonical_bos: ALIGNED=6, NEUTRAL=11, AGAINST=3
   - lite: ALIGNED=10, NEUTRAL=36, AGAINST=10
   - **OOS_EVIDENCE_GATE = SUBPOWERED** (ninguna celda débil alcanza 30).

## Diagnóstico cuantitativo del cuello de botella

- HOLDOUT (2021–2025, 5 años) concentra solo 20.0% (canonical) / 29.2% (lite)
  del total. Tasa de eventos ~4 obs/año (canonical) y ~11/año (lite).
- Celdas más débiles y años adicionales de holdout necesarios a tasa actual:
  - canonical AGAINST n=3 → ~45 años más
  - canonical ALIGNED n=6 → ~20 años más
  - lite ALIGNED/AGAINST n=10 → ~10 años más cada una
- Conclusión: el cuello es **escasez real de eventos**, no solo clasificación.
  Llegar a n≥30 en HOLDOUT requeriría ~10–45 años más de datos.

## Decisión de detención (estado final C)

Se evalúa si una ampliación pre-registrada puede ejecutarse autónomamente:

- El addendum congela HOLDOUT 2021–2025 como "evaluación final, intocable".
- Para alcanzar n≥30 haría falta UNA de:
  1. mover el límite de HOLDOUT al futuro (rompe el holdout congelado);
  2. reducir n_min de 30 (cambia criterio estadístico post-resultado = p-hacking prohibido);
  3. cambiar la unidad de muestra / definición de evento (cambia la hipótesis).
- Ninguna está autorizada autónomamente. Todas son decisiones reservadas al
  cliente o rompen reglas no negociables (anti-p-hacking, holdout intocable).

**Estado final: C — BLOCKED_REQUIRES_CLIENT_DECISION.**

## Prohibiciones respetadas

NO backtest. NO entrenamiento IA. NO Shadow Mode. NO trading. NO can_trade=true.
NO GitHub Actions. NO nube. NO cambiar thresholds. NO p-hacking. NO mezclar
canonical/lite. NO modificar datasets fuente. NO commit/push (pendiente
autorización del Director). FASE 6 (snapshot) NO ejecutada porque Gate 4 es
SUBPOWERED.

## Archivos creados/modificados

- `data/learning/seq_ctx_01/manifest.json` (regenerado, status
  `WAITING_FOR_OOS_EVIDENCE`, OOS `SUBPOWERED`)
- `data/learning/seq_ctx_01/manifest_before.json` (respaldo ANTES para comparar)
- `data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl` (100 filas, nuevo hash)
- `data/learning/seq_ctx_01/SEQ_CTX_01_LITE.jsonl` (192 filas, nuevo hash)
- `data/learning/seq_ctx_01/exclusions_report.json`
- `scripts/lab/experiments/_audit_independent.py` (auditoría stdlib, nueva)
- `scripts/lab/experiments/_compare_before_after.py` (comparador, nuevo)
- `.hermes-worklog/2026-08-24_MISION_REGEN_OOS_GATE.md` (esta bitácora)

## Riesgos / deuda

- Inconsistencia documental: el addendum describe HOLDOUT ANTES de la corrección
  (20/0/0 y 36/3/17) y §1 describe el holdout previo a la corrección (7/7/1).
  El artefacto en disco (hoy, con buckets corregidos) dice 5/14/1 y 5/47/4 en el
  ANTES, y 6/11/3 y 10/36/10 en el DESPUÉS. El artefacto en disco es la verdad;
  el addendum está desactualizado y debe reconciliarse.
- `generator_worktree=DIRTY`: el manifest conserva hashes de fuentes; no es
  reproducido desde commit limpio hasta que el Director autorice commit.
- TNA behavioral/full-span sigue PENDIENTE (el snapshot del worklog previo V3
  embebe `tna_behavioral_full_span: PASS` como metadato, no como evidencia
  verificada de ese gate específico).

## Siguiente etapa

El proyecto queda **NO autorizado** para crear/usar el snapshot de entrenamiento
IA: el Gate OOS es SUBPOWERED. Para avanzar, el cliente debe decidir una de:

1. **Ampliar la ventana HOLDOUT** (romper el congelamiento 2021–2025) bajo un
   nuevo pre-registro explícito del cliente — solo si se acepta redefinir el
   holdout como no-intocable.
2. **Redefinir la unidad de muestra** (p.ej. incluir nodos de profundidad menor,
   o relajar dedup) bajo nuevo SDD pre-registrado — cambia la hipótesis.
3. **Aceptar SUBPOWERED** como veredicto final y no promover el dataset a IA.
4. **Reducir el alcance** a solo `lite` NEUTRAL (única celda con n=36≥30) como
   sub-experimento descriptivo, sin declarar edge.

Sin una de esas decisiones del cliente, la misión se detiene en C.

---

## Reconciliación posterior de artefactos (2026-08-24)

El cierre anterior describe correctamente esta misión hasta Gate OOS, pero
posteriormente Hermes ejecutó una misión separada de infraestructura IA. Por
eso existen artefactos posteriores que no deben confundirse con una aprobación
del Gate OOS:

- Se crearon snapshots para `canonical_bos` y `lite` con hash/schema/lineage.
- Se ejecutó `TrainingPipeline` solo como skeleton contractual:
  `model_training.executed=false`; no se aprendieron pesos.
- Se registraron checkpoints skeleton y ambos modelos quedaron en Shadow Mode
  con `can_trade=false`.
- La evaluación OOS fue descriptiva y no cambió el veredicto
  `SUBPOWERED`/`WAITING_FOR_OOS_EVIDENCE`.

La frase “FASE 6 no ejecutada” sigue siendo válida para esta misión autónoma en
su cierre original; los snapshots posteriores pertenecen a otra ejecución y no
constituyen autorización de entrenamiento real, edge ni promoción.

## Corrección aplicada al control de frontera IA (2026-08-24)

- `exp_seq_ctx_01_snapshot.py` ahora exige simultáneamente
  `manifest.status=OOS_SUFFICIENT` y `oos_sufficiency.status=SUFFICIENT` antes
  de crear un snapshot. Con el manifest vigente, termina fail-closed y no
  escribe artefactos.
- `exp_seq_ctx_01_train_pipeline.py` aplica la misma barrera antes de registrar
  modelos o checkpoints.
- El manifest de futuros snapshots distingue `tna_streaming_prefix=PASS` de
  `tna_behavioral_full_span=UNVERIFIED`; no se vuelve a presentar el primero
  como certificación global del segundo.
- Los snapshots/registries ya presentes no se borraron ni reescribieron: quedan
  como evidencia histórica de infraestructura skeleton, sin pesos aprendidos,
  sin edge y sin promoción.
