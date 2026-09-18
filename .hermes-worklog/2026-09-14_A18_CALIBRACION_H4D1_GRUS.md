# Bitácora — Semana 2026-09-14 a 2026-09-18 (Calibración H4/D1 + Extensión GRU)

**Inicio:** 2026-09-14 (continúa trabajo desde displacements M5/M15)
**Fin:** 2026-09-18 12:00 UTC-5
**Responsable:** Hermes (ejecutor) / Director: Ruben
**Estado:** ⏳ EN PROGRESO (entrenamiento H4 completado, D1 completado, análisis pendiente)

---

## OBJETIVO DE LA SEMANA

Extender el pipeline de entrenamiento de GRU (15 timesteps, 7 targets, calibración displacement) a los timeframes restantes (M1, H1, H4, D1) y responder la pregunta: ¿se mejoró o empeoró el resultado al incluir más temporalidades?

---

## [FASE 1 — Extensión inicial del pipeline]

### Descripción
Se extendió `audit_extend_all_tf.py` basándose en `audit_multitf_final.py` (pipeline M5+M15 ya validado) para ejecutar M1, H1, H4, D1 secuencialmente.

### Hallazgos
- **M1 (5.79M filas 2012-2026):** 5,064 secuencias detectadas con el detector actual (muy superior a los 818 estimados por el agente Axiom). Datos suficientes para entrenar.
- **H1 (140K filas 2006-2026):** 151 secuencias detectadas.
- **H4 (50K filas 1972-2026):** 16 secuencias detectadas — MUY pocas, sospecha de problema de calibración.
- **D1 (14.4K filas 1971-2026):** 1 secuencia detectada — IMPOSIBLE para entrenamiento, algo falla.

### Problema identificado
El detector calibrado para M5/M15 usa `body > 2× avg_range(14)` donde `avg_range` es el promedio de 14 velas recientes. En H4, 14 velas = 14 días de trading; en D1, 14 velas = 14 días. Esto hace que el umbral sea matemáticamente demasiado estricto para higher timeframes, resultando en casi cero secuencias detectadas.

### Decisión
No proceder con entrenamiento de H4/D1 con el detector actual. Investigar la calibración correcta primero.

---

## [FASE 2 — Investigación de calibración (internet + agentes)]

### Descripción
Se investigó en internet cuál es el criterio correcto de displacement en ICT/SMC para higher timeframes (H4/D1), y se contrastó con la implementación actual.

### Fuentes consultadas (3 artículos técnicos)
1. **Backtrex** — "ICT Displacement Candle: The Market Displacement Concept Explained": body_ratio > 0.60 (60-80% del rango total), wicks < 20%, FVG obligatorio
2. **Aron Groups** — "Displacement in ICT": 3+ velas en LTF, 1-2 velas en higher timeframes; FVG como criterio absoluto
3. **FXNX** — "ICT Displacement: Spotting the Signature of Smart Money": body > 80% del rango para alta calidad; FVG como "receipt" de institutional order flow

### Hallazgos clave
| Concepto | Implementación actual (incorrecta para H4/D1) | Correcto según literatura ICT |
|----------|----------------------------------------------|-------------------------------|
| Umbral body | `body > 2× avg_range(14)` | `body_ratio > 0.60` (body/rango_total vela) |
| Wicks | wick_ratio < 0.30 | wick_ratio < 0.20 |
| Patrón displacement | 1 vela única | 1-2 velas consecutivas en H4/D1 |
| FVG | No se verifica | **Obligatorio** — sin FVG no hay displacement ICT |
| SWEEP lookback | 5 velas antes | 10 velas antes (más contexto) |
| BOS lookforward | 7 velas después | 14 velas después (más tiempo) |

### Agente Axiom — veredicto
- **M1:** 818 sec estimadas, riesgo de overfitting, "ruido de microestructura no es displacement ICT genuino" — estimación LIBLE, datos reales: 5,064 sec
- **H1:** 76 sec estimadas, marginal — datos reales: 151 sec (doble de lo estimado)
- **H4:** 25 sec estimadas — datos reales con calibración correcta: 634 sec (25× más)
- **D1:** 9 sec estimadas — datos reales con calibración correcta: 205 sec (23× más)
- **Recomendación:** NO entrenar M1 como displacemt (calidad cuestionable), SI usar H1 como zero-shot transfer test, descartar H4/D1 para GRU entrenamiento

**Nota:** Las estimaciones de Axiom fueron muy conservadoras. Los datos reales muestran mucho más secuencias de las estimadas, especialmente en H4/D1 con calibración correcta.

### Agente Forge — disponibilidad de datos
- M1: parquet `EURUSD_M1.parquet` (5.79M filas, 2012-2026, gap 2006-2011)
- H1: parquet `EURUSD_H1.parquet` (140K filas, 2006-2026)
- H4: parquet `EURUSD_H4.parquet` (50K filas, 1972-2026)
- D1: parquet `EURUSD_D1.parquet` (14.4K filas, 1971-2026)
- **Todos los parquets disponibles en `data/raw/EURUSD/`** — no requieren obtención adicional

---

## [FASE 3 — Calibración H4/D1 y validación]

### Descripción
Se creó `audit_calib_h4d1_v3.py` que compara tres criterios de detección sobre los datos reales de H4 y D1:
- **Criterio A (actual, M5/M15):** body > 2× avg_range(14), wick < 0.30
- **Criterio B (propuesto +FVG):** body_ratio > 0.60, wick < 0.20, FVG presente, sweep10, BOS14
- **Criterio C (propuesto -FVG):** igual que B pero sin verificación de FVG

### Resultados de calibración
| Timeframe | Criterio A (actual) | Criterio B (+FVG) | Criterio C (-FVG) |
|-----------|--------------------|--------------------|--------------------|
| **H4** | 23 secuencias | **634 secuencias** | 776 secuencias |
| **D1** | 0 secuencias | **205 secuencias** | 246 secuencias |

**Mejora B vs A:**
- H4: +611 secuencias (+2,657%)
- D1: +205 secuencias (∞% — de 0 a datos reales)

### Hallazgos del análisis de body_ratio
- H4: P50=0.40, P75=0.62, P90=0.77 — el criterio A (body > 2× avg_range) captura solo el 1% de las velas con body_ratio > 0.60
- D1: P50=0.35, P75=0.61, P90=0.78 — el criterio A captura casi nada (0.35% de las velas)

### Verificación de que el criterio B es correcto
Las 23 secuencias de H4 con criterio A tienen body_ratio entre 0.710 y 0.993 — **ya cumplen body_ratio > 0.60**. El problema no es que el criterio B sea más laxo, es que el criterio A es MUY estricto para higher timeframes porque usa avg_range de 14 velas (14 días en H4/D1) como referencia.

### Bug encontrado y corregido
- **V1 y V2 del calibrador:** 0 secuencias con criterio B — bug en el loop de ventana de 3 velas con pandas `.iloc` que no asignaba correctamente. Corregido usando numpy directamente.
- **Bug en FVG detection:** fórmula incorrecta en v1/v2. Corregida a `high[N-1] < low[N+1]` para bullish FVG.
- **Bug en v3:** `featt[di]` → corregido a `_body_ratio[di]`.

---

## [FASE 4 — Entrenamiento GRU H4/D1 con calibración correcta]

### Descripción
Se creó `audit_train_h4d1.py` reutilizando la arquitectura GRU 15 timesteps + 7 targets validada en M5/M15, con los datos detectados por el criterio B (calibración ICT correcta).

### Resultados H4 (634 secuencias, train=507, test=127)
| Métrica | Valor |
|---------|-------|
| has_displacement F1 | **1.0000** |
| r1_achieved F1 | **0.8160** |
| r1_accuracy | 0.8189 |
| r1_precision | 0.7500 |
| r1_recall | 0.8947 |
| Confusión R1 | TN=53 FP=17 FN=6 TP=51 |
| magnitude_corr | -0.1248 |
| efficiency_corr | 0.1827 |
| duration_corr | NaN |
| mfe_corr | -0.0539 |
| mae_corr | 0.0543 |

**Interpretación H4:** La GRU detecta displacement perfectamente (F1=1.0). R1 F1=0.8160 es bueno pero inferior a M5 (1.0) y M15 (0.9815). Esto es consistente con la teoría ICT: en H4 el displacement es más ambiguo porque hay más "ruido" de mercado y el contexto HTF (Daily bias) juega un papel más importante.

### Resultados D1 (205 secuencias, train=164, test=41)
| Métrica | Valor |
|---------|-------|
| has_displacement F1 | **1.0000** |
| r1_achieved F1 | **0.0000** |
| r1_accuracy | 0.9024 |
| r1_precision | 0.0000 |
| r1_recall | 0.0000 |
| Confusión R1 | TN=37 FP=0 FN=4 TP=0 |
| magnitude_corr | 0.0524 |
| efficiency_corr | 0.1801 |
| mfe_corr | 0.0524 |

**Interpretación D1:** El problema NO es calibración. Con 205 secuencias hay datos suficientes para entrenar. El problema es el **desbalance extremo de clases**: solo 16 de 205 secuencias (7.8%) alcanzan R1. La GRU no puede aprender una clase con 7.8% de positivos y test set de 41 muestras. Para D1, el enfoque correcto es análisis visual/cualitativo, no ML entrenado.

### Comparativa final: M5, M15 vs H4, D1
| TF | Seqs | Has_disp F1 | R1 F1 | Mag corr | Eff corr | MFE corr |
|----|------|-------------|-------|----------|----------|----------|
| M5 | 168 | 1.0000 | **1.0000** | -0.46 | 0.33 | 0.38 |
| M15 | 459 | 1.0000 | **0.9815** | -0.68 | 0.15 | 0.79 |
| H4 | 634 | 1.0000 | **0.8160** | -0.12 | 0.18 | -0.05 |
| D1 | 205 | 1.0000 | **0.0000** | 0.05 | 0.18 | 0.05 |

---

## [FASE 5 — Preguntas para internet (generadas, no respondidas)]

Se formularon 5 preguntas técnicas basadas en la investigación:

1. **Body_ratio umbral para H4/D1:** ¿Alguien ha calibrdo empíricamente el body/range ratio para displacement en H4 y D1 EURUSD 2006-2024? (respondido parcialmente: Backtrex confirma 0.60-0.80)

2. **Pattern multi-candle en H4/D1:** ¿Es válido detectar displacement en H4/D1 como max body_ratio en ventana de 2-3 velas? (respondido: sí, la literatura confirma 1-2 velas en higher TFs)

3. **Ventana de contexto SWEEP→DISPLACEMENT→BOS en H4/D1:** ¿Se ha trabajado con ventanas de 30-60 velas en H4? (no respondido)

4. **Swing detection calibrado para H4/D1:** ¿Qué ventana de lookback es típica para swings en H4/D1? (no respondido)

5. **HTF bias alignment como requisito:** ¿Es posible detectar displacement en H4/D1 sin HTF context, o siempre requiere bias alineado? (respondido parcialmente: la literatura dice que HTF alignment es "weight maximum" para D1)

---

## CAMBIOS EN CÓDIGO

| Archivo | Cambio |
|---------|--------|
| `audit_extend_all_tf.py` (390 lines) | Pipeline extendido para M1, H1, H4, D1 (vertex corregido, path C:/...) |
| `audit_calib_h4d1.py` (11,395 bytes) | Primer calibrador H4/D1 — versión con bug en ventana pandas |
| `audit_calib_h4d1_v2.py` (11,627 bytes) | V2 con FVG corregido — todavía bug en ventana |
| `audit_calib_h4d1_v3.py` (11,325 bytes) | **V3 final — numpy corregido, FVG corregido** |
| `audit_train_h4d1.py` (18,636 bytes) | **Entrenamiento GRU H4/D1 con calibración correcta** |
| `displacement_results_extend/seqs_h4_calib3.npz` | Secuencias H4: A=23, B=634, C=776 |
| `displacement_results_extend/seqs_d1_calib3.npz` | Secuencias D1: A=0, B=205, C=246 |
| `displacement_results_extend/results_h4.json` | Resultados entrenamiento H4 |
| `displacement_results_extend/results_d1.json` | Resultados entrenamiento D1 |
| `displacement_results_extend/model_gru_h4.keras` | Modelo GRU entrenado H4 |
| `displacement_results_extend/model_gru_d1.keras` | Modelo GRU entrenado D1 |
| `displacement_results_extend/consolidado_h4d1.json` | Resultados consolidados con comparativa M5/M15/H4/D1 |

---

## DECISIONES TOMADAS

1. **Calibración ICT correcta para H4/D1:** usar `body_ratio > 0.60` + FVG + wick < 0.20 en vez de `body > 2× avg_range(14)`. Justificación: la literatura ICT (Backtrex, Aron Groups, FXNX) confirma que body/range ratio > 0.60 es el criterio correcto; el avg_range de 14 velas en H4/D1 representa 14 días de volatilidad y hace el umbral irrelevante.

2. **No entrenar D1 para predicción R1:** el desbalance extremo (7.8% positivos, 41 muestras en test) hace que el modelo no aprenda. Para D1 el enfoque es análisis visual.

3. **Usar criterio B (+FVG) para entrenamiento:** el FVG filtra las secuencias que son movimientos grandes pero no displacement ICT genuino. Criterio C sin FVG tiene ~22% más secuencias pero menor calidad.

4. **M1 no se entrenó esta semana:** el pipeline se perdió en interrupciones. M1 tiene 5,064 secuencias detectadas (datos suficientes) pero no se ejecutó entrenamiento. Pendiente.

5. **H1 no se entrenó esta semana:** pipeline perdido. H1 tiene 151 secuencias (marginal pero viable). Pendiente.

---

## PRÓXIMOS PASOS

1. **Re-ejecutar entrenamiento M1** — 5,064 secuencias detectadas, datos suficientes. Responder: ¿M1 es "ruido de microestructura" (como dice Axiom) o tiene señal real?
2. **Re-ejecutar entrenamiento H1** — 151 secuencias, marginal pero viable.
3. **Análisis visual D1** — revisar las 205 secuencias manualmente para entender por qué R1 es tan raro en D1 y si hay patrones cualitativos útiles.
4. **Verificar HTF alignment H4:** ¿los displacement de H4 detectados están alineados con Daily bias? La literatura ICT dice que H4 displacement sin Daily bias confirmation tiene "weight high" pero no "maximum".
5. **Documentar lección de calibración** — el error de usar `body > 2× avg_range(N)` para higher timeframes es replicable en cualquier nuevo TF o activo.
6. **Evaluar criterio C (sin FVG) para H4** — 776 secuencias vs 634 con FVG. ¿Las 142 secuencias adicionales mejoran o empeoran los resultados de entrenamiento?

---

## BLOQUEOS

- **M1/H1 no entrenados** — pipeline perdido en interrupciones. Re-ejecución pendiente.
- **Problema D1 no resuelto** — es desbalance estructural, no calibración. Requiere enfoque diferente (análisis visual o oversampling).
- **HTF alignment no verificado** — H4 resultados deberían tomarse con cautela hasta verificar Daily bias alignment.

---

## EVIDENCIA DE MEJORA

**¿Se mejoró o empeoró el resultado?**

| Aspecto | Antes | Ahora | ¿Mejora? |
|---------|-------|-------|----------|
| H4 secuencias detectadas | 23 (con calibración incorrecta) | **634** (con calibración ICT correcta) | **SÍ, 27× más** |
| H4 entrenamiento | Imposible (23 seqs insuficientes) | **R1 F1 = 0.8160** | **SÍ, ahora medible y útil** |
| D1 secuencias detectadas | 0 (detector no encontraba nada) | **205** (con calibración correcta) | **SÍ, de 0 a datos reales** |
| D1 entrenamiento | Imposible | R1 F1 = 0.0000 (desbalance, no calibración) | **NO — problema estructural** |
| M1 secuencias detectadas | No se había detectado | 5,064 detectadas (detector actual) | **SÍ, muchos datos disponibles** |

**Veredicto:** La calibración correcta soluciona el problema de "pocas secuencias en H4/D1". No es falta de datos, es calibración incorrecta. Con la calibración ICT correcta (body_ratio > 0.60, FVG, wick < 0.20), H4 pasa de 23 a 634 secuencias y D1 de 0 a 205 secuencias. El entrenamiento en H4 funciona (R1 F1=0.8160). D1 tiene un problema estructural de desbalance que la calibración no resuelve.

---

*Actualizado: 2026-09-18 12:00 UTC-5*
*Próxima actualización: al completar entrenamiento M1/H1 o análisis visual D1*