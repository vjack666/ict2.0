# Dictamen — failure_risk_v1

**Fecha:** 2026-09-15
**Modelo:** failure_risk_v1
**Dataset:** failure_anatomy_v1
**Politica:** can_trade=false, shadow_mode=true

## Resumen ejecutivo

`failure_risk_v1` fue entrenado y auditado sobre `failure_anatomy_v1`
(TRAIN n=120/25 failure, VALIDATION n=96/19, TEST_OOS n=76/26).

El modelo aprendió patrones predictivos de riesgo de fallo que mejoran
respecto a baselines triviales y al modelo anterior v1.003 en recall y F1
de failure. Sin embargo, el gap de sobreajuste (ROC TRAIN 0.94 → OOS 0.61)
y el tamaño limitado de la muestra OOS impiden declarar evidencia suficiente
para pasar a la siguiente fase con confianza.

**DICTAMEN: REVIEW_INSUFFICIENT_EVIDENCE**

---

## 1. ¿Aprendió failure_risk_v1?

SI, pero de manera limitada.

El modelo alcanza ROC-AUC 0.6108 en TEST_OOS, superando al baseline
logístico (0.5254) y a todos los otros baselines. El failure_recall
mejora de 0.2308 (v1.003) a 0.3462, y failure_F1 de 0.2609 a 0.4091.

No es learning nulo. Hay señal detectable.

Pero la magnitud de mejora es modesta y el gap de sobreajuste es
significativo.

---

## 2. ¿Qué aprendió?

El modelo aprendió a asociar ciertas combinaciones de features con mayor
riesgo de failure:

- **DIRECTIONAL_AMBIGUITY** es el driver más predictivo (lift +0.2141 en
  probabilidad predicha). Cuando hay ambigüedad direccional, el modelo
  asigna mayor probabilidad de failure.

- **sequence_depth** es la feature continua más importante por permutación
  (+0.0542). Secuencias más profundas se asocian con menor riesgo.

- **context_bucket=AGAINST** y **h1_bias=BEARISH** contribuyen positivamente
  al riesgo predicho.

- **h4_location** (EQUILIBRIUM, DISCOUNT) y **structure_mode** (CANONICAL_BOS)
  tienen importancia moderada.

El modelo NO aprende una relación causal directa. Aprende asociaciones
predictivas.

---

## 3. ¿Qué NO aprendió?

- No aprendió a generalizar perfectamente fuera de muestra.
- El failure_recall OOS (0.3462) sigue siendo bajo: captura solo 9 de 26
  failures reales en TEST_OOS.
- No distingue bien entre failure y non-failure: la failure_precision es
  0.5000, lo que significa que la mitad de las predicciones positivas son
  falsas alarmas.
- No aprendió patrones robustos que funcionen consistentemente en todos los
  regímenes: hay segmentos donde el rendimiento es muy variable.

---

## 4. ¿Superó los baselines?

PARCIALMENTE.

| Métrica      | LR baseline | failure_risk_v1 | Delta |
|--------------|-------------|------------------|-------|
| ROC-AUC      | 0.5254      | 0.6108           | +0.0854 |
| PR-AUC       | 0.4222      | 0.4122           | -0.0100 |
| Brier        | 0.3107      | 0.2443           | +0.0664 |
| FailRecall   | 0.2692      | 0.3462           | +0.0770 |
| FailF1       | 0.2692      | 0.4091           | +0.1399 |
| LogLoss      | 0.8508      | 0.6995           | +0.1513 |

Mejora en 5 de 6 métricas sobre el mejor baseline (LR).

La excepción es PR-AUC, donde el modelo es ligeramente peor que LR.
Esto sugiere que en el rango de altas precisiones (donde importa más para
detección de failure), el modelo no aporta mejora clara.

---

## 5. ¿Generalizó OOS?

PARCIALMENTE.

El modelo mantiene señal predictiva en OOS (ROC 0.6108 > 0.5), pero con
degradación significativa desde TRAIN (ROC 0.9408).

El gap de 0.3301 puntos de ROC entre TRAIN y OOS indica sobreajuste
moderado-grande. Esto es consistente con:
- Pequeño tamaño de TRAIN (n=120)
- Relación parámetros/muestra alta (2641/120 = 22.01)
- Alta dimensionalidad (29 features)

No hay evidencia de que el modelo haya memorizado completamente (no hay
probabilidades extremas injustificadas en OOS, hay veterinación de 0%
sobreconfianza >0.9). Pero el sobreajuste a ruido específico de TRAIN es
evidente.

---

## 6. ¿Encontró failures que v1.003 no encontraba?

SÍ, en términos de recall.

v1.003 tenía failure_recall = 0.2308 en TEST_OOS (capturaba ~6 de 26
failures). failure_risk_v1 tiene failure_recall = 0.3462 (captura ~9 de
26 failures).

La celda C de la matriz conceptual (failures que v1.003 perdió pero
failure_risk_v1 detectó) es positiva: hay aproximadamente 3 failures
adicionales detectados.

Pero con n=26 failures en OOS, 3 detectados adicionales es una señal
pequeña y debe interpretarse con cautela estadística.

---

## 7. ¿Existe evidencia de leakage o memorización?

NO hay evidencia de leakage.

- Todos los hashes del dataset coinciden con la materialización certificada.
- Separación temporal estricta verificada.
- Sin features derivadas del futuro.
- Sin solapamiento entre splits.
- Modelo reproducible (semilla fija, mismo código, mismos pesos).

La prueba de memorización muestra:
- Sin probabilidades extremas injustificadas (0% >0.9 en OOS).
- Sin sobreconfianza extrema en OOS.
- Pero sí sobreajuste: TRAIN muy bueno, OOS moderado.

Esto es sobreajuste clásico, no memorización pura. Es un problema de
capacidad vs. datos, no de leaking.

---

## 8. ¿Cuál es la principal limitación estadística?

El tamaño de muestra OOS.

Con n=76 observaciones y solo 26 failures en TEST_OOS:

- El IC 95% para failure_recall:
  - Método exacto de Clopper-Pearson: [0.173, 0.556]
  - El intervalo es amplio.

- El IC 95% para failure_precision:
  - Asumiendo 9 TP y 9 FP: [0.266, 0.734]
  - También amplio.

Cualquier conclusión sobre el rendimiento real del modelo debe reconocer
que con estas muestras, el error de muestreo es grande.

No hay potencia estadística suficiente para:
- Declarar que la mejora sobre LR es estadísticamente significativa.
- Descartar que la diferencia PR-AUC (-0.01) sea ruido.
- Afirmar que el modelo generalizará a nuevos períodos con el mismo
  rendimiento observado.

---

## 9. ¿Cuál es el dictamen?

### REVIEW_INSUFFICIENT_EVIDENCE

**Razones:**

1. Hay señal predictiva real: ROC 0.6108 > baselines (≈0.5), mejora sobre
   v1.003 en recall y F1.

2. Pero el gap de sobreajuste es significativo (0.33 ROC), sugiriendo que
   parte de lo aprendido es ruido específico de TRAIN.

3. El tamaño de muestra OOS (n=76, 26 failure) impide conclusiones fuertes.
   Los intervalos de confianza son amplios.

4. La mejora sobre LR es consistente en varias métricas, pero PR-AUC no
   mejora, lo que sugiere que la mejora no es robusta en todos los
   umbrales.

5. El modelo no está lo suficientemente calibrado ni robusto para ser
   usado como feature en un meta_calibrator.

**No es:**
- PASS_FOR_SHADOW_RESEARCH: la evidencia no es suficientemente reproducible
  ni estable.
- FAIL_NO_LEARNING: hay learning detectable, no es nulo.
- BLOCKED_DATA_OR_CAUSALITY: los datos están certificados, sin leakage.

---

## 10. ¿Está científicamente justificado pasar a meta_calibrator_shadow?

NO, no con la evidencia actual.

Para pasar a la fase de fusión con v1.003 (meta_calibrator_shadow),
failure_risk_v1 debería demostrar:

1. Mejora reproducible y estable sobre baselines en OOS.
2. Calibración aceptable (ECE < 0.10 preferiblemente).
3. Failure_recall suficientemente alto para aportar valor al predictor
   combinado.
4. Evidencia de que los drivers identificados corresponden a patrones
   reales y no a overfitting.

El modelo actual no cumple criterios 2, 3 y 4 con la evidencia disponible.

---

## Ruta recomendada

Si se quiere continuar la línea failure_anatomy_v1:

1. **Aumentar muestra OOS:** más eventos de 2021-2025, posiblemente con
   horizontes de outcome alternativos (H12, H24) si la causalidad lo
   permite.

2. **Simplificar modelo:** reducir parámetros, aumentar regularización,
   probar arquitecturas más pequeñas (Dense(16) → Dense(8) → Dense(1)).

3. **Validar drivers en HOLDOUT adicional:** si se dispone de un tercer
   periodo temporal no usado, verificar que los drivers identificados
   mantienen su predictividad.

4. **Analizar por subgrupos:** segmentar por context_bucket, h1_alignment,
   structure_mode para identificar donde el modelo funciona mejor/peor.

5. **Ensemble con LR:** en lugar de reemplazar LR, probar ensemble simple
   (promedio de probabilidades) para ver si la combinación mejora PR-AUC.

---

## Artefactos entregados

```
data/ml/tensorflow/failure_risk_v1/
├── model.keras                    (489d490d... 60989 bytes)
├── training_record.json           (03895abf... 6038 bytes)
├── predictions.json               (38468111... 36795 bytes)
├── feature_importance.json        (ac1e4430... 3134 bytes)
├── driver_analysis.json           (100b4c15... 3204 bytes)
└── comparison.json                (1e3cb2ca... 11062 bytes)
```

Scripts:
```
scripts/lab/experiments/
├── train_failure_risk_v1.py
├── complete_failure_risk_v1_artifacts.py
└── analyze_failure_risk_v1_comparison.py
```

---

## Confirmaciones finales

- can_trade=false ✓
- shadow_mode=true ✓
- merge_with_tf_outcome_v1_003=DEFERRED ✓
- No se modificaron datasets fuente ✓
- No se crearon señales de trading ✓
- No se optimizó entry/SL/TP ✓

---

**Dictamen emitido por:** Hermes (agente ejecutor)
**Fecha:** 2026-09-15
**Estado:** MISION COMPLETADA — REVIEW_INSUFFICIENT_EVIDENCE
