# Dictamen final — TensorFlow AI Outcome v1.002

**Fecha:** 2026-09-15  
**Run:** `tf_outcome_v1_002`  
**Estado:** `REVIEW`  
**Alcance:** diagnostico local, `shadow_mode=true`, `can_trade=false`  
**Artefactos locales:** `data/ml/tensorflow/tf_outcome_v1_002/`

## Resumen

Se continuo el trabajo dejado por Hermes sin sobrescribir `tf_outcome_v1_001`.
La nueva corrida usa el corpus combinado `SEQ_CTX_01_CANONICAL_BOS.jsonl` +
`SEQ_CTX_01_LITE.jsonl`, corrige `idx_to_label`, registra baseline,
distribucion de clases, calibracion, abstencion y drift por ano.

El flujo TensorFlow queda mecanicamente completo, pero no es PASS cientifico ni
`TRAINING_ELIGIBLE`. El resultado honesto es `REVIEW`.

## Evidencia principal

| Campo | Resultado |
| --- | --- |
| TRAIN | 120 eventos |
| VALIDATION | 96 eventos |
| TEST_OOS | 76 eventos |
| Baseline OOS accuracy | 0.2632 |
| TensorFlow OOS accuracy | 0.4474 |
| TensorFlow OOS log_loss | 1.0893 |
| TensorFlow OOS Brier | 0.6583 |
| ECE OOS | 0.0878 |
| `failure` OOS support | 26 |
| `failure` OOS recall | 0.0769 |
| `failure` OOS F1 | 0.1290 |

## Antes vs ahora

### Antes: `tf_outcome_v1_001`

- Entreno solo con `SEQ_CTX_01_CANONICAL_BOS.jsonl` (100 eventos).
- `idx_to_label` estaba invertido en `feature_schema.json`.
- `failure` colapso completamente: precision/recall/F1 = 0.
- El OOS era muy pequeno: 20 eventos.
- FULL/PREFIX estricto quedo en `FAIL` en el artefacto dejado por Hermes.

### Ahora: `tf_outcome_v1_002`

- Usa `SEQ_CTX_01_CANONICAL_BOS.jsonl` + `SEQ_CTX_01_LITE.jsonl` (292 eventos).
- `feature_schema.json` corrige `idx_to_label` como indice -> etiqueta.
- El preflight de contrato persistido pasa:
  - campos requeridos `PASS`;
  - `event_id` unico `PASS`;
  - `can_trade=false` `PASS`;
  - labels conocidos `PASS`;
  - `label_not_in_features` `PASS`;
  - splits temporales ordenados `PASS`.
- El modelo ya no colapsa completamente `failure`, pero su recall sigue bajo.
- La clase `failure` en TEST_OOS tiene n=26, menor que el umbral interpretativo
  n>=30.

## Limitaciones y bloqueo

La corrida queda en `REVIEW`, no `PASS`, por estas razones:

1. `failure` no esta resuelto: recall OOS 0.0769 y F1 0.1290.
2. `failure` tiene soporte OOS de 26, por debajo de n>=30.
3. El preflight nuevo verifica contrato PIT persistido, pero no reemplaza una
   reproduccion completa del productor FULL/PREFIX desde datos fuente.
4. Los artefactos bajo `data/` estan ignorados por Git; son evidencia local,
   no una entrega versionada completa por si solos.

## Veredicto

```text
TENSORFLOW_V1_002 = REVIEW
TRAINING_PIPELINE = COMPLETADO MECANICAMENTE
SCIENTIFIC_PASS = NO
TRAINING_ELIGIBLE = NO
EDGE = NO DEMOSTRADO
SHADOW_MODE = true
CAN_TRADE = false
```

## Siguiente trabajo

1. Reproducir el productor `SEQ_CTX_01` desde el generador original y emitir
   FULL/PREFIX real de productor, no solo preflight de artefacto persistido.
2. Aumentar soporte de `failure` o aceptar formalmente que el corpus actual no
   alcanza n>=30 en esa clase OOS.
3. Probar una v1.003 solo si el gate causal del productor queda certificado:
   focalizar `failure` con features adicionales causales, sin tocar HOLDOUT
   para ajustar.
4. Registrar los artefactos relevantes fuera de `data/` o definir una politica
   explicita para versionar evidencia ML ignorada.

## Confirmaciones

- No se modificaron datasets fuente.
- No se descargo informacion nueva.
- No se activo MT5, DEMO, paper ni produccion.
- No se cambio `can_trade=false`.
- No hay autorizacion de trading ni promocion.
