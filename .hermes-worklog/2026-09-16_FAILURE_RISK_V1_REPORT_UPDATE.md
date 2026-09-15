# Actualización de reportes neural_training_progress_v1 — failure_risk_v1 integrado

**Fecha:** 2026-09-16
**Motivo:** Usuario pidió actualizar los reportes para incluir el modelo ya entrenado.

## Cambios realizados

### Reporte técnico `neural_training_progress_v1.md`
- Agregada sección completa de `failure_risk_v1` con configuración, métricas TRAIN/VALIDATION/OOS.
- Añadida comparativa contra baselines: majority class, prevalence, driver count, logistic regression.
- Aclarada explícitamente la comparación analítica vs fusión.
- Marcado como REVIEW, no PASS.
- Documentado sobreajuste, calibración deficiente y PR-AUC inferior al baseline.

### Reporte simple `neural_training_progress_v1_simple.md`
- Corregidos errores de redacción:
  - "algún fallo" en lugar de "algún fallo" (typo corregido a "algún fallo").
  - "termirar la cruzar" corregido a "terminar la cruzada".
  - "ventoso" → contexto clarificado.
- Eliminada repetición redundante "no trading no trading no trading".
- Añadida explicación de sobreajuste, mala calibración y por qué no pasa a PASS.
- Añadida explicación del significado analítico de reconocer failures que v1.003 no reconocía.
- Reflejado estado actual: REVIEW.

### JSON de datos `neural_training_progress_v1.json`
- Actualizado con datos reales de `failure_risk_v1` desde `training_record.json` y `comparison.json`.
- Incluidos baselines en OOS.
- Añadida sección `failure_risk_v1_vs_baselines` con deltas.

### .hermes-index.md
- Actualizada sección de documentación reciente.

## Estado
- Archivos modificados: 3 reportes + índice.
- `can_trade=false` intacto.
- Sin fusión con v1.003.
- Sin cambios en modelo ni dataset.
