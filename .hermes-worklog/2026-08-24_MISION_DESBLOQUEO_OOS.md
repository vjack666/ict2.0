# Bitácora — Misión multiagente: DESBLOQUEAR CIENTÍFICAMENTE EXP-SEQ-CTX-01

**Fecha:** 2026-08-24 (UTC-5)
**Orquestador:** Hermes (Agente 0 / CEO operativo) — misión autónoma, sin pausas
**Checkout único:** `C:/Users/v_jac/Desktop/ICT SYSTEM` (rama `feature/a5-audit-datos`)
**Restricciones:** sin worktree, sin nube, sin commit/push, sin descargar datos.
**Contextualización:** Engram (memoria local, #534–#542) + Graphify (grafo repo).

## Tabla de Gates (viva)

| Gate | Estado | Evidencia | Bloqueador |
|---|---|---|---|
| TNA streaming-prefix (G1) | PASS | `reports/audits/tna_streaming_prefix_2026-08-22.json` (0/124377 mismatches) | — |
| TNA behavioral/full-span | PASS (reconciliado) | `reports/audits/temporal/tna_20y.json` (124377 barras, TNA_BEHAVIORAL=PASS) + `tna_behavioral_fullspan_reconciliation.json` | — |
| Causal/PIT (G0) | PASS | `reports/audits/experiments/seq_ctx_01/gate_causal.json` (0/120) | — |
| OOS sufficiency | EN EJECUCIÓN (FASE 5) | `data/learning/seq_ctx_01/OOS_EXPANSION/` | subpotencia histórica de `canonical_bos` |
| Data contract | PENDIENTE FASE 8 | — | — |
| Reproducibility | PENDIENTE FASE 7 | — | — |
| Dataset certification | PENDIENTE FASE 8 | — | — |
| Snapshot | PENDIENTE FASE 9 | — | — |
| Auditoría final | PENDIENTE FASE 10 | — | — |

## FASE 1 — TNA behavioral/full-span (Agente 1 / Assurance) ✅ PASS
- Evidencia existente válida: `tna_20y.json` cubre **124.377 barras H1 20Y completas**
  (2006–2025), `TNA_TRACE_INTEGRITY=PASS`, `TNA_BEHAVIORAL=PASS`, asof_violations=0.
- Hashes de `engine/mtf_navigation.py` y `engine/sequential_events.py` coinciden con los
  del manifest del dataset vigente (evidencia reproducible, misma fuente).
- No se requirió nueva ejecución: se reconcilió y formalizó en
  `reports/audits/experiments/seq_ctx_01/tna_behavioral_fullspan_reconciliation.json`.
- El factory (`exp_seq_ctx_01_dataset.py`) consume `tna_streaming_prefix_...` como G1;
  este reporte es evidencia complementaria del mismo universo full-span.

## FASE 2 — Diseño de ampliación OOS (Agente 2 / Científico) ✅ PRE-REGISTRADO
- Artefacto: `docs/planificacion/OOS_EXPANSION_PREREGISTRATION.md` (escrito ANTES de
  generar observaciones).
- Universo congelado: 8 instrumentos (7 FX + XAUUSD) × {canonical_bos, lite} × HOLDOUT 2021–2025
  (+ EURUSD DESIGN/VALIDATION, pues solo EURUSD tiene D1/H4 pre-2020).
- Mismos parámetros: horizontes +6/12/24/48, purga +48, dedup intra-variante,
  context_bucket normativo, `can_trade=false`. Criterio `n>=30` por celda.
- Criterio de parada: (A) todas celdas ≥30, o (B) agotado universo pre-registrado.

## FASE 3 — Inventario de datos (Agente 3 / CDO) ✅
- `data/learning/seq_ctx_01/OOS_DATA_INVENTORY.json`.
- 8 instrumentos en `data/raw` (7 pares FX + XAUUSD). HALLAZGO: H1 desde 2006, pero **D1/H4 solo desde
  2020-01-02** en los 7 no-EURUSD → contexto PIT válido SOLO para HOLDOUT 2021–2025.
  Esto justifica el diseño de FASE 2 (no-EURUSD aporta solo HOLDOUT).

## FASE 4 — Revisión de pipeline + tests (Agente 4 / CTO) ✅
- `scripts/lab/experiments/exp_seq_ctx_01_oos_expansion.py` generaliza la fábrica a
  multi-símbolo SIN cambiar semántica (mismo bucket, purga +48, dedup, PIT, can_trade).
- `tests/focal/test_oos_expansion_focal.py`: **15/15 PASS** (scoring normativo
  bullish/bearish × aligned/against/neutral, sensibilidad H4/H1, purga +48, dedup,
  guarda can_trade=false, no mezcla modos, rechazo timestamp futuro).

## FASE 6 — Gate de suficiencia OOS (Agente 6, independiente) ✅ COMPLETADA
- `_oos_sufficiency_verdict.py` (estadístico distinto al ejecutor).
- Universo pre-registrado **AGOTADO** (8 símbolos procesados). Celdas HOLDOUT:
  - canonical_bos: ALIGNED=19 ❌, NEUTRAL=110 ✅, AGAINST=23 ❌
  - lite: ALIGNED=24 ❌, NEUTRAL=177 ✅, AGAINST=44 ✅
- **VEREDICTO: `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`** (3 celdas <30 tras
  agotar el universo). NO se rebajó el umbral. NO se combinaron celdas.

## FASE 7 — Reproducción limpia ⏸ NO APLICABLE
- No procede: el criterio de entrar a FASE 7 era TNA PASS + OOS SUFFICIENT. OOS=EXHAUSTED.
  Eliminar DIRTY del worktree requeriría commit (prohibido sin autorización del cliente).

## FASE 8 — Data contract ⏸ NO APLICABLE (validador listo, no ejecutado)
- `validate_oos_expansion.py` quedó preparado pero FASE 6 = EXHAUSTED => la cadena
  `run_remainder.py` no lo invocó (correcto: sin suficiencia OOS no se certifica dataset
  para aprendizaje). La integridad SÍ se verificó en FASE 10 (red team) sobre el JSONL.

## FASE 9 — Snapshot ⛔ BLOQUEADO (por diseño)
- `exp_seq_ctx_01_oos_snapshot.py` NO se ejecutó: requiere FASE6=OOS_SUFFICIENT.
  No se creó snapshot de entrenamiento. `can_trade=false` preservado.

## FASE 10 — Auditoría independiente final (Agente 10 / Red Team) ✅ COMPLETADA
- `_audit_oos_final.py`: **integridad técnica PASS**, pero `PASS_INTEGRITY_ONLY`;
  no es elegible para snapshot porque OOS está agotado y el worktree está DIRTY.
  SOBRE LA INTEGRIDAD (no leakage, no mezcla canonical/lite, no duplicados,
  HOLDOUT no contaminado, buckets reconstruibles 100%, `can_trade=false`).
- IMPORTANTE: el veredicto red team certifica CALIDAD TÉCNICA del dataset, NO
  suficiencia OOS. El gate OOS (FASE 6) sigue siendo el que dicta el cierre.

## VEREDICTO FINAL DE MISIÓN
**`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`** — cierre científico NEGATIVO honesto.
El universo pre-registrado (8 instrumentos: 7 FX + XAUUSD × HOLDOUT 2021–2025) se agotó y 3 de 6 celdas
ALIGNED/AGAINST quedaron <30. Esto NO es un fallo de ingeniería ni se corrige
rebajando el umbral: es evidencia de que `canonical_bos` (y parcialmente lite ALIGNED)
es un detector de eventos demasiado raros para alcanzar potencia muestral OOS bajo el
diseño aprobado. La IA NO se entrena. No se declara edge. No se activa trading.
Estado final del experimento: `WAITING_FOR_OOS_EVIDENCE` (cierre científico documentado,
sin snapshot de aprendizaje).

## HALLAZGO CIENTÍFICO CENTRAL
El bloqueo no es ingeniería: es **potencia muestral**. `canonical_bos` es un detector
de eventos raros; tras agotar 8 símbolos × HOLDOUT 2021–2025, sus celdas ALIGNED/AGAINST
podrían seguir <30. Eso NO es un fallo a "arreglar rebajando el umbral": es evidencia de
que bajo el diseño pre-registrado no hay potencia suficiente para esas celdas. El
veredicto honesto sería `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE` (no un PASS).

## Correcciones posteriores de auditoría (2026-08-24)

- El conteo correcto es **625 filas totales** (`canonical_bos=236`, `lite=389`),
  de las cuales **397 pertenecen a HOLDOUT** (`152` canonical y `245` lite).
  La frase anterior “625 obs HOLDOUT” era incorrecta y queda corregida; los
  conteos por celda y el veredicto OOS no cambian.
- El validador ahora comprueba explícitamente la purga `+48`, el split temporal
  real y timestamps futuros dentro de `features_at_t`. Resultado: **16 pruebas
  focales PASS** y contrato OOS PASS sobre las 625 filas.
- El red team separa integridad de elegibilidad: veredicto
  `PASS_INTEGRITY_ONLY`, `snapshot_eligible=false`, porque el OOS está agotado y
  el worktree de generación está `DIRTY`.

## SIGUIENTE ACCIÓN
No repetir FASE 5/6 con el mismo universo. Solo preparar un nuevo preregistro
metodológico o cerrar este experimento; no entrenar IA ni crear snapshot.
