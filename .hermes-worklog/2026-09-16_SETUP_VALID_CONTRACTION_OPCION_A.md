# Bitácora de Trabajo — 2026-09-16 — Contractación Setup Válido (OPCIÓN A)

## [INICIO]

- **Tarea:** Contractar setup válido en modo shadow/research — corregir materializador de setup_grammar_v1, regenerar dataset, reentrenar setup_quality_v1, comparar contra baselines.
- **Auditor:** Hermes (agente ejecutor principal)
- **Fecha:** 2026-09-16
- **Estado al inicio:** 
  - Materializador con defecto conocido: `pd_array_zone()` etiqueta USABLE_UNGRADED solo por presencia de FVG/OB, sin evaluar 3 condiciones POI
  - Dataset existente con 219 falsos positivos (USABLE_UNGRADED → INVALID_ZONE semántico)
  - Detector semántico SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1 funcional (6/6 casos de juguete)
  - Auditoría semántica completada: 292 filas auditadas, 0 EVIDENCE_MISSING, 0 falsos negativos, 219 falsos positivos
  - Estado del dataset: `ready_for_setup_quality_training_review`
- **MISSIONS AUTORIZADAS:** OPCIÓN A (corregir + regenerar + reentrenar + comparar)
- **RESTRICCIONES:** `can_trade=false`, `entry_authorized=false`, shadow mode. No MT5, no órdenes, no trading real.
- **BASELINES A SUPERAR:** setup_decision 84.21%, weak_link 86.84%, failure_risk 49.92% balanced accuracy

---

## [FASE 1 — DIAGNÓSTICO DEL DEFECTO]

### Defecto encontrado en `pd_array_zone()`

Ubicación: `scripts/lab/experiments/materialize_setup_grammar_dataset_v1.py:314-318`

```python
def pd_array_zone(stages, evidence=None):
    if "FVG" in stages or "OB" in stages or evidence.get("zone_present"):
        return "USABLE_UNGRADED"
    return "NO_ZONE"
```

**Problema:** La función solo verifica si hay FVG/OB en la secuencia de stages. No evalúa:

1. **Condición POI (zona correcta):** ¿El PD Array está en la zona correcta del dealing range? (premium para short, discount para long)
2. **Condición de sesgo HTF alineado:** ¿h1_alignment=ALIGNED, direction_hint compatible, context_bucket=ALIGNED?
3. **Condición de respaldo institucional:** ¿Hay displacement + FVG/OB presentes en M15 hasta decision_time?

**Consecuencia:** 219 filas etiquetadas como USABLE_UNGRADED son semánticamente INVALID_ZONE. El materializador produce falsos positivos masivos.

### Evidencia de que el defecto existe

- Auditoría semántica `setup_grammar_semantics_v1_audit.md`: 219/219 USABLE_UNGRADED son INVALID_ZONE
- Detector semántico `semantic_pd_array_eval_v1.py:246-288`: evalúa las 3 condiciones correctamente (6/6 casos de juguete pasan)
- Auditoría M15-only `setup_grammar_semantics_audit_v1_standalone.py`: 0 EVIDENCE_MISSING, todas las filas auditadas

### Causa raíz

El materializador fue diseñado para supervisión H1 (secuencia de stages), pero la etiqueta `pd_array_zone` se usa como feature para entrenar la red `setup_quality_v1`. Sin evaluar las 3 condiciones POI, la red aprende de etiquetas incorrectas.

---

## [FASE 2 — DISEÑO DE LA CORRECCIÓN]

### Enfoque

Reutilizar el detector semántico `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1` (`semantic_pd_array_eval_v1.py`) para evaluar cada fila durante la materialización.

### Función a modificar

`pd_array_zone(stages, evidence=None)` → extender a `pd_array_zone(stages, features_at_t, exec_tf_evidence, direction)`

### Firmas propuestas

**Opción A — Extender la función existente:**

```python
def pd_array_zone(
    stages: set[str],
    features_at_t: dict[str, Any] | None = None,
    exec_tf_evidence: dict[str, Any] | None = None,
    direction: int = 0,
) -> str:
    # Evaluar las 3 condiciones POI usando el detector semántico
    # Retornar USABLE_UNGRADED solo si las 3 condiciones se cumplen
    # Retornar NO_ZONE si no hay PD Array o no cumple condiciones
```

**Opción B — Crear función wrapper separada:**

```python
def pd_array_zone_semantic(
    stages: set[str],
    features_at_t: dict[str, Any] | None = None,
    exec_tf_evidence: dict[str, Any] | None = None,
    direction: int = 0,
) -> str:
    # Usa semantic_pd_array_zone() del detector
```

### Decisión: Opción A (extender la función existente)

- Menos cambios en `materialize_row()` (que ya pasa `evidence` a `pd_array_zone()`).
- La función `materialize_row()` ya tiene acceso a `features_at_t`, `exec_tf_evidence` y `direction`.
- Se mantiene la capacidad de regresión: si el detector semántico falla, se puede volver a la versión simple.

### Implementación del detector semántico integrado

La función `semantic_pd_array_zone()` en `semantic_pd_array_eval_v1.py` ya implementa las 3 condiciones. La integraré como:

```python
from semantic_pd_array_eval_v1 import semantic_pd_array_zone as _semantic_pd_array_zone

def pd_array_zone(
    stages: set[str],
    features_at_t: dict[str, Any] | None = None,
    exec_tf_evidence: dict[str, Any] | None = None,
    direction: int = 0,
) -> str:
    # Construir M15 evidence desde exec_tf_evidence
    m15_evidence = _build_m15_evidence_for_semantics(exec_tf_evidence)
    
    # Evaluar con detector semántico
    result = _semantic_pd_array_zone(
        decision_time=decision_time,
        features_at_t=features_at_t,
        m15_evidence=m15_evidence,
        direction=direction,
    )
    
    # Convertir resultado semántico a etiqueta de materializador
    if result["zone_state"] == "VALID_ITF_ZONE":
        return "USABLE_UNGRADED"
    return "NO_ZONE"
```

### Condiciones de éxito

1. Las 219 filas que antes eran USABLE_UNGRADED ahora deben ser NO_ZONE (si no cumplen las 3 condiciones).
2. Las 73 filas que ya eran NO_ZONE deben seguir siéndolo (0 falsos negativos).
3. El dataset regenerado debe tener 0 falsos positivos (según auditoría semántica).
4. Los hashes deben ser diferentes a los del dataset anterior (porque las etiquetas cambiaron).

---

## [FASE 3 — PLAN DE EJECUCIÓN]

### Paso 1: Corregir el materializador (setup_grammar_materialization_fix_v1.py)

- Extender `pd_array_zone()` para evaluar las 3 condiciones POI
- Integrar el detector semántico `semantic_pd_array_eval_v1.py`
- Mantener compatibilidad hacia atrás (si el detector falla, usar evaluación simple)

### Paso 2: Regenerar el dataset

- Ejecutar `materialize_setup_grammar_dataset_v1.py` con el materializador corregido
- Sobrescribir los archivos existentes en `data/ml/tensorflow/setup_grammar_v1/`
- Generar nuevos hashes SHA256

### Paso 3: Verificar el dataset regenerado

- Verificar hashes (sha256sum)
- Verificar conteos de splits (TRAIN 120, VALIDATION 96, TEST_OOS 76)
- Verificar ausencia de leakage (FULL vs PREFIX)
- Verificar que no hay features derivadas del futuro
- Ejecutar tests existentes (`test_setup_grammar_dataset.py`)

### Paso 4: Reentrenar setup_quality_v1

- Ejecutar `train_setup_quality_v1.py` con el dataset corregido
- Comparar métricas contra los 3 baselines:
  - setup_decision: 84.21% → ¿mejora?
  - weak_link: 86.84% → ¿mejora?
  - failure_risk: 49.92% → ¿mejora?

### Paso 5: Entregar reporte reproducible

- Comandos ejecutados
- Hashes de dataset y modelo
- Métricas TRAIN/VALIDATION/TEST_OOS
- Comparación antes/después
- Riesgos identificados
- Dictamen: PASS / FAIL / REVIEW

---

## [FASE 4 — DECISIONES DE DISEÑO]

### Decisión 1: Usar detector semántico existente

**Decisión:** Reutilizar `semantic_pd_array_eval_v1.py` en lugar de crear lógica nueva.

**Razón:** El detector ya está verificado (6/6 casos de juguete), ya evalúa las 3 condiciones correctamente, y la auditoría semántica ya lo usó para auditar las 292 filas.

### Decisión 2: Extender pd_array_zone() vs crear función nueva

**Decisión:** Extender la función existente `pd_array_zone()`.

**Razón:** Menos cambios en `materialize_row()`, que ya pasa `evidence` a esta función. La firma extendida mantiene compatibilidad con el código existente.

### Decisión 3: No editar dataset a mano

**Decisión:** Regenerar el dataset desde fuentes originales (`SEQ_CTX_01_CANONICAL_BOS.jsonl`, `SEQ_CTX_01_LITE.jsonl`).

**Razón:** Editar a mano introduciría errores humanos y no sería reproducible. La correción debe estar en el materializador, no en el dataset.

### Decisión 4: Mantener shadow mode durante todo el proceso

**Decisión:** `can_trade=false`, `entry_authorized=false` durante toda la ejecución.

**Razón:** La misión es investigación/capacidad neuronal, no trading real. No hay autorización para levantar estas restricciones.

---

## [FASE 5 — RIESGOS IDENTIFICADOS]

### Riesgo 1: Regresión en rendimiento

**Descripción:** Al corregir las etiquetas, el dataset tendrá menos USABLE_UNGRADED (las 219 falsos positivos se volverán NO_ZONE). Esto puede reducir el número de ejemplos positivos para entrenar `setup_decision` y `weak_link`.

**Mitigación:** Verificar que el rendimiento no empeore significativamente. Si el modelo con dataset corregido tiene métricas peores que los baselines, eso es señal de que las neuronas no están aprendiendo la tesis ICT correctamente.

### Riesgo 2: Detector semántico incompleto

**Descripción:** El detector semántico usa presencia conjunta de displacement + FVG/OB como proxy de respaldo institucional. La relación causal explícita `displacement → PD Array` no está disponible.

**Mitigación:** Documentar esta limitación en el reporte. La auditoría semántica ya identificó esto. Si es crítico, se puede mejorar el detector en una fase futura.

### Riesgo 3: Cambios en splits

**Descripción:** Al regenerar el dataset, los splits pueden cambiar si la lógica de división depende de las etiquetas.

**Mitigación:** Verificar que los splits (TRAIN 120, VALIDATION 96, TEST_OOS 76) se mantienen igual después de la regeneración.

---

## [FASE 6 — EVIDENCIA REQUERIDA PARA CIERRE]

### Evidencia mínima requerida

1. **Dataset corregido:**
   - Hashes SHA256 de los 3 archivos JSONL
   - Conteos de splits (TRAIN 120, VALIDATION 96, TEST_OOS 76)
   - Conteos de etiquetas (NO_ZONE vs USABLE_UNGRADED)
   - Ausencia de leakage (FULL vs PREFIX)

2. **Modelo reentrenado:**
   - Hashes del modelo (model.keras, training_record.json, predictions.json)
   - Métricas TRAIN/VALIDATION/TEST_OOS para los 3 heads
   - Comparación contra baselines (84.21%, 86.84%, 49.92%)

3. **Reporte reproducible:**
   - Comandos ejecutados (con output)
   - Hashes verificados
   - Métricas documentadas
   - Riesgos identificados
   - Dictamen explícito (PASS / FAIL / REVIEW)

---

## [ESTADO]

**Estado:** `PLANNED` — fase 0 completada, diseño listo para ejecución.

**Siguiente paso:** Implementar corrección del materializador (`setup_grammar_materialization_fix_v1.py`).
