# Bitácora de Hermes — Corrección y validación replay causal H4/M15

**Perfil:** Atlas (CEO operativo)  
**Misión:** Corregir los 7 fallos restantes y publicar evidencia nueva  

---

## 2026-09-20 — Ejecución de corrección

### Análisis de los 7 fallos

** falls 1-6 (tests H7, H8, OE06, OE10, OE11):**
- Causa: timestamps incoherentes en pruebas unitarias
- `_ob(anchor=10)` crea objeto con `creation_time=10:00`
- Las pruebas enviaban barras a las 01:00, 02:00, 00:30 — ANTERIORES al nacimiento
- Solución: corregir timestamps de las pruebas para que sean posteriores a las 10:00
- Esto respeta el contrato: no se aceptan barras anteriores al nacimiento

** fallo 7 (test_object_invalidated_after_T_available_in_prior_snapshot):**
- Causa: `_record_transition` no guardaba snapshot al registrar transición
- `projection_at(T)` no reflejaba el estado correcto después de una transición
- Solución: `_record_transition` ahora guarda snapshot cuando `prev != new`
- Esto respeta el contrato: transición registrada → proyección coherente

** fallo adicional (no contado en los 7 originales):**
- `_is_out_of_order` no rechazaba cuando `bar_time > last_time` pero `bar_idx < last_idx`
- Esto era un bug de causalidad real en el código de producción
- Solución: rechazar cuando `bar_idx < last_idx` independientemente del tiempo
- Esto respeta el contrato: OUT_OF_ORDER por índice cronológico

### Correcciones de código en engine/market_state.py

1. `_record_transition`: +11 líneas para guardar snapshot automático
2. `_is_out_of_order`: corrección de lógica para rechazar por índice menor

### Correcciones en tests/test_integridad_causal_h6_h9.py

- 6 pruebas con timestamps corregidos (01:00 → 11:00, 02:00 → 11:00, etc.)
- Docstrings actualizados para documentar los timestamps usados

### Ejecución de validación

**Pruebas focales de replay:** 18/18 PASS ✅  
**Suite completa:** 855 passed, 1 skipped, 0 failed ✅ (era 848 passed, 7 failed)  
**Verificador A/B:** ambos PASS_H4_M15_PIT_PILOT ✅ (sin cambios vs versión anterior)

### Auditoría independiente

**AUDITORÍA VIGIL = NO EJECUTADA**
- Vigil existe como perfil pero no tiene sesión activa ni skill delegable
- No fue posible ejecutar auditoría automatizada

### Publicación

- Commits creados en `hermes/evidencia-ict-replay-pass-20260920`
- SHA a confirmar después del push
