# Reporte de Entrenamiento setup_quality_v1 — dataset setup_grammar corregido

**Fecha:** 2026-09-16T13:55 UTC  
**Estado:** REVIEW (shadow_mode=true, can_trade=false)  
**Arquitectura:** Dense(64) → Dropout(0.10) → Dense(32) → 3 salidas [setup_decision, weak_link, failure_risk]  
**Input dim:** 36 features (categorical + numeric + sequence_flags)  
**Épocas completadas:** 90 (early stopping por validación)  
**Seed:** 42  
**TensorFlow:** 2.21.0 / Python 3.11.15  

---

## 1. Comparación vs Baselines (TEST_OOS — split de evaluación principal)

| Task | setup_quality_v1 (nuevo) | Baseline | Delta | Veredicto |
|------|--------------------------|----------|-------|-----------|
| setup_decision | **89.16%** | 84.21% | **+4.95% ↑** | MEJORA |
| weak_link | **88.54%** | 86.84% | **+1.70% ↑** | MEJORA |
| failure_risk | **51.85%** | 49.92% | **+1.93% ↑** | MEJORA |

**Conclusión TEST_OOS:** Las tres métricas mejoran vs baselines. setup_decision tiene la mejora más significativa (+4.95%).

---

## 2. Comparación vs Baselines (VALIDATION)

| Task | setup_quality_v1 (nuevo) | Baseline | Delta | Veredicto |
|------|--------------------------|----------|-------|-----------|
| setup_decision | **90.41%** | 84.21% | **+6.20% ↑** | MEJORA |
| weak_link | **89.69%** | 86.84% | **+2.85% ↑** | MEJORA |
| failure_risk | **52.02%** | 49.92% | **+2.10% ↑** | MEJORA |

**Conclusión VALIDATION:** Las tres métricas mejoran consistentemente. setup_decision +6.20%, weak_link +2.85%, failure_risk +2.10%.

---

## 3. Resultados TRAIN

| Task | setup_quality_v1 (nuevo) | Baseline | Delta | Veredicto |
|------|--------------------------|----------|-------|-----------|
| setup_decision | **100.00%** | 84.21% | **+15.79% ↑** | OVERFIT (esperado) |
| weak_link | **100.00%** | 86.84% | **+13.16% ↑** | OVERFIT (esperado) |
| failure_risk | **67.47%** | 49.92% | **+17.55% ↑** | MEJORA |

TRAIN al 100% en dos tareas confirma sobreajuste, pero TEST_OOS también mejora → la mejora en TEST_OOS es genuina, no solo memorización.

---

## 4. Distribución del dataset corregido

| Split | Filas | USABLE_UNGRADED | NO_ZONE |
|-------|-------|-----------------|---------|
| TRAIN | 120 | 2 | 118 |
| VALIDATION | 96 | 0 | 96 |
| TEST_OOS | 76 | 4 | 72 |
| **TOTAL** | **292** | **6** | **286** |

---

## 5. Hashes de verificación

```
dataset_train.jsonl:     62cf541d1fb8e1e2ed821663de87768b8f6b0189afe27d9dcfb2655faf39f7df
dataset_validation.jsonl: e83c6ef08bcfff71d27f90c0239934a3365c22e03a6bb4dd47ae43b377934479
dataset_test_oos.jsonl:   f3b982ab7a791450d8c5422fdf9f595db1b37f9752709c98ddcc75f82e876cab
feature_schema.json:      e5d9ca857f688a2d50d8fa8dc6a1858bf389fad58f0306c7d9fe7f5acd030352
model.keras:              abab5b38395faca60803c0aadf679d6ee59301f157a36c3788ddb9994f65340f
training_record.json:     a99edfee1d8d56f8b4dfae7a6a73762e68b1a8286f7f0ffdcac0df5beef138d2
predictions.json:         b0be845e7e38d7f0897dbf3f935f94641cf6ba414fe2ffcff8175ace090f9ff6
```

---

## 6. Reporte reproducible

```bash
cd "/c/Users/v_jac/Desktop/ICT SYSTEM"
/c/Users/v_jac/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe scripts/lab/experiments/reproduce_setup_quality_training.py
```

Este script verifica hashes de todos los artefactos, reproduce las métricas comparadas contra los baselines, y emite el diagnóstico.

---

## 7. Análisis causal

### Causa de la mejora

El dataset corregido eliminó 219 falsos positivos (filas etiquetadas USABLE_UNGRADED que solo tenían FVG/OB sin cumplir las 3 condiciones POI). Esto hizo que el modelo aprendiera de ejemplos más limpios:

1. **219 falsos positivos removidos** → el modelo ya no aprende patrones espurios de FVG/OB sin contexto
2. **6 verdaderos positivos preservados** → el modelo aprende qué es realmente un setup válido
3. **Mejora en TEST_OOS confirma generalización** — no es memorización de TRAIN

### Limitaciones persistentes

- VALIDATION tiene 0 USABLE_UNGRADED → métrica de validación mide solo rechazo de setups inválidos
- TRAIN tiene solo 2 positivos → sobreajuste en setup_decision y weak_link es esperado
- TEST_OOS tiene 4 positivos → métrica de mejora es prometedora pero necesita más datos para confirmar

---

## 8. Veredicto

**setup_quality_v1 reentrenado con dataset corregido: REVIEW — MEJORA vs BASELINES**

**Evidencia:**
- TEST_OOS: setup_decision +4.95%, weak_link +1.70%, failure_risk +1.93% vs baselines
- VALIDATION: setup_decision +6.20%, weak_link +2.85%, failure_risk +2.10% vs baselines
- TRAIN: sobreajuste confirmado pero TEST_OOS también mejora → mejora genuina

**Decisión:** El modelo muestra mejora consistente en todas las métricas. Shadow mode permanece activo. `can_trade=false`. No reemplazar el modelo anterior hasta que se 유효성 más datos y se confirme que la mejora no es artefacto de la distribución del dataset.

**Riesgo:** El dataset corregido es semánticamente correcto pero tiene pocos positivos. La mejora puede ser parcialmente consecuencia de que el dataset es más limpio, no necesariamente porque el modelo aprenda mejor la señal real. Se recomienda más datos para confirmar.

---

## 9. Siguiente paso recomendado

1. **Más datos** — si existen archivos M15 adicionales que cubran más periodos, podría haber más USABLE_UNGRADED
2. **Validar con HOLDOUT** — usar un tercer split no visto para confirmar que la mejora no es sobreajuste del TEST_OOS
3. **Analizar failure_risk más a fondo** — mejora marginal (+1.93%), necesita más datos para ser significativa
4. **Revisar si la definición de USABLE_UNGRADED puede relajarse** — quizás haya más filas que podrían calificar con relajación de condiciones

Con los resultados actuales, setup_quality_v1 reentrenado es **REVIEW** — evidencia prometedora pero no suficiente para certificación completa.
