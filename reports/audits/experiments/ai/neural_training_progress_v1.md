# Reporte Técnico — Avance Entrenamiento IA / TensorFlow

**Fecha:** 2026-09-15
**Commit actual:** `c495efc feat(ai): materialize failure anatomy dataset`
**Entorno:** Python 3.11.15 / TensorFlow 2.21.0 / `.venv`
**Modo:** LOCAL_ONLY
**Política:** `can_trade=false`, `shadow_mode=true`

---

## 1. Resumen ejecutivo

ICT SYSTEM dispone de tres entrenamientos consecutivos de una red TensorFlow para
predicción de *outcome* ICT (`continuation`, `reversal`, `failure`), más una nueva
línea paralela dedicada exclusivamente al estudio de la **anatomía del fallo**.

Estado global:

| Línea | Estado | Nota |
|-------|--------|------|
| `tf_outcome_v1_001` | BLOCKED/REVIEW | colapso total de `failure` |
| `tf_outcome_v1_002` | REVIEW | primer modelo que no colapsa, pero recall bajo |
| `tf_outcome_v1_003` | REVIEW | mejora medible en `failure`, aún insuficiente |
| `failure_anatomy_v1` | READY_FOR_TRAINING_REVIEW | dataset materializado, sin modelo aún |

Conclusión técnica: **hay aprendizaje medible en la línea v1.001→v1.003, pero no
hay PASS científico** porque `failure` sigue con soporte OOS < 30 y recall bajo.

---

## 2. Línea de tiempo

- **2026-09-15:** `tf_outcome_v1_001` entrenado con `SEQ_CTX_01_CANONICAL_BOS.jsonl`
  (100 eventos, 6 features). Resultado: `failure` colapsa. Estado BLOCKED/REVIEW.
- **2026-09-15:** `tf_outcome_v1_002` entrenado con CANONICAL_BOS + LITE (292 eventos).
  Corrige `idx_to_label`, mantiene arquitectura. Resultado: `failure` ya no colapsa
  totalmente, pero recall 0.0769. Estado REVIEW.
- **2026-09-15:** `tf_outcome_v1_003` entrenado, amplía a 41 features, BatchNorm,
  Dropout 0.20/0.10, 96/48 unidades. Resultado: `failure` recall 0.2308. Estado REVIEW.
- **2026-09-15:** Apertura de `failure_anatomy_v1` como línea separada. Contrato
  `FAILURE_TAXONOMY_V1` creado.
- **2026-09-15:** Materialización de `failure_anatomy_v1`. Dataset listo para
  entrenamiento. Estado READY_FOR_TRAINING_REVIEW.

---

## 3. Tabla comparativa de versiones

### 3.1 Métricas v1.001 — BLOCKED/REVIEW

| Métrica | Valor |
|---------|-------|
| accuracy | 0.4500 |
| balanced_accuracy | 0.4259 |
| log_loss | 1.0821 |
| Brier | 0.6431 |
| ECE | 0.0878 |
| failure precision | 0.0000 |
| failure recall | 0.0000 |
| failure F1 | 0.0000 |
| failure support OOS | 7 |
| estado | BLOCKED/REVIEW |

**Observaciones:**
- `idx_to_label` invertido en `feature_schema.json`.
- `failure` colapsó completamente: precision/recall/F1 = 0.
- OOS muy pequeño (20 eventos, 7 failure).

### 3.2 Métricas v1.002 — REVIEW

| Métrica | Valor |
|---------|-------|
| accuracy | 0.4474 |
| balanced_accuracy | 0.4256 |
| log_loss | 1.0893 |
| Brier | 0.6583 |
| ECE | 0.0878 |
| failure precision | 0.4000 |
| failure recall | 0.0769 |
| failure F1 | 0.1290 |
| failure support OOS | 26 |
| estado | REVIEW |

**Observaciones:**
- Corrige `idx_to_label` como índice → etiqueta.
- Usa CANONICAL_BOS + LITE (292 eventos).
- `failure` ya no colapsa completamente, pero recall sigue bajo.
- Soporte OOS failure = 26 < 30.
- FULL/PREFIX no reproducido desde productor original.

### 3.3 Métricas v1.003 — REVIEW

| Métrica | Valor |
|---------|-------|
| accuracy | 0.5132 |
| balanced_accuracy | 0.5158 |
| log_loss | 1.0199 |
| Brier | 0.5964 |
| ECE | 0.1493 |
| failure precision | 0.3000 |
| failure recall | 0.2308 |
| failure F1 | 0.2609 |
| failure support OOS | 26 |
| estado | REVIEW |

**Observaciones:**
- Amplía matriz de features a 41 entradas.
- BatchNorm + Dropout 0.20/0.10 + 96/48 unidades.
- `failure` mejora notablemente vs v1.002.
- Soporte OOS failure sigue en 26 (< 30).
- ECE 0.1493 (calibración moderada).
- Sin reproducción FULL/PREFIX completa desde productor original.

### 3.4 failure_anatomy_v1 — READY_FOR_TRAINING_REVIEW

| Métrica | Valor |
|---------|-------|
| accuracy | NO DISPONIBLE (no entrenado) |
| balanced_accuracy | NO DISPONIBLE |
| log_loss | NO DISPONIBLE |
| Brier | NO DISPONIBLE |
| ECE | NO DISPONIBLE |
| failure precision | NO DISPONIBLE |
| failure recall | NO DISPONIBLE |
| failure F1 | NO DISPONIBLE |
| estado | READY_FOR_TRAINING_REVIEW |

**Dataset materializado:**

| Split | Filas | Failure | Hash |
|-------|-------|---------|------|
| TRAIN | 120 | 25 | `f34cc94cb50be5652ede901ba18e9a9c519834b8717be0750906bb51cf708863` |
| VALIDATION | 96 | 19 | `58e7ea4cc88b772c5734bb77c6096aec6545f46bec6aa5fbd281c9d76604b3ad` |
| TEST_OOS | 76 | 26 | `68e6b1e7a1792d93c6fe49ba49fbf113589d54a3c15c5d4f02ba90b5e3d11695` |

---

## 4. Comparativa de métricas clave

| Versión | accuracy | failure recall | failure F1 | failure support |
|---------|----------|----------------|------------|-----------------|
| v1.001 | 0.4500 | 0.0000 | 0.0000 | 7 |
| v1.002 | 0.4474 | 0.0769 | 0.1290 | 26 |
| v1.003 | 0.5132 | 0.2308 | 0.2609 | 26 |
| failure_anatomy_v1 | pendiente | pendiente | pendiente | 26 |

Mejora absoluta v1.002 → v1.003:
- failure recall: +0.1539
- failure F1: +0.1319
- accuracy: +0.0658

---

## 5. Datasets usados

### 5.1 `SEQ_CTX_01_CANONICAL_BOS.jsonl`

- 100 eventos ICT clasificados.
- 102.8 KB.
- SHA256: `7a1d2f15c1a6d23f8175ab76026845171d9735a29ade477670091ef9eb311ad7`
- Distribución labels: continuation 43, reversal 33, failure 24.
- Splits: DESIGN 36, VALIDATION 44, HOLDOUT 20.
- Symbol: EURUSD únicamente.
- Rango temporal: 2007-07-18 → 2024-09-19.
- Campos: `features_at_t`, `constraints`, `context_inputs`, `context_layers`, `sequence`,
  `sequence_depth`, `direction`, `label_end_6`, `label_end_12`, `label_end_24`, `label_end_48`.

### 5.2 `SEQ_CTX_01_LITE.jsonl`

- 192 eventos ICT clasificados.
- 193.6 KB.
- SHA256: `2229b8a6d45f0658076829b9c13650f12b65254c146c8228ef438bb79655796f`
- Distribución labels: continuation 66, reversal 80, failure 46.
- Splits: DESIGN 84, VALIDATION 52, HOLDOUT 56.
- Symbol: EURUSD únicamente.
- Rango temporal: 2006-01-11 → 2025-11-13.

### 5.3 Corpus combinado usado por v1.002 y v1.003

- Total: 292 eventos.
- TRAIN (DESIGN): 120 eventos.
- VALIDATION: 96 eventos.
- TEST_OOS (HOLDOUT): 76 eventos.
- Failure en TRAIN: 25.
- Failure en VALIDATION: 19.
- Failure en TEST_OOS: 26.

---

## 6. Explicación de los splits

- **TRAIN (DESIGN):** datos que la red ve Durante el entrenamiento. Se usan para
  ajustar los pesos de la red. La red puede ver tantas veces como epocas se
  configuren.

- **VALIDATION:** datos que la red **no** ve durante el entrenamiento. Se usan para
  monitorear si el modelo empieza a sobreajustar y para elegir cuándo detenerlo
  (early stopping). Es una señal de alarma, no de certificación.

- **TEST_OOS (HOLDOUT):** datos **completamente reservados**. Se tocan **una sola vez**
  al final del entrenamiento. Su función es evaluar la generalización honesta. No se
  pueden usar para ajustar arquitectura, elegir features, calibrar thresholds ni tomar
  ninguna decisión que afecte al modelo.

**¿Por qué HOLDOUT/OOS no se usa para entrenar?**

Porque si se usa OOS durante el desarrollo, el modelo indirectamente aprende de los
datos que debería predecir. Eso invalida la evaluación final: ya no es una prueba
honesta de generalización, es una medida optimista de ajuste. En términos simples, es
como estudiar con las preguntas del examen final: la nota sube, pero no mides lo que
aprendiste.

---

## 7. Explicación de la taxonomía FAILURE_TAXONOMY_V1

La taxonomía `FAILURE_TAXONOMY_V1` define categorías de causas candidatas de fallo que
pueden observarse **antes** del resultado.

Es un contrato de laboratorio, no una señal operativa. Su función es diagnóstica:
organizar hipótesis causales sobre por qué una secuencia puede fallar.

Los drivers definidos son:

### 7.1 HTF_CONFLICT

La dirección de la secuencia entra en conflicto con sesgos o alineación HTF
observables en `features_at_t`.

Ejemplos:
- secuencia alcista con bias HTF bajista;
- secuencia bajista con bias HTF alcista;
- `h1_alignment=AGAINST`.

### 7.2 ADVERSE_CONTEXT

El contexto alrededor de la secuencia es adverso o explícitamente en contra.

Ejemplos:
- `context_bucket=AGAINST`;
- `h1_alignment=AGAINST`.

### 7.3 IMMATURE_SEQUENCE

La secuencia aún no muestra suficiente madurez estructural antes del outcome.

Ejemplos:
- `sequence_depth < 4`;
- falta una etapa crítica esperada en la secuencia.

### 7.4 CONSTRAINT_CONTRADICTION

Las restricciones operativas contradicen la dirección de la secuencia.

Ejemplos:
- secuencia alcista con `allow_long=false`;
- secuencia bajista con `allow_short=false`;
- `direction_hint` contrario a `sequence_direction`.

### 7.5 WEAK_STRUCTURE

La estructura observada antes del resultado es débil o incompleta.

Ejemplos:
- falta `DISPLACEMENT`;
- falta `STRUCTURE`;
- no hay confirmación estructural suficiente en la representación causal.

### 7.6 LOW_SUPPORT_REGIME

El patrón pertenece a un régimen con soporte insuficiente en TRAIN/DESIGN.

Se calcula con combinaciones de contexto ajustadas solo sobre TRAIN. Si una combinación
aparece poco o no aparece en TRAIN, el driver queda activo para advertir que el modelo
debe abstenerse o tratarlo con cautela.

### 7.7 DIRECTIONAL_AMBIGUITY

La dirección no tiene autoridad clara en las features disponibles antes del resultado.

Ejemplos:
- `direction_hint=UNKNOWN`;
- bias `MIXED`, `NEUTRAL` o `UNKNOWN`;
- mezcla simultánea de señales alcistas y bajistas.

### 7.8 UNKNOWN

Se usa cuando ningún driver anterior se activa. No significa que no exista una causa
real; significa que esta taxonomía v1 no la puede explicar con las features actuales.

---

## 8. Drivers materializados en failure_anatomy_v1

Conteos globales de drivers en el dataset materializado:

| Driver | Count |
|--------|-------|
| HTF_CONFLICT | 174 |
| ADVERSE_CONTEXT | 82 |
| IMMATURE_SEQUENCE | 0 |
| CONSTRAINT_CONTRADICTION | 132 |
| WEAK_STRUCTURE | 0 |
| LOW_SUPPORT_REGIME | 195 |
| DIRECTIONAL_AMBIGUITY | 277 |
| UNKNOWN | 0 |

**Nota:** `IMMATURE_SEQUENCE`, `WEAK_STRUCTURE` y `UNKNOWN` no aparecen en esta
materialización porque las filas disponibles tienen secuencias maduras con
`DISPLACEMENT` y `STRUCTURE`. Eso no significa que los drivers sean irrelevantes, sino
que el corpus actual no los activa.

---

## 9. Riesgos y límites

1. **Soporte bajo de `failure` en OOS.**
   v1.003 tiene failure support = 26, por debajo del umbral interpretativo n ≥ 30.
   Esto limita la confianza en cualquier conclusión sobre la clase `failure`.

2. **FULL/PREFIX no reproducido.**
   El productor original de `SEQ_CTX_01` no ha sido ejecutado en modo de auditoría
   completa. Los checks actuales validan artefactos persistidos, no la línea causal
   completa desde datos fuente.

3. **Correlación ≠ causalidad.**
   Mejorar recall de `failure` no prueba que el modelo entienda por qué falla. Solo
   prueba que empata patrones con ejemplos históricos.

4. **`can_trade=false` permanece.**
   Ninguna métrica mejorada autoriza trading, DEMO, live signal ni producción.

5. **Datasets ignorados por Git.**
   Los artefactos TF están bajo `data/`, que está en `.gitignore`. Son evidencia local,
   no entrega versionada pública.

6. **Sample smallness.**
   292 eventos totales es pequeño para una red neuronal generalizar bien. Es un primer
   ciclo demostrativo de aprendizaje, no un entrenamiento productivo.

---

## 10. Siguiente trabajo recomendado

En orden lógico:

1. **Entrenar `failure_risk_v1`** sobre el dataset `failure_anatomy_v1`.
   - Objetivo binario: `is_failure`.
   - Arquitectura conservadora recomendada: Dense(48) + Dropout(0.10) + Dense(24) + Dense(1+Sigmoid).
   - VALIDATION para early stopping.
   - TEST_OOS reservado para dictamen final.

2. **Auditar calibración de `failure_risk_v1`.**
   - ECE, Brier, curva de confianza.
   - Comparar probabilidad predicha vs tasa real de failure por bin.

3. **Comparar `failure_risk_v1` contra baseline.**
   - Clase mayoritaria.
   - Regresión logística o baseline lineal mínimo.
   - No usar OOS para elegir entre modelos.

4. **Mantener `can_trade=false`.**
   - Sin trading, DEMO, live signal, producción.
   - Sin modificar datasets fuente.
   - Sin descargar datos, sin MT5.

5. **Solo después, evaluar fusión tardía con v1.003.**
   - Forma recomendada: late fusion.
   - `outcome_probs_v1_003 + failure_risk_v1 → meta_calibrator_shadow`.
   - Solo si `failure_risk_v1` cierra en REVIEW reproducible sin fallos de procedencia.

---

## 11. Confirmaciones explícitas

- No se modificaron datasets fuente.
- No se descargaron datos.
- No se activó MT5, DEMO, paper ni producción.
- No se cambió `can_trade=false`.
- No se promueve a producción.
- No se declara PASS científico.

---

## 12. Archivos de evidencia

- `data/ml/tensorflow/tf_outcome_v1_001/`
- `data/ml/tensorflow/tf_outcome_v1_002/`
- `data/ml/tensorflow/tf_outcome_v1_003/`
- `data/ml/tensorflow/failure_anatomy_v1/`
- `reports/audits/experiments/ai/tensorflow_v1_t1_corpus_verification.md`
- `reports/audits/experiments/ai/tensorflow_v1_002_final_dictamen.md`
- `reports/audits/experiments/ai/tensorflow_v1_003_neural_training.md`
- `reports/audits/experiments/ai/failure_anatomy_learning_line_v1.md`
- `reports/audits/experiments/ai/failure_anatomy_v1_materialization.md`
- `docs/contratos/FAILURE_TAXONOMY_V1.md`
- `docs/planificacion/PLAN_ENTRENAMIENTO_TENSORFLOW_HERMES_V1.md`
- `docs/planificacion/PLAN_FAILURE_ANATOMY_LEARNING_V1.md`
- `reports/audits/experiments/ai/neural_training_progress_v1.json`
- `reports/audits/experiments/ai/neural_training_progress_v1.png`
- `reports/audits/experiments/ai/neural_learning_map_v1.png`

---

*Fin del reporte técnico.*
