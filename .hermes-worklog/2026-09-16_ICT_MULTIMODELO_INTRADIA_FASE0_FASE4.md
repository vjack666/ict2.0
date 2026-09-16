# Bitacora - ICT Multimodelo Intradia v1

**Fecha:** 2026-09-16
**Estado:** `MORE_DETERMINISTIC_WORK_REQUIRED`
**Modo:** investigacion local, solo diagnostico, sin ordenes.

## Alcance completado

- Inventario de contratos y detectores existentes para PO3, Turtle Soup,
  Silver Bullet, killzone, setup grammar, execution y PASS_EDGE.
- Nuevo plan multimodelo, contrato comun de identidad y gate de frecuencia.
- Cierre reproducible de `EXECUTION_CALIBRATION_PREFLIGHT_V2` con JSON y MD.
- Auditoria paralela de los 286 casos ABSTAIN/REJECT sin editar labels.
- Unificacion de evaluacion temporal en `engine/killzone.py` y pruebas DST.

## Evidencia

- Fuentes declaradas: 60/60 cargadas; decision_time en rango para 292/292.
- `fine_execution()` M15: 0/292 con 4 barras; con 30 barras, TRAIN 119/120,
  VALIDATION 96/96 y TEST_OOS 76/76. No hubo violaciones causales.
- `sweep_ts` materializado: 0/292; la ejecucion es fallback de swing, no SL
  anclado al sweep.
- PASS: 6 filas, 5 eventos deduplicados, 1036 semanas calendario,
  0.004826 eventos/semana. No alcanza el gate de frecuencia.
- Reclasificacion estructural: PO3 27; Turtle Soup 2; Silver Bullet 1 sin
  conteo certificado por conflicto de horario documental.

## Decisiones

- La meta 2-3 semanal se trata como medicion; no se modificaron reglas para
  elevar la frecuencia.
- Las coincidencias no cambian `grammar_labels` ni se convierten en PASS.
- Silver Bullet queda en `REVIEW_SCHEDULE_CONTRACT` hasta unificar sus horas
  exactas entre los documentos locales.

## Siguiente accion

Implementar el generador determinista comun bajo
`ICT_MULTIMODEL_CANDIDATE_V1`, materializar `sweep_ts` y geometria de
ejecucion, luego correr `FREQ_GATE_2_3_WEEKLY` por familia y combinado.
