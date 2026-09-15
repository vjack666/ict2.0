# Dictamen de apertura — Failure Anatomy Learning v1

**Fecha:** 2026-09-15  
**Estado:** `OPENED`  
**Relacion:** continuacion separada de `tf_outcome_v1_003`  
**Politica:** `can_trade=false`, `shadow_mode=true`  
**Alcance:** abrir una nueva linea de aprendizaje para estudiar fallos antes de
fusionarla con la red de outcome existente.

## Motivo

El entrenamiento `tf_outcome_v1_003` completo un ciclo neural con datos
grabados existentes y mejoro la deteccion de `failure`, pero el fallo sigue
siendo la clase mas debil:

```text
failure support = 26
failure precision = 0.3000
failure recall = 0.2308
failure F1 = 0.2609
status = REVIEW
```

Por eso, el siguiente aprendizaje no debe ser solo aumentar capacidad del mismo
clasificador. La nueva linea debe estudiar especificamente la anatomia del
fallo: que sintomas existian antes de que una secuencia terminara en
`failure`.

## Nueva pregunta de aprendizaje

```text
Que riesgo de fallo tiene esta secuencia y que factores causales lo explican?
```

Esta pregunta queda separada de:

```text
Que outcome final es mas probable: continuation, reversal o failure?
```

## Decision

Se abre `failure_anatomy_v1` como linea independiente, con union futura
diferida hacia `tf_outcome_v1_003` o una futura `tf_outcome_v1_004`.

Forma de union recomendada:

```text
outcome_probs_v1_003 + failure_risk_v1 -> meta_calibrator_shadow
```

La union no se ejecuta ahora. Primero se exige procedencia, no leakage,
calibracion y evidencia OOS suficiente.

## Veredicto

```text
LINE_OPENED = YES
TRAINING_STARTED = NO
MERGE_STARTED = NO
SCIENTIFIC_PASS = NO
TRADING_AUTHORIZATION = NO
CAN_TRADE = false
```

## Riesgos

- `failure` todavia tiene soporte OOS bajo.
- Las causas candidatas deben ser observables antes del resultado.
- Si la taxonomia se define despues de mirar OOS, puede introducir sesgo.
- Una mejora de recall no equivale a edge economico.

## Siguiente accion

1. Crear `FAILURE_TAXONOMY_V1`.
2. Materializar `failure_anatomy_v1` con hashes y split congelado.
3. Entrenar `failure_risk_v1` como modelo binario diagnostico.
4. Auditar no leakage y calibracion.
5. Solo despues, probar fusion tardia con `tf_outcome_v1_003`.
