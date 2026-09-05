# Bitácora — Spec AI Outcome Classifier v2

**Fecha:** 2026-09-05
**AGENTE:** sdd-spec (executor)
**DEPARTAMENTO:** D3 IA, con D4 Datos y D5 Assurance
**TAREA:** Escribir la especificación delta para el reentrenamiento del
clasificador de outcomes sobre el funnel canónico del engine (`ai-outcome-v2`).

## STATUS

**COMPLETED** (fase spec; siguiente: design)

## EVIDENCIA

- Especificación técnica precisa y testeable: `ai_outcome_v2_adapter.py` consume
  exclusivamente `engine/episodes.py` (Episodes/FunnelRecords/rejections), los
  reason codes de rechazo se preservan en el dataset (nunca se descartan).
- Contratos de features A–F con listas exactas, tipos y cardinalidad; set F
  define el encoding tri-state de `allow_long`/`allow_short` como TRES columnas
  one-hot (ALLOW/BLOCK/NO_OPINION), prohibiendo `bool(None)->False`. Se citan
  las trampas de colapso NULL: `outcome_classifier.py:139`,
  `engine/plan.py:68` (`fillna(False)`), `wyckoff_intraday_diagnostic_train.py:112-117`.
- Dataset v2: schema campo a campo con regla de causalidad (features observables
  en `time <= event_time`; `label_available_time > event_time`; `can_trade=false`).
- Target `label_end_12` congelado idéntico al baseline (12 velas M15, close
  firmado vs mediana del rango de las 20 velas previas; empates -> failure).
- Splits cronológicos exactos 2006-01-01→2008-06-30 /
  2008-07-01→2009-06-30 / 2009-07-01→2010-12-31, sin futuro en training.
- Gates G0–G13 con check exacto, artefacto de evidencia y acción de fallo;
  G6 (NULL tercio estado) exige test automático de supervivencia
  snapshot→funnel→dataset→trainer; G8 define el test de horizonte causal
  (FULL vs PREFIX idénticos); G9 define el scan de whitelist de campos
  prohibidos.
- Igualdad de experimento A–F y tabla fija de comparación vs baseline con
  clasificación final en una de seis categorías.
- Restricciones: `can_trade=false`, no MT5, no modificación de engine, no
  optimización circular, no push, sin `TRAINING_ELIGIBLE`, sin lenguaje "edge".

## ARCHIVOS

- `.hermes/plans/2026-09-05_AI_OUTCOME_V2_SPEC.md` (nuevo)
- `docs/planificacion/SDD_AI_OUTCOME_CLASSIFIER_V1.md` (se añadió §5 v2; v1 intacta)
- `.hermes/plans/2026-09-05_AI_OUTCOME_V2_PROPOSAL.md` (referencia, no modificado)

## ENGRAM

- Espec persistida en Engram (topic `sdd/ai-outcome-v2/spec`, project ict2.0).

## RIESGOS

- El funnel del engine puede producir menos filas que el baseline (gates más
  estrictos); aceptado (calidad sobre cantidad), se reportará el conteo.
- Algunos segmentos de análisis per-celda pueden quedar con N<30; se reporta y
  marca, no se fabrican celdas.
- Provenance bloqueada -> no se alcanzará `TRAINING_ELIGIBLE`; la corrida queda
  `DIAGNOSTIC_ONLY`.

## SIGUIENTE ACCIÓN

Fase de diseño (sdd-design): detallar estructuras y firmas del adapter,
materializador v2, runner de ablación y evaluador.
