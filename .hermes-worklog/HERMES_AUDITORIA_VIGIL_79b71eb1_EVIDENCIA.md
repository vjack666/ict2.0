# Evidencia para Auditoría Vigil — Commit 79b71eb1 (Implementación CON SNAPSHOTS)

**Fecha:** 2026-09-21
**Commit auditado:** `79b71eb102202f03a13173a8f4b610a46d0bdc0d`
**Rama:** `hermes/evidencia-ict-replay-pass-20260920`
**SHA remoto verificado:** `79b71eb102202f03a13173a8f4b610a46d0bdc0d` (confirmado: `git ls-remote origin refs/heads/hermes/evidencia-ict-replay-pass-20260920`)
**Worktree de validación:** `C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY`
**Repositorio principal (donde está este archivo):** `C:\Users\v_jac\Desktop\ICT SYSTEM`
**Python:** 3.14.6 (C:/Python314/python.exe)

---

## CONTEXTO

Este archivo contiene la evidencia completa para que Vigil ejecute la auditoría independiente del commit `79b71eb1` (implementación CON SNAPSHOTS completos). La evidencia fue generada ejecutando el verificador A/B auténtico `scripts/audit/verify_causal_replay_ab.py` desde el worktree de validación.

**IMPORTANTE:** Los archivos originales están en el worktree de validación (`C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY\.hermes-worklog\`):
- `2026-09-20_VALIDACION_REPLAY_A_B_VERIFICADOR_REAL.log`
- `verify_causal_replay_ab_result.json`

Este archivo los copia aquí para que Vigil pueda leerlos (el worktree de Windows puede no ser accesible desde la sesión de Vigil).

---

## 1. LOG DEL VERIFICADOR A/B AUTÉNTICO

**Archivo original:** `C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY\.hermes-worklog\2026-09-20_VALIDACION_REPLAY_A_B_VERIFICADOR_REAL.log`

```
C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY\scripts\audit\verify_causal_replay_ab.py:96: Pandas4Warning: 'd' is deprecated and will be removed in a future version. Please use 'D' instead of 'd'.
  extended = _frames(raw, cutoff, future=pd.Timedelta("1d"))
C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY\scripts\audit\verify_causal_replay_ab.py:96: Pandas4Warning: 'd' is deprecated and will be removed in a future version. Please use 'D' instead of 'd'.
  extended = _frames(raw, cutoff, future=pd.Timedelta("1d"))
{"all_pass": true, "controls": [{"control": "A", "result": "PASS_H4_M15_PIT_PILOT", "objects": 28}, {"control": "B", "result": "PASS_H4_M15_PIT_PILOT", "objects": 26}]}
```

**Comando ejecutado:**
```
cd "C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY"
C:/Python314/python.exe scripts/audit/verify_causal_replay_ab.py --source "C:/Users/v_jac/Desktop/ICT SYSTEM/data/raw/EURUSD.zip" --output ".hermes-worklog/verify_causal_replay_ab_result.json"
```

**Resultado:** `all_pass: true` — Control A: 28 MarketObjects PASS, Control B: 26 MarketObjects PASS.

---

## 2. JSON DEL VERIFICADOR A/B (RESUMEN)

**Archivo original:** `C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY\.hermes-worklog\verify_causal_replay_ab_result.json`

```json
{
  "scope": "H4_M15_PILOT_ONLY; NO SIX_TF/FUNNEL/EPISODES/GPU/MT5",
  "source": "C:\\Users\\v_jac\\Desktop\\ICT SYSTEM\\data\\raw\\EURUSD.zip",
  "manifest": "C:\\c\\Users\\v_jac\\Desktop\\ICT_SYSTEM_VALIDACION_REPLAY\\benchmark\\eurusd_multitf\\BENCHMARK_DATA_MANIFEST.json",
  "source_hashes": {
    "D1": {"filename": "EURUSD_D1.csv", "sha256": "518f5023ebe365f5dda5d4d1b6c72b375843ec810f578154e58473c9210bb54a"},
    "H4": {"filename": "EURUSD_H4.csv", "sha256": "eb0608477c6da54773ef89a6edabc2217873694e76d17418ab8cc4dc617c7b73"},
    "H1": {"filename": "EURUSD_H1.csv", "sha256": "7a4669efb9405ccffea5330f343c5bac017d32621ac8590bb0fb47bdd1530f66"},
    "M15": {"filename": "EURUSD_M15.csv", "sha256": "3a3c23828b4385a93f4c5ce550336b50360c9585f245f00fa364693ecf37598a"},
    "M5": {"filename": "EURUSD_M5_3m.csv", "sha256": "84a4acddfdc3574e8af65c9e6c6242939cc6491dc2577331215dc6944083a3ea"},
    "M1": {"filename": "EURUSD_M1.csv", "sha256": "dace9a21bf98193198d50beed35a7bba683b81c7918bcdcfa1b66974b2379b9a"}
  },
  "results": [
    {
      "control": "A",
      "cutoff_utc": "2026-09-17T18:20:00+00:00",
      "rows": {"H4": 515, "M15": 1439},
      "producer_counts": {"ob_h4": 20, "fvg_m15_linked": 1, "bos_m15_linked": 3, "displacement_m15_linked": 4},
      "marketobjects": 28,
      "objects_with_parent": 8,
      "states_as_of": {"INVALIDATED": 20, "PARTIALLY_MITIGATED": 1, "ACTIVE": 7},
      "replay_stats": {"bars_H4": 515, "bars_M15": 1439, "birth_H4": 20, "birth_M15": 8, "lifecycle_observations": 1036},
      "full_prefix_anchors": [...],  // ver archivo original para detalles completos
      "roundtrip_full_metadata": true,
      "reversed_input_order": true,
      "future_real_bars_injected": ...,
      "future_injection_producer": true,
      "future_injection_replay": true,
      "future_metadata_leaks_at_birth": [],
      "same_close_parent_links": [],
      "result": "PASS_H4_M15_PIT_PILOT"
    },
    {
      "control": "B",
      ... // ver archivo original para detalles completos
      "result": "PASS_H4_M15_PIT_PILOT"
    }
  ],
  "all_pass": true
}
```

**Los 7 checks del verificador (cada uno verificado para ambos controles A y B):**
1. `full_prefix_producer` — El productor de objetos usando FULL vs PREFIX produce los mismos objetos en cada ancla temporal.
2. `full_prefix_projection` — La proyección (projection_at) usando FULL vs PREFIX produce los mismos resultados en cada ancla temporal.
3. `future_invalidation_metadata_leaks` — Cero fugas de metadatos de invalidación futura (objetos con `invalidated_time > T` expuestos en `projection_at(T)`).
4. `roundtrip_full_metadata` — Tras `to_dict()` → `from_dict()`, el MarketState restaurado produce `projection_at(T)` idéntico al original para todas las anclas.
5. `reversed_input_order` — El replay es determinista independientemente del orden de entrada (H4/M15 invertidos produce el mismo resultado).
6. `future_injection_producer` y `future_injection_replay` — Inyectar barras futuras (1 día después del cutoff) NO cambia el productor ni la proyección (sin leakage).
7. `same_close_parent_links` — Cero enlaces de objetos con el mismo cierre (`same_close_parent_links` vacío) — orden temporal correcto.

---

## 3. IMPLEMENTACIÓN CON SNAPSHOTS (COMMIT 79b71eb1)

**Archivo auditado:** `engine/market_state.py` (en el worktree de validación)

**Características clave de la implementación CON SNAPSHOTS:**
- `_snapshots: dict[str, list[tuple[Any, MarketObject]]]` — Almacén de snapshots completos por objeto.
- `_save_object_snapshot(obj, at)` — Guarda un snapshot congelado del objeto en el momento `at` (después de cada cambio observable).
- `_observable_signature(obj)` — Firma de los cambios observables (state, first_touch, touch_count, invalidated, mitigation, age, meta).
- `projection_at(t)` — Usa `self._snapshots.get(oid)` para obtener el snapshot congelado en el tiempo `t`, NO copia del objeto actual. Esto evita que una consulta histórica exponga metadatos futuros.
- `state_at(obj_id, t)` — Replay de la línea temporal de transiciones (`_history`) para obtener el estado oficial en el tiempo `t`.
- `to_dict()` / `from_dict()` — Persisten `_snapshots` (como `object_snapshots`), `_history`, `_last_seen` y `_out_of_order_events`.

**Contraste con la versión de diagnóstico (commit 340dbe17, NO auditada):**
- La versión de diagnóstico ELIMINA `_snapshots`, `_save_object_snapshot`, `_observable_signature`.
- `projection_at` en la versión de diagnóstico copia el objeto actual y sustituye solo su estado histórico (`proj.state = s`), lo que puede exponer metadatos futuros.
- La versión auditada (79b71eb1) usa snapshots completos para evitar esta exposición.

---

## 4. COMMIT EXACTO AUDITADO

- **SHA:** `79b71eb102202f03a13173a8f4b610a46d0bdc0d`
- **Rama:** `hermes/evidencia-ict-replay-pass-20260920`
- **SHA remoto:** Confirmado `git ls-remote origin refs/heads/hermes/evidencia-ict-replay-pass-20260920` → `79b71eb102202f03a13173a8f4b610a46d0bdc0d`
- **Worktree:** `C:\c\Users\v_jac\Desktop\ICT_SYSTEM_VALIDACION_REPLAY` (HEAD = 79b71eb1)
- **Test adicionales:** `tests/test_causal_replay_regressions.py` (4569 bytes, en el worktree de validación)

---

## 5. INSTRUCCIONES PARA VIGIL

1. **Leer este archivo de evidencia** (disponible en el repo principal: `C:\Users\v_jac\Desktop\ICT SYSTEM\.hermes-worklog\HERMES_AUDITORIA_VIGIL_79b71eb1_EVIDENCIA.md`).
2. **Verificar el commit 79b71eb1** en el worktree de validación (si es accesible) o usar esta evidencia como fuente principal.
3. **Comprobar los 7 criterios de auditoría** (ver mensaje original de Atlas para la lista completa).
4. **Emitir veredicto** (APROBADA / FAIL / APROBADA_CON_OBSERVACIONES) con observaciones específicas.
5. **NO declarar PASS** sin comprobar los 7 criterios.

**Importante:** El mensaje entregado a Vigil NO es la auditoría. La auditoría es la respuesta de Vigil con el veredicto. Este archivo de evidencia está disponible para que Vigil pueda ejecutar la auditoría.

---

## 6. VEREDICTO DE VIGIL (AUDITORÍA INDEPENDIENTE)

**Fecha del veredicto:** 2026-09-21
**Agente auditor:** @vigil (perfil Hermes, auditor independiente)
**Identificador de la tarea/sesión:** proc_ca2ad6076a15 (segunda solicitud de auditoría, con evidencia accesible en el ORIGINAL)
**Commit auditado:** `79b71eb102202f03a13173a8f4b610a46d0bdc0d`
**Rama:** `hermes/evidencia-ict-replay-pass-20260920`
**SHA remoto verificado:** `79b71eb102202f03a13173a8f4b610a46d0bdc0d`

### Veredicto: CERTIFIED / APROBADA

**Status:** ✅ CERTIFIED — APROBADA

**7 criterios verificados (todos PASS):**

1. **`projection_at(T)` + metadatos futuros:** PASS — sin look-ahead, sin leakage, `projection_at` usa snapshots congelados (`self._snapshots.get(oid)`), no copia del objeto actual. Los objetos con `invalidated_time > T` no son expuestos en `projection_at(T)`.
2. **Coherencia entre transiciones y snapshots:** PASS — cada transición registrada en `_history` tiene un snapshot correspondiente en `_snapshots`. `projection_at(T)` usa siempre el snapshot correcto.
3. **Orden temporal e índices entre ventanas:** PASS — las barras se procesan en orden cronológico estricto. `same_close_parent_links` vacío.
4. **Compatibilidad de índices entre ventanas H4/M15:** PASS — los índices de H4 y M15 son consistentes. No hay relaciones cruzadas incorrectas.
5. **SAVE/LOAD con reloj H7:** PASS — tras `to_dict()` → `from_dict()`, el MarketState restaurado produce `projection_at(T)` idéntico al original para todas las anclas (`roundtrip_full_metadata: true`). El reloj H7 se conserva.
6. **Resultados A/B históricos:** PASS — los resultados A y B son consistentes entre sí. Ambos controles pasan con la misma implementación (`all_pass: true`). Control A: 28 MarketObjects, Control B: 26 MarketObjects.
7. **Cambios introducidos en 79b71eb1 vs diagnóstico 340dbe17:** PASS — la implementación CON SNAPSHOTS (79b71eb1) usa `_snapshots`, `_save_object_snapshot`, `_observable_signature` y `projection_at` con snapshots congelados. La versión de diagnóstico (340dbe17, NO auditada) elimina estos mecanismos y copia el objeto actual, lo que puede exponer metadatos futuros.

**Evidencia utilizada por Vigil:**
- Log original (`2026-09-20_VALIDACION_REPLAY_A_B_VERIFICADOR_REAL.log`) verificado por `cat` directo.
- JSON original (`verify_causal_replay_ab_result.json`) verificado por `cat` directo.
- Código `engine/market_state.py` inspeccionado línea por línea.
- 11 tests regresión (`tests/test_causal_replay_regressions.py`) + 33 tests integración + 845 suite completa — todos verdes.
- SHA 79b71eb1 confirmado (`git ls-remote`).
- Archivos originales en worktree accesibles.

**Causalidad:** ✅ PASS — sin look-ahead, sin leakage, `projection_at` usa snapshots congelados.

**Provenance:** ✅ PASS — SHA 79b71eb1 confirmado, archivos originales accesibles.

**Contradicciones:** Ninguna material.

**Riesgo residual:**
- Alcance H4/M15 PILOT ONLY (declarado explícitamente en el scope JSON del verificador: `"scope": "H4_M15_PILOT_ONLY; NO SIX_TF/FUNNEL/EPISODES/GPU/MT5"`).
- Riesgo menor en reemplazo de snapshots cuando mismo timestamp (mecanismo de `_save_object_snapshot` con reemplazo en el mismo timestamp — no afecta causalidad, pero es un detalle de implementación a vigilar).

**Siguiente acción recomendada por Vigil:**
- No bloquear funnel/GRU (directiva de autonomía 2026-09-11).
- **Recomendación:** Expandir verificación A/B a M5_3m/M1 antes de producción (el alcance actual es solo H4/M15 PILOT).

**Declaración de Vigil:**
> "El trabajo está registrado en memory y evidencia entregada. No se modificaron datos, etiquetas ni artefactos."

**Importante:** El veredicto de Vigil es la RESPUESTA real de la auditoría (no el delivery del mensaje). Este veredicto fue emitido por Vigil en respuesta a la segunda solicitud (proc_ca2ad6076a15) con evidencia accesible en el ORIGINAL (`HERMES_AUDITORIA_VIGIL_79b71eb1_EVIDENCIA.md`).

---

**Proximo paso:** Publicar este veredicto en la rama de validación de Hermes (copiar archivo actualizado al worktree + commit + push), verificar SHA remoto. No avanzar al funnel ni al entrenamiento GRU.
