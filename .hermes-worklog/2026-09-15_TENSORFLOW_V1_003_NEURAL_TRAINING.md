# Bitacora — TensorFlow AI Outcome v1.003 neural training

**Fecha:** 2026-09-15  
**Responsable:** Codex / D3 IA  
**Solicitud:** entrenar redes neuronales con la data grabada disponible.  
**Estado:** `REVIEW` — entrenamiento completado, sin PASS cientifico.

## Que se hizo

- Se creo `scripts/lab/experiments/train_tensorflow_outcome_v1_003.py`.
- Se entreno una red TensorFlow sobre `SEQ_CTX_01_CANONICAL_BOS + LITE`.
- Se agregaron features causales persistidas mas ricas:
  - constraints;
  - modo canonical/lite;
  - capas HTF;
  - context bucket;
  - etapas de secuencia.
- Se guardaron artefactos locales en `data/ml/tensorflow/tf_outcome_v1_003/`.
- Se documento el dictamen en
  `reports/audits/experiments/ai/tensorflow_v1_003_neural_training.md`.

## Resultado

```text
OOS accuracy = 0.5132
OOS log_loss = 1.0199
failure recall = 0.2308
failure F1 = 0.2609
failure support = 26
status = REVIEW
```

## Decision

La red aprendio mas que v1.002 y dejo de tratar `failure` como clase casi muda,
pero no hay PASS porque `failure` tiene soporte OOS menor de 30 y el recall
sigue bajo.

## Limites

- `can_trade=false`.
- Sin MT5, sin DEMO, sin paper, sin ordenes.
- Sin modificacion de datasets fuente.
- Sin promocion ni edge declarado.

## Siguiente accion

Cerrar FULL/PREFIX desde el productor original o aceptar formalmente que el
corpus actual queda en `REVIEW` aunque la red muestre aprendizaje.
