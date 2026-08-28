# Bitácora — Engine Lifecycle v1 (autoridad única de transición de MarketObject)

**Fecha:** 2026-08-28 · **Autoridad:** CEO/Metodología (Ruben) congela convención v1 y autoriza implementación.
**Departamento:** CTO / ingeniería diaria (engine/).
**Branch:** `codex/audit-hermes-cert-20260826`

## [INICIO]
- Tarea: implementar `engine/lifecycle.py` como ÚNICA autoridad causal de estados para `MarketObject` (FVG/OB), v1.
- Decisión metodológica congelada (CEO): authority_tf=lifecycle_tf=origin_tf; PARTIAL=penetración; CE 50% = evidencia no terminal; MITIGATED=recorre far_side; INVALIDATED=cierre allá; precedencia INVALIDATED>MITIGATED; EXPIRED y CONSUMED deshabilitados; OBSERVAR≠MATAR.
- git status al inicio: rama 1 commit adelante de origin, worktree sucio (datos/charts modificados sin commitear).

## [FASE 1] — Inspección del contrato real
- `engine/market_object.py` ya tiene vocabulario completo (`_ALLOWED_TRANSITIONS`, `is_terminal`, `parent_object`, `related_objects`, `first_touch_bar`, `invalidated_bar`).
- HALLAZGO: `_TERMINAL_STATES` incluía `MITIGATED`. Eso CONTRADICE la convención v1 (MITIGATED puede ir a INVALIDATED). Defecto corregido aquí.
- `engine/detectors/fvg.py` crea FVG en `ACTIVE` y nunca transiciona (confirma: el detector no gestiona lifecycle).
- `engine/detectors/ob.py` crea OB en `ACTIVE` con geometría canónica wick-to-wick (`zone_high=fp.high, zone_low=fp.low`).
- `engine/ltf_canonical_feed.py::_touch_state` mutaba estado inline a PARTIAL. Rompía la regla de autoridad única -> reencaminado a lifecycle.

## [FASE 2] — Implementación
- `engine/lifecycle.py` (nuevo): `evaluate()` y `observe_lower_tf()`.
  - `evaluate`: solo vela cerrada de authority_tf; PIT estricto (nada antes de `tradable_time`); simetría bull/bear; MITIGATED si low/high cruza far_side; INVALIDATED si cierre allá; precedencia INVALIDATED>MITIGATED; registra `CE_TOUCHED` como evidencia.
  - `observe_lower_tf`: solo observa (first_touch/penetration en meta), NO transiciona. Materializa OBSERVAR≠MATAR.
- `engine/market_object.py`: MITIGATED sale de `_TERMINAL_STATES`; MITIGATED puede -> INVALIDATED (según decisión v1).
- `engine/ltf_canonical_feed.py`: `_touch_state` delega en `evaluate` vela a vela (autoridad única preservada).

## [FASE 3] — Verificación (gates exigidos por CEO)
- `tests/test_lifecycle.py` (nuevo, 9 tests) cubre los 8 gates + PIT tradable_time:
  1. PIT FULL vs PREFIX idéntico hasta t ✓
  2. Simetría bull/bear ✓
  3. Autoridad MTF: M15 no invalida OB H4 (observe_lower_tf) ✓
  4. Terminalidad (INVALIDATED no resucita) ✓
  5. Idempotencia ✓
  6. Timestamps exactos (first_touch_bar/invalidated_bar/decision_time) ✓
  7. Precedencia INVALIDATED>MITIGATED ✓
  8. Replay pequeño real inspeccionable ✓
  + PIT: sin toque antes de tradable_time ✓
- `test_market_object_pd_contract.py::test_lifecycle_transition_contract` actualizado a la convención v1 (MITIGATED no terminal).
- `scripts/demo_lifecycle_replay.py` (nuevo): evidencia de replay vela a vela (ACTIVE->PARTIAL->INVALIDATED, barras exactas).

## [VERIFICACIÓN FINAL]
- `tests/test_lifecycle.py tests/test_ltf_canonical_feed.py tests/test_daily_motor.py tests/test_market_object_pd_contract.py` => **34 passed**.
- Replay demo => OK (FVG_M15_3_BULL: ACTIVE@10, PARTIAL@11, INVALIDATED@13; first_touch=11, invalidated=13).
- `pytest tests/` completo: **234 passed, 2 failed**.
  - FALLO PREEXISTENTE (no introducido): `test_sequential_outcome.py::test_sweep_nodes_carry_wick_extremes_backward_compatible` — confirmado fallando también sin mis cambios (`git stash`). Fuera de alcance del lifecycle; se reporta, no se toca.
  - `test_market_object_pd_contract` ya corregido arriba.

## [HALLAZGOS]
- El contrato `MarketObject` ya estaba casi listo; el defecto real era la AUSENCIA de ejecutor de lifecycle y que MITIGATED estaba marcado terminal prematuramente.
- `test_sequential_outage` preexistente sugiere deuda en `engine/sequential_events` (sweep wick extremes) — no tocado para no ampliar alcance.

## [CONCLUSIÓN]
- OBJETIVO: cumplido. Lifecycle v1 implementado como autoridad única, con tests PIT/autoridad/simetría/terminalidad/idempotencia y demo de replay.
- PENDIENTE (siguiente en orden congelado): Market State por vela, luego Setup Builder, Episodes/funnel.
- RIESGO: `test_sequential_outcome` preexistente sigue rojo; no bloquea lifecycle pero debe auditarse aparte.
- COMMIT: local selectivo (engine/lifecycle.py, engine/market_object.py, engine/ltf_canonical_feed.py, tests/test_lifecycle.py, tests/test_market_object_pd_contract.py, scripts/demo_lifecycle_replay.py). Sin push (regla del repo: push tras auditoría independiente + instrucción explícita).

## [DECLARACIÓN PARA AUDITORÍA INDEPENDIENTE — Codex / auditor]

Este cierre queda listo para que un auditor (Codex u otro autorizado) lo verifique
antes del push. Resumen ejecutivo de lo entregado y su trazabilidad:

### Cambios en esta sesión (2 commits locales, sin push)
1. `757f041` — feat(engine): lifecycle v1 — única autoridad de transición MarketObject (FVG/OB)
2. `9209641` — fix(engine): SeqNode SWEEP propaga extremos de wick desde la detección

### Qué hace cada uno
- **lifecycle v1 (757f041):** `engine/lifecycle.py` es la ÚNICA autoridad de transición de
  FVG/OB. `evaluate()` aplica la convención metodológica v1 congelada por CEO (2026-08-28):
  authority_tf=lifecycle_tf=origin_tf; PARTIAL=penetración; CE 50% = evidencia no terminal;
  MITIGATED=recorre far_side; INVALIDATED=cierre allá; precedencia INVALIDATED>MITIGATED;
  EXPIRED/CONSUMED deshabilitados; PIT/zero-lookahead estricto (nada antes de tradable_time).
  `observe_lower_tf()` solo observa (OBSERVAR≠MATAR). `engine/market_object.py`: MITIGATED
  dejó de ser terminal (exigido por la convención v1). `ltf_canonical_feed._touch_state`
  reencaminado a lifecycle (fin del mutate inline → autoridad única).
- **fix SWEEP (9209641):** el nodo SWEEP solo llevaba `pool_form_bar`; el test exigía
  `sweep_high`/`sweep_low`. Se actualizó en la fuente (`_detect_atomics` siembra los extremos
  del wick y del pool desde high[b]/low[b]/top/bot) y el nodo los propaga. No reconstruido a mano.

### Evidencia reproducible (correr localmente)
- `pytest tests/test_lifecycle.py tests/test_ltf_canonical_feed.py tests/test_daily_motor.py tests/test_market_object_pd_contract.py` → 34 passed
- `pytest tests/test_sequential_events.py tests/test_sequential_outcome.py` → 23 passed
- `pytest tests/` completo → **236 passed, 0 failed** (el test de sweep ya no está rojo)
- `python -m scripts.demo_lifecycle_replay` → replay vela a vela OK
  (FVG_M15_3_BULL: ACTIVE@10, PARTIAL@11, INVALIDATED@13; first_touch=11, invalidated=13)

### Gates exigidos por CEO — estado
1. PIT FULL vs PREFIX idéntico hasta t → CUBIERTO (test_lifecycle)
2. Simetría bull/bear → CUBIERTO
3. Autoridad MTF: M15 no invalida OB H4 → CUBIERTO (observe_lower_tf)
4. Terminalidad (no resucita) → CUBIERTO
5. Idempotencia → CUBIERTO
6. Timestamps exactos → CUBIERTO
7. Precedencia INVALIDATED>MITIGATED → CUBIERTO
8. Replay pequeño real → CUBIERTO
+ PIT tradable_time (nada antes) → CUBIERTO

### Riesgos / pendientes para el auditor
- `authority_tf != origin_tf` (OB H4 decidido por H4 mientras M15 observa): `observe_lower_tf`
  no transiciona, pero la GUARDA de que "M15 nunca sea pasado como authority_tf de un H4"
  conviene subirla a `MarketObject` cuando se construya Market State. Hoy depende del llamador.
- Worktree sucio (parquet/charts modificados sin commitear, demo_acuidad lifecycle untracked):
  excluir del push para no subir binarios de datos.
- Siguiente en orden congelado: engine/market_state.py (proyección event-sourced por T),
  luego Setup Builder, Episodes/funnel, experimentos, IA.

### Criterio de DONE para el auditor
Auditar causalidad PIT, autoridad MTF y que lifecycle sea la ÚNICA mutadora de `state`.
Si firma, proceder con push tras instrucción explícita de Ruben.

## [REVISIÓN POR AUDITORÍA — Codex NEEDS REVISION 2026-08-28]

Auditor independiente (Codex, D5 Assurance + D2) clasificó el cierre como `NEEDS REVISION`.
Hallazgos y correcciones aplicadas:

### H1 — Autoridad no protegida por el motor (CRÍTICO)
- Fallo: `evaluate()` aceptaba `authority_tf` distinto de `origin_tf`; un OB H4
  podía quedar `INVALIDATED` desde M15.
- Corrección: `MarketObject` ahora tiene `authority_tf`/`lifecycle_tf` (default = origin_tf)
  y `_validate_authority_invariants` RECHAZA en `__post_init__` authority/lifecycle != origin.
  `evaluate()` exige `authority_tf == obj.authority_tf` y lanza `ValueError` si no.
  Ya no depende del caller.

### H2 — Observación LTF mezclada con estado oficial
- Fallo: `observe_lower_tf` mutaba `first_touch_bar`/`first_touch_time`/`touch_count` canónicos.
- Corrección: `observe_lower_tf` ya NO toca metadatos oficiales. La observación se acumula
  en `obj.meta["observations"][tf]` (separada por temporalidad). touch_count/first_touch
  pertenecen solo al lifecycle de authority_tf.

### H3 — Idempotencia incompleta (touch_count duplicado)
- Fallo: doble evaluación de la misma vela incrementaba `touch_count` dos veces.
- Corrección: dedupe por `event_key = tf | candle_close_time | event_type` en
  `obj.meta["_seen_events"]`. Reprocesar la misma vela => 0 efectos secundarios.

### H4 — Auditoría histórica obsoleta
- `scripts/audit_fase5_lifecycle.py` mutaba `o.state` directo y forzaba `terminal=0`,
  contradiciendo la autoridad única de lifecycle.
- Corrección: marcado HISTÓRICO en el header; no debe usarse como auditoría vigente.
  Para medir lifecycle real, usar `engine.lifecycle`. (No se reescribió su lógica interna
  para no ampliar alcance; el header cumple la recomendación del auditor.)

### H5 — Advertencia pandas (narrative.py:303)
- `Pandas4Warning: future.no_silent_downcasting`. No bloquea; registrado para mantenimiento
  (fuera de alcance de lifecycle).

### Tests añadidos (6) cubriendo los 4 puntos del auditor
- `test_constructor_rejects_authority_tf_not_equal_origin`
- `test_evaluate_rejects_lower_tf_authority` (H1)
- `test_observe_lower_tf_does_not_alter_official_decision` (H2)
- `test_double_evaluation_idempotent_no_side_effects` (H3)
- `test_different_tf_bar_indices_not_cross_compared` (H2/H3)
- `test_observe_then_evaluate_authority_separate_tracking` (H1+H2 integración)
- `test_lower_tf_cannot_invalidate_higher_tf_object` actualizado a la nueva estructura.

### Verificación final de la revisión
- `pytest tests/` completo → **242 passed, 0 failed** (era 236 antes de la revisión).
- `scripts/demo_lifecycle_replay.py` → OK (ACTIVE->PARTIAL->INVALIDATED, barras exactas).
- Sin push (regla repo: auditoría firma + GO de Ruben).

### Estado tras revisión
Los 4 puntos de `NEEDS REVISION` están corregidos. Lifecycle v1 queda en estado
CERTIFICABLE pendiente de re-auditoría de Codex. Siguiente paso del orden congelado:
`engine/market_state.py` (proyección event-sourced por T), usando `authority_tf`/`observations`
ya separados.

## [REVISIÓN DE CERTIFICACIÓN — RUN CONTINUO + anti-falsificación TF 2026-08-28]

La segunda lectura de la auditoría (`NEEDS REVISION`) señaló defectos de
**integración y persistencia** que bloquean la certificación. Corregidos:

### C1 — "M15 disfrazado de H4" (falsificación de temporalidad)
- Fallo: `evaluate()` validaba `authority_tf == obj.authority_tf` pero NO que la
  *vela* perteneciera a ese TF. Un caller podía pasar `authority_tf="H4"` con una
  barra M15 y el motor la aceptaba.
- Corrección: `evaluate()` exige ahora `closed_bar["tf"] == authority_tf ==
  obj.authority_tf`. Si la vela es de otro TF => `ValueError`. Regla militar:
  solo una vela de authority_tf cerrada puede cambiar el estado oficial.
  (Test: `test_evaluate_rejects_bar_from_wrong_tf_m15_disguised_as_h4`.)

### C2 — Persistencia / RUN CONTINUO (round-trip SAVE→LOAD→CONTINUE)
- Fallo A: `_seen_events` era un `set` de Python → `to_dict()` → `json.dumps` explotaba.
- Fallo B: `to_dict()` no incluía `authority_tf`/`lifecycle_tf`/`observation_tf`/
  `execution_tf` → al recargar se perdía la identidad MTF.
- Corrección: `to_dict()` incluye los 4 campos nuevos y `_normalize_meta` (staticmethod)
  convierte `set` -> `lista` y dicts anidados a JSON-safe. `from_dict()` reconstruye
  `_seen_events` como `set` y lee los 4 campos. Round-trip idéntico.
  (Tests: `test_round_trip_json_preserves_full_identity_and_lifecycle`,
   `test_full_vs_save_restore_continue_identical`.)

### C3 — Identidad fail-closed (sin colapso de event_key)
- Fallo: `event_key = TF|timestamp|event_type`; si `timestamp=None` dos velas
  distintas colapsaban y se descartaban silenciosamente.
- Corrección: `event_key` ahora es `TF|time|bar_index|event_type` y EXIGE
  `bar_time` y `bar_index` válidos; si faltan, `evaluate`/`observe_lower_tf`
  lanzan `ValueError` (rechazo, no descarte). Mejor rechazar que inventar causalidad.
  (Tests: `test_evaluate_requires_identity_fail_closed`,
   `test_observe_requires_identity_fail_closed`,
   `test_distinct_bars_with_null_time_not_collapsed`.)

### Criterio de CERTIFICACIÓN (propuesto al auditor)
Lifecycle V1 se declara CERTIFIED cuando:
1. Objeto H4 no puede ser alterado por ninguna vela que no sea H4. ✅ (C1)
2. Guardar/cargar conserva EXACTAMENTE toda su identidad y lifecycle. ✅ (C2)
3. FULL vs SAVE→RESTORE→CONTINUE produce EXACTAMENTE el mismo resultado. ✅ (C2)
4. Observación LTF no reescribe historia oficial. ✅ (H2 previo)
5. Idempotencia real (misma vela => 0 efectos secundarios). ✅ (H3 + C3)

### Verificación final
- `pytest tests/` completo → **248 passed, 0 failed** (era 242 antes de esta ronda).
- Sin push (regla repo: auditoría firma + GO de Ruben).

### Siguiente paso
`engine/market_state.py` (proyección event-sourced por T). Los cimientos
(autoridad MTF protegida, observación separada, idempotencia, round-trip JSON)
ya están sentados.
