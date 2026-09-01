# Contrato — IA de outcomes ICT v1

**Estado:** NORMATIVO PARA IMPLEMENTACIÓN LOCAL; ENTRENAMIENTO CONDICIONADO
**Fecha:** 2026-08-31
**Objetivo:** clasificar un evento ICT histórico como `continuation`,
`reversal` o `failure` sin convertirlo en señal ni orden.

## 1. Plan de datos

El entrenamiento de investigación usa exclusivamente un `DatasetSnapshot`
certificado del plano histórico (Dukascopy). El parquet operativo de MT5 no se
usa para entrenar este modelo: MT5 alimentará una evaluación futura en vivo
`Shadow Mode`, con los pesos ya congelados.

## 2. Target y features v1

- Target inicial: `label_end_6`. El horizonte no se elige después de observar
  resultados; cambiarlo exige otro pre-registro.
- Clases fijas: `continuation`, `reversal`, `failure`.
- Features permitidas: `direction`, `sequence_depth`, `context_bucket`,
  `h1_alignment`, `d1_bias`, `h4_location` y presencia de etapas de secuencia.
- Todas las features deben existir en `features_at_t` o derivarse de él y ser
  observables con `time <= event_time`.
- Se prohíben labels, outcomes futuros, PnL, entry, SL, TP, OTE y cualquier
  dato operativo dentro de las features.

## 3. Entrenamiento

La implementación v1 es `deterministic_multinomial_softmax`: semilla fija,
normalización calculada solo con TRAIN, ajuste solo con TRAIN y evaluación
separada en VALIDATION y TEST/OOS. El artefacto registra snapshot, hashes,
commit, schema, features, clases, seed y métricas.

El entrenador exige simultáneamente:

1. `DatasetSnapshot` íntegro y manifest `verdict=PASS`.
2. Gate causal FULL/PREFIX y gates temporales del experimento en `PASS`.
3. Autorización científica explícita:
   `status=PASS`, `verdict=TRAINING_ELIGIBLE` y `dataset_hash` coincidente.
4. Mínimos de filas y soporte de las tres clases en TRAIN.
5. `can_trade=false` en todas las filas.

Si falta cualquiera, el resultado es `BLOCKED`; no se relaja el umbral ni se
rellenan datos. El experimento actual `EXP-SEQ-CTX-01` no cumple aún el punto
3 porque cerró como `OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`.

## 4. Artefacto e inferencia

La predicción devuelve probabilidades, confianza, clase, lineage y resultado
INF-7 (`ACCEPT`, `REVIEW` o `ABSTAIN`). Siempre incluye:

```text
shadow_mode=true
can_trade=false
```

Una predicción `ACCEPT` significa únicamente que pasó la política de
confianza/dominio; nunca significa comprar, vender o enviar una orden.

## 5. Gates de promoción

La v1 no promueve modelos. Antes de considerar un candidato para Shadow Mode
con datos MT5 deben existir: evaluación OOS suficiente, comparación contra un
baseline, calibración INF-6, dominio conocido/drift INF-8, abstención INF-7,
revisión independiente y aprobación explícita del cliente. La operación real
requiere un contrato separado.
