# Worklog — Failure Anatomy Learning Line Opened

**Fecha:** 2026-09-15  
**Agente:** Codex  
**Departamento:** D3 CAIO / D6 Research / D5 Assurance  
**Estado:** COMPLETED  
**Modo:** LOCAL_ONLY  
**Politica:** `can_trade=false`

## Solicitud

El usuario pregunto que es lo siguiente que deben aprender las neuronas y pidio
abrir una nueva linea de aprendizaje para despues unirla con la red ya
entrenada.

## Accion ejecutada

Se abrio la linea `failure_anatomy_v1`, separada de `tf_outcome_v1_003`, para
que el sistema aprenda la anatomia del fallo antes de fusionar ese conocimiento
con el clasificador general de outcome.

## Evidencia

- Plan operativo creado:
  `docs/planificacion/PLAN_FAILURE_ANATOMY_LEARNING_V1.md`
- Dictamen de apertura creado:
  `reports/audits/experiments/ai/failure_anatomy_learning_line_v1.md`
- Base de decision: `tf_outcome_v1_003` quedo en `REVIEW`, con mejora en
  `failure` pero soporte OOS bajo.

## Antes

`tf_outcome_v1_003` aprendia tres clases:

```text
continuation
reversal
failure
```

Resultado principal:

```text
accuracy = 0.5132
failure recall = 0.2308
failure F1 = 0.2609
status = REVIEW
```

## Ahora

`failure_anatomy_v1` estudiara una pregunta mas especifica:

```text
Que riesgo de fallo tiene esta secuencia y que factores lo explican?
```

Drivers iniciales:

- conflicto HTF;
- contexto adverso;
- secuencia inmadura;
- restriccion contradictoria;
- debilidad estructural;
- regimen con soporte bajo;
- ambiguedad direccional.

## Fusion futura

La fusion recomendada es tardia:

```text
outcome_probs_v1_003 + failure_risk_v1 -> meta_calibrator_shadow
```

No se ejecuta fusion ni entrenamiento en esta apertura.

## Riesgos y limites

- No hay `SCIENTIFIC_PASS`.
- No se activo trading.
- No se cambio `can_trade=false`.
- No se modificaron datasets fuente.
- La nueva linea requiere taxonomia, materializacion, entrenamiento y auditoria
  antes de unirse a v1.003.

## Siguiente accion

Crear `FAILURE_TAXONOMY_V1` y materializar `failure_anatomy_v1` con evidencia
de procedencia, split congelado y no leakage.
