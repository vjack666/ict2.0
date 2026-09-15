# Bitacora — TensorFlow AI Outcome v1.002

**Fecha:** 2026-09-15  
**Responsable:** Codex / CEO operativo  
**Origen:** continuacion del trabajo dejado por Hermes en `tf_outcome_v1_001`  
**Estado:** `REVIEW` — flujo completo mecanicamente, sin PASS cientifico.

## Que se hizo

- Se audito el estado dejado por Hermes:
  - trainer TensorFlow v1.001;
  - artefactos `tf_outcome_v1_001`;
  - scripts de auditoria T1-B/T1-C/T1-D;
  - reporte T1 de corpus.
- Se corrigio `scripts/lab/experiments/t1_verify_corpus.py` para apuntar al root
  real del repositorio y generar el reporte en `reports/audits/experiments/ai/`.
- Se creo `scripts/lab/experiments/train_tensorflow_outcome_v1_002.py`.
- Se ejecuto una nueva corrida aislada:
  - `data/ml/tensorflow/tf_outcome_v1_002/`;
  - corpus combinado `CANONICAL_BOS + LITE`;
  - baseline, preflight, feature schema, entrenamiento, OOS, calibracion,
    abstencion, drift y reporte.
- Se creo el dictamen:
  - `reports/audits/experiments/ai/tensorflow_v1_002_final_dictamen.md`.

## Resultado

```text
TRAIN = 120
VALIDATION = 96
TEST_OOS = 76
baseline_accuracy = 0.2632
model_accuracy = 0.4474
model_log_loss = 1.0893
failure_support_oos = 26
failure_recall_oos = 0.0769
status = REVIEW
```

## Decision

La ejecucion queda completada en sentido mecanico, pero no se declara PASS:

- `failure` ya no esta totalmente colapsada, pero sigue muy debil.
- `failure` OOS tiene n=26, por debajo del umbral interpretativo n>=30.
- El preflight verifica contrato PIT persistido, no una reproduccion completa
  FULL/PREFIX del productor original.

## Limites respetados

- No se modificaron datasets fuente.
- No se descargo data nueva.
- No se activo MT5 ni ejecucion.
- No se cambio `can_trade=false`.
- No hay promocion ni autorizacion de trading.

## Siguiente accion

Certificar el productor `SEQ_CTX_01` con FULL/PREFIX reproducido desde el
generador original o aceptar formalmente que el corpus actual queda en REVIEW
por soporte OOS insuficiente en `failure`.
