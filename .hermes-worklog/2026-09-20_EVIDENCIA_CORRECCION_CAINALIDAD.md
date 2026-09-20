# Bitácora de Trabajo — EVIDENCIA DE CORRECCIÓN CAUSALIDAD

**Fecha:** 2026-09-20
**Rama:** `hermes/evidencia-ict-estado-real-20260920`
**Commit HEAD:** ver `git rev-parse HEAD` en esta rama
**SHA del commit de evidencia:** pendiente (se hace en este commit)
**Python:** 3.14.6 (C:/Python314/python.exe)

**Misión:** Verificar que los 7 fallos de causalidad (rayos A y B) están resueltos y documentar la evidencia reproducible. Sin repetir publicación del commit GPT `ddcb09b9` ni del commit Hermes `79b71eb1` (que ya existen en GitHub, en `origin/gpt/ict-causal-replay-20260920` y `origin/hermes/evidencia-ict-replay-pass-20260920` respectivamente).

---

## RESUMEN EJECUTIVO

Los 7 fallos de causalidad (rayos A y B) **YA ESTÁN RESUELTOS** en esta rama, por los commits heredados reescritos (`b277f7c9`, `5e10b10f`, `b690c9d0`) que incluyen la corrección de causalidad equivalente al commit Hermes `79b71eb1`. La corrección está IMPLEMENTADA (no reimplementada) — los métodos `_is_out_of_order`, `_save_object_snapshot`, `_record_transition`, y `advance_bar` con `_update_last_seen` ya tienen la lógica correcta.

La auditoría independiente de Vigil está EN CURSO (mensaje enviado, respuesta pendiente). No se incluye el dictamen aún.

---

## CAUSAS INDIVIDUALES DE LOS SIETE FALLOS (en la rama GPT remota `ddcb09b9`, sin corrección)

### Rayo A — Barra anterior al nacimiento del objeto (fallos 1-6)

**Bug raíz común:** `engine/market_state.py:_save_object_snapshot` (línea 334) lanza `ValueError: snapshot time reversed` cuando intenta guardar un snapshot con timestamp anterior al último snapshot existente.

**Caso 1 — `test_H7_vela_fuera_de_orden_rechazada_fail_closed`:**
- `advance_bar` acepta barra válida (index 10, tiempo T1).
- La firma observable cambia (touches/CE/metadata), se intenta guardar snapshot con tiempo T1.
- Pero ya hay un snapshot previo con tiempo MAYSOR (ej. de barra anterior) → ValueError.

**Caso 2 — `test_H7_mismo_tf_reloj_independiente_no_contamina_otro_tf`:**
- Mismo bug: después de aceptar barra H4 válida, la firma observable cambia y se intenta guardar snapshot con tiempo de la barra actual, que es ANTERIOR al último snapshot guardado.

**Caso 3 — `test_H8_m15_observa_correctamente_h4_sin_cambiar_estado`:**
- M15 observa H4: firma observable cambia (touches), se intenta guardar snapshot con tiempo M15 (T0+30m), que es ANTERIOR al snapshot previo (T0+4h de H4) → ValueError.

**Caso 4 — `test_OE06_objeto_terminal_no_resucita`:**
- After invalidating bar (index 12), the observable signature changes, triggering `_save_object_snapshot` with time T2, but last snapshot is T1 (from earlier valid bar) → ValueError.

**Caso 5 — `test_OE10_padre_htf_invalidado_hijo_ltf_sigue_existiendo`:**
- Same bug: after invalidating parent H4, the LTF (FVG M15) observable signature changes (touch_count metadata), triggering snapshot save with time T2, but last H4 snapshot is T1 → ValueError (even though FVG has its own authority_tf M15, the snapshot is keyed by obj_id and the time check is global per obj_id).

**Caso 6 — `test_OE11_save_load_conserva_reloj_out_of_order`:**
- Same bug: after accepting first valid bar (index 10), firma observable changes, `_save_object_snapshot` called with time T1, but there's already a snapshot with later time → ValueError.

**Corrección aplicada (equivante al commit Hermes `79b71eb1`):**
- `_is_out_of_order` ahora rechaza cuando `bar_idx < last_idx` aunque `bar_time >= last_time` (compara índice, no tiempo, para la TF que decide/observa).
- `_save_object_snapshot` guarda snapshot solo cuando el estado oficial cambia (no solo cuando la firma observable cambia). Esto evita guardar snapshots irrelevantes que causan el error de "time reversed".
- `advance_bar` avanza el reloj de la TF solo si la barra fue ACEPTADA (`_update_last_seen` al final, después del check de out-of-order).
- `_record_transition` guarda la transición en la línea temporal del objeto para que `projection_at` refleje el cambio de estado.

### Rayo B — Transición histórica directamente + projection_at(T) (fallo 7)

**Caso 7 — `test_object_invalidated_after_T_available_in_prior_snapshot`:**
- El objeto se invalida después de `t_late` mediante `ob.transition_to(ObjectState.INVALIDATED)` + `ms._record_transition(...)`.
- `projection_at(t_early)` y `projection_at(t_late)` no reflejan la transición porque `_record_transition` no guarda snapshot de la transición.
- El contrato exige: "una transición registrada mediante una API pública debe mantener coherentes el historial de estados y los snapshots completos."
- Si `projection_at(t_late)` muestra `ACTIVE` en lugar de `INVALIDATED`, el historial está roto.

**Corrección aplicada:**
- `_record_transition` ahora guarda un snapshot del objeto en el momento de la transición (si el tiempo es válido y posterior al último snapshot). Esto hace que `projection_at(t_late)` refleje `INVALIDATED`.

---

## CONTRATO CORRECTO DE CADA OPERACIÓN (determinado por el usuario)

1. **Barra anterior al nacimiento del objeto:** NO debe cambiar retroactivamente su estado. `OUT_OF_ORDER` fail-closed (rechaza la barra y registra el evento).
2. **Transición registrada mediante API pública:** debe mantener coherentes el historial de estados Y los snapshots completos. `projection_at(T)` debe reflejar la transición.
3. **Si una prueba modifica directamente estructuras internas:** determina si debe adaptarse al contrato público; NO cambies su expectativa solo para conseguir PASS.

---

## VERIFICACIÓN

### 7 pruebas fallidas (rayos A y B) — ahora PASAN

```
tests/test_integridad_causal_h6_h9.py::test_H7_vela_fuera_de_orden_rechazada_fail_closed PASSED
tests/test_integridad_causal_h6_h9.py::test_H7_mismo_tf_reloj_independiente_no_contamina_otro_tf PASSED
tests/test_integridad_causal_h6_h9.py::test_H8_m15_observa_correctamente_h4_sin_cambiar_estado PASSED
tests/test_integridad_causal_h6_h9.py::test_OE06_objeto_terminal_no_resucita PASSED
tests/test_integridad_causal_h6_h9.py::test_OE10_padre_htf_invalidado_hijo_ltf_sigue_existiendo PASSED
tests/test_integridad_causal_h6_h9.py::test_OE11_save_load_conserva_reloj_out_of_order PASSED
tests/test_setup_builder_integration.py::test_object_invalidated_after_T_available_in_prior_snapshot PASSED

7 passed in 2.00s
```

**Archivo de evidencia:** `.hermes-worklog/2026-09-20_FALLOS_CAINALIDAD_A_B_TRACE.txt` (tracebacks completos de los 7 fallos en la rama GPT remota `ddcb09b9`, sin corrección).

### Pruebas focales de replay (H4/M15 A/B) — PASAN

```
tests/test_mtf_replay_t7b.py::test_t7b_context_uses_latest_published_bos_only PASSED
tests/test_mtf_replay_t7f_completion.py::test_aggregate_requires_every_year_and_preserves_provenance_block PASSED
tests/test_mtf_replay_orchestrator.py::test_clock_batches_simultaneous_closes_htf_first_independent_of_input_order PASSED
tests/test_mtf_replay_orchestrator.py::test_orchestrator_emits_valid_deterministic_artifact_and_chunks PASSED
tests/test_mtf_replay_orchestrator.py::test_full_prefix_is_identical_for_every_observable_batch PASSED  <-- VERIFICADOR A/B HISTÓRICO
tests/test_mtf_replay_orchestrator.py::test_lower_tf_observation_cannot_kill_h4_object PASSED
tests/test_mtf_replay_orchestrator.py::test_event_driven_decisions_skip_only_duplicate_recomposition PASSED
tests/test_mtf_replay_orchestrator.py::test_checkpoint_resume_preserves_market_state_and_rejects_hash_mismatch PASSED
tests/test_mtf_replay_orchestrator.py::test_execution_waits_one_bar_and_post_entry_invalidation_is_separate PASSED
tests/test_mtf_replay_orchestrator.py::test_cancel_before_entry_removes_pending_plan_and_same_bar_never_fills PASSED
tests/test_mtf_replay_orchestrator.py::test_m5_refinement_profile_uses_same_clock_without_extra_authority PASSED
tests/test_mtf_replay_orchestrator.py::test_chunk_writer_materializes_lazy_files_without_semantic_drift PASSED

12 passed in 3.53s
```

**Verificador A/B histórico:** `test_full_prefix_is_identical_for_every_observable_batch` — FULL y PREFIX dan resultados idénticos para cada lote observable. PASS.

### Suite completa — PASÓ

```
845 passed, 0 failed, 0 skipped, 8 warnings in 65.70s
```

**Archivo de evidencia:** `.hermes-worklog/2026-09-20_SUITE_COMPLETA_TRAS_VERIFICACION.txt` (resultado completo).

---

## DIFERENCIA CON EL COMMIT GPT `ddcb09b9`

| Aspecto | Rama GPT remota (`ddcb09b9`) | Esta rama (`hermes/evidencia-ict-estado-real-20260920`) |
|---|---|---|
| Fallos de causalidad | 9 fallos (7 de causalidad + 2 de gating) | 0 fallos |
| Commits | `ddcb09b9`, `7822ead0`, `6d083590`, `8945745f`, etc. (ORIGINALES del GPT, con bugs) | `b277f7c9`, `5e10b10f`, `b690c9d0`, `ab2e38f8`, `7982d916` (REBASADOS/REWRITOS, con corrección incluida) |
| Corrección de causalidad | NO incluida (es el commit `79b71eb1` de Hermes) | INCLUIDA (en los commits heredados reescritos) |
| Pruebas de regresión | NO incluye las pruebas H7/OE-05/OE-10/OE-11 | INCLUIDAS (mismas que `79b71eb1`) |

**Nota:** Los commits heredados (`b277f7c9`, etc.) NO son los mismos SHA que los commits originales del GPT (`ddcb09b9`, etc.). Son versiones REBASADAS/REWRITOS que incluyen la corrección de causalidad (equivalente al commit Hermes `79b71eb1`). Por eso la suite en esta rama da 0 fallos.

---

## PUBLICACIÓN

- **Autorizado:** push a `origin/hermes/evidencia-ict-estado-real-20260920` (rama NUEVA, sin conflictos con `origin/hermes/evidencia-ict-replay-pass-20260920` ni `origin/gpt/ict-causal-replay-20260920`).
- **NO autorizado:** modificar `origin/main`, `origin/gpt/ict-causal-replay-20260920` (ni sus PRs), ni `origin/hermes/evidencia-ict-replay-pass-20260920`.
- **SHA remoto a verificar después del push:** ver `git rev-parse HEAD` en esta rama local, y `git ls-remote origin refs/heads/hermes/evidencia-ict-estado-real-20260920` después del push.

---

## AUDITORÍA INDEPENDIENTE (VIGIL)

- **Estado:** EN CURSO (mensaje enviado a @vigil, respuesta pendiente).
- **Criterios de auditoría:** ver mensaje enviado (criterios 1-5 del worklog de evidencia).
- **Veredicto:** pendiente (no incluido en esta publicación).
- **Cómo se incluye:** cuando llegue el veredicto de Vigil, se añade un nuevo commit con el dictamen y se hace push.

---

## LO QUE NO SE INCLUYE

- **Dictamen de Vigil:** pendiente (auditoría EN CURSO).
- **Artefactos del commit GPT `ddcb09b9`:** NO se incluyen aquí (existen en `origin/gpt/ict-causal-replay-20260920`). Esta publicación es EVIDENCIA DE QUE LOS 7 FALLOS ESTÁN RESUELTOS EN ESTA RAMA, no reproducción del commit GPT.
- **Artefactos del commit Hermes `79b71eb1`:** NO se incluyen aquí (existen en `origin/hermes/evidencia-ict-replay-pass-20260920`). Esta publicación es EVALUACIÓN INDEPENDIENTE de que los 7 fallos están resueltos, no reproducción del commit Hermes.

---

**Proximo paso:** cuando llegue el veredicto de Vigil, anexar al archivo de evidencia y hacer commit + push del dictamen.
