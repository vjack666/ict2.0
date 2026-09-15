# Dictamen — TensorFlow AI Outcome v1.003

**Fecha:** 2026-09-15  
**Run:** `tf_outcome_v1_003`  
**Estado:** `REVIEW`  
**Alcance:** entrenamiento neural diagnostico con datos grabados existentes  
**Artefactos locales:** `data/ml/tensorflow/tf_outcome_v1_003/`  
**Politica:** `can_trade=false`, `shadow_mode=true`

## Que se entreno

Se entreno una red neuronal TensorFlow sobre la data ya grabada de `SEQ_CTX_01`,
sin modificar datasets fuente:

- `SEQ_CTX_01_CANONICAL_BOS.jsonl`
- `SEQ_CTX_01_LITE.jsonl`

La v1.003 amplio la matriz de features respecto a v1.002:

- features numericas: `sequence_direction`, `sequence_depth`, `allow_long`,
  `allow_short`;
- categoricas one-hot ajustadas solo con TRAIN: `structure_mode`,
  `context_bucket`, `d1_bias`, `h1_alignment`, `h4_location`,
  `direction_hint`, `h1_bias`, `h4_bias`;
- indicadores binarios de etapas de secuencia vistas en TRAIN.

HOLDOUT se uso solo para evaluacion final.

## Resultado comparativo

| Run | Corpus | OOS accuracy | OOS log_loss | `failure` recall | `failure` F1 | Estado |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| v1.001 | CANONICAL_BOS | 0.4500 | 1.0821 | 0.0000 | 0.0000 | BLOCKED/REVIEW |
| v1.002 | CANONICAL_BOS + LITE | 0.4474 | 1.0893 | 0.0769 | 0.1290 | REVIEW |
| v1.003 | CANONICAL_BOS + LITE + richer features | 0.5132 | 1.0199 | 0.2308 | 0.2609 | REVIEW |

La v1.003 mejora la capacidad de detectar `failure`, pero todavia no alcanza
un PASS cientifico.

## Metricas v1.003

```text
TEST_OOS = 76
accuracy = 0.5132
balanced_accuracy = 0.5158
log_loss = 1.0199
brier = 0.5964
ECE = 0.1493

continuation: support=30 precision=0.6452 recall=0.6667 f1=0.6557
reversal:     support=20 precision=0.5200 recall=0.6500 f1=0.5778
failure:      support=26 precision=0.3000 recall=0.2308 f1=0.2609
```

## Veredicto

```text
NEURAL_TRAINING = COMPLETED
MODEL_STATUS = REVIEW
SCIENTIFIC_PASS = NO
TRAINING_ELIGIBLE = NO
EDGE = NO DEMOSTRADO
CAN_TRADE = false
```

El entrenamiento cumple el objetivo de poner a trabajar la red con la data
grabada y obtener aprendizaje medible. No autoriza trading ni promocion porque:

1. `failure` OOS tiene soporte 26, menor que n>=30.
2. `failure` mejora, pero sigue debil frente a continuation/reversal.
3. Falta reproducir FULL/PREFIX desde el productor original, no solo validar el
   artefacto persistido.

## Siguiente paso recomendado

Para continuar sin fabricar evidencia:

1. Reproducir `SEQ_CTX_01` desde el generador original y cerrar FULL/PREFIX real.
2. Si se permite otra iteracion, crear v1.004 con foco en `failure`:
   arquitectura conservadora, misma division temporal, sin tocar HOLDOUT para
   ajustar.
3. Si el soporte de `failure` sigue por debajo de 30, mantener `REVIEW` aunque
   el modelo mejore.

## Confirmaciones

- No se modificaron datasets fuente.
- No se descargaron datos.
- No se activo MT5 ni ningun entorno operativo.
- No se cambio `can_trade=false`.
- No se promueve a produccion.
