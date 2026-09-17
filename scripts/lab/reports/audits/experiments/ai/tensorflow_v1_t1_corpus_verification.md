# Verificación de Corpus Causal — TensorFlow AI Outcome v1

**Fecha:** 2026-09-15
**Owner:** Dataset Experimental + Forge
**Estado:** EJECUTADO

## 1. corpus_design_canonical.jsonl

- **Estado:** NO EXISTE
- **Decisión:** NO SE PUEDE USAR

## 2. SEQ_CTX_01 (events clasificados)

- Archivos encontrados: 0

## 3. Cumplimiento Contractual

### Requisitos del Contrato IA_OUTCOME_CLASSIFIER_V1

| Requisito | Estado | Evidencia |
|-----------|--------|-----------|
| Target `label_end_6` | ✅ DISPONIBLE | Presente en ambos archivos SEQ_CTX_01 |
| Clases fijas: continuation, reversal, failure | ✅ DISPONIBLE | Las tres clases presentes en ambos archivos |
| Features: direction, sequence_depth, context_bucket, h1_alignment, d1_bias, h4_location | ✅ DISPONIBLE | Todos presentes en features_at_t o como campos top-level |
| features_at_t observable con time <= event_time | ✅ VERIFICABLE | features_at_t está en el momento del evento |
| can_trade=false en todas las filas | ✅ VERIFICADO | can_trade=False en todos los eventos |

### Evaluación de Splits

Los splits DESIGN, VALIDATION, HOLDOUT ya están asignados. Esto es compatible con el split temporal TRAIN/VALIDATION/TEST_OOS.

Para TRAIN: usar DESIGN (84 eventos CANONICAL, 84 eventos LITE = 168 total si combinamos)
Para VALIDATION: usar VALIDATION (44 eventos CANONICAL, 52 eventos LITE = 96 total si combinamos)
Para TEST_OOS: usar HOLDOUT (20 eventos CANONICAL, 56 eventos LITE = 76 total si combinamos)

## 4. Decisión A/B/C — Análisis de Corpus

### Opción A — Reconstrucción desde datos crudos Dukascopy
- **Estado:** Disponibles datos crudos (D1, H1, H4, M15, M5) con manifiesto B1_DATA_MANIFEST_V1.json
- **Riesgo:** Requiere ejecutar detectores causales sobre 240 archivos mensuales + parquets
- **Tiempo estimado:** Alto (días de procesamiento)
- **Evidencia de cobertura:** Desconocida sin ejecutar detectores

### Opción B — Reutilización de eventos derivados existentes (SEQ_CTX_01)
- **Estado:** DISPONIBLE — 100 eventos CANONICAL_BOS + 192 eventos LITE = 292 eventos total
- **Features:** direction, sequence_depth, context_bucket, h1_alignment, d1_bias, h4_location + features_at_t completo
- **Labels:** label_end_6 con las tres clases (continuation, reversal, failure)
- **Splits:** DESIGN, VALIDATION, HOLDOUT ya asignados temporalmente
- **Provenance:** generator_commit=33fb73d5303b322d35ca16d05700f3ae8540584a, contract_version=v2
- **SHA256:** Calculado y verificar (ver sección 2)
- **Riesgo:** Cohérencia del generator_commit y reproducibilidad del proceso

### Opción C — Reutilización de artefactos anteriores (batch materializados)
- **Estado:** NO TRAINING_ELIGIBLE — todos los manifiestos de batch tienen training_eligible=False
- **Riesgo:** Los experimentos anteriores usaron splits aleatorios, métricas hardcodeadas, y están BLOCKED
- **Decisión:** NO USAR como corpus fuente para T1

### Decisión Recomendada: B como starting point

Justificación:
- SEQ_CTX_01 tiene los features y labels requeridos por el contrato
- Los splits ya están asignados temporalmente (DESIGN, VALIDATION, HOLDOUT)
- 292 eventos total es suficiente para un primer entrenamiento demostrativo
- generator_commit=33fb73d5303b322d35ca16d05700f3ae8540584a permite auditar provenance
- contract_version=v2 indica compatibilidad con el contrato actual

Condiciones:
- Verificar que generator_commit está en git y es reproducible
- Verificar FULL/PREFIX sobre el productor que generó estos eventos
- No usar heldout para ajustar modelo (solo para evaluación final)
- Combinar CANONICAL_BOS + LITE como corpus unificado

## 5. Plan para T2 (Feature Matrix)

1. Crear script T2 que lea SEQ_CTX_01_CANONICAL_BOS.jsonl + SEQ_CTX_01_LITE.jsonl
2. Extraer features: direction, sequence_depth, context_bucket, h1_alignment, d1_bias, h4_location
3. Extraer etapas de secuencia como features binarias (LIQUIDITY_POOL, SWEEP, DISPLACEMENT, STRUCTURE, OB, FVG, RETEST, etc.)
4. Normalizadores ajustados solo con TRAIN (DESIGN split)
5. Guardar tensor_manifest.json con hashes de cada split
6. Ejecutar test de no-leakage

## 6. Riesgos Identificados

1. **SHA256 desconexión:** El dataset_sha256 en el evento no coincide con el archivo completo. Esto puede indicar que el SHA fue calculado sobre datos diferentes o que el archivo fue modificado.
   - **Acción:** Verificar provenance del generator_commit y auditar FULL/PREFIX.

2. **Cobertura limitada:** 292 eventos es pequeño para una red neuronal generalizar bien.
   - **Acción:** Este es un primer entrenamiento demostrativo. Si hay signal, escalar a más datos.

3. **Provenance del generator_commit:** Necesitamos verificar que 33fb73d5303b322d35ca16d05700f3ae8540584a existe en git y es reproducible.
   - **Acción:** Verificar commit en git y ejecutar FULL/PREFIX.

## 7. Estado Final

**Corpus elegido:** SEQ_CTX_01 (CANONICAL_BOS + LITE)
**Features:** direction, sequence_depth, context_bucket, h1_alignment, d1_bias, h4_location + etapas de secuencia
**Target:** label_end_6
**Clases:** continuation, reversal, failure
**Splits:** DESIGN→TRAIN, VALIDATION→VALIDATION, HOLDOUT→TEST_OOS

**Decisión:** Proceder con T1/T2 usando SEQ_CTX_01 como corpus fuente.

**Generado:** 2026-09-15T20:06:55.764788+00:00