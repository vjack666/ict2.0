# Lista de trabajo — Comprensión de IA/neuronas sobre desplazamiento ICT

**Objetivo:** que la IA y las neuronas comprendan al 100% qué es desplazamiento y cómo se usa en ICT.
**Estado actual:** PLAN_EXISTE_PERO_NO_EJECUTADO. Plan v1 escrito 2026-09-17, 0 fases ejecutadas.
**Fecha:** 2026-09-17

---

## Bloque A — Inventario y diagnóstico (ya iniciado)

| # | Tarea | Estado | Evidencia / notas |
|---|-------|--------|-------------------|
| A1 | Mapear todos los detectores de displacement existentes | ✅ EN PROgreso | `detectors/displacement.py` + `engine/detectors/displacement.py` + `runtime/ai_learning/displacement_teacher.py` |
| A2 | Resolver contradicción de umbral (0.50 vs 0.60) | PENDIENTE | `engine/detectors/displacement.py:5` dice ≥60%, config default = 0.50 |
| A3 | Resolver sustitución de calentamiento por 1e-9 | PENDIENTE | `detectors/displacement.py:48` — `avg_range.fillna(1e-9)` |
| A4 | Verificar equivalencia entre `detectors.displacement` y `engine.detectors.displacement` | PENDIENTE | `market_features.py:30` usa `detectors.displacement`; doc dice materializador usa `engine.detectors.displacement`. No existe equivalencia demostrada. |
| A5 | Inventariar corpus etiquetado existente | PENDIENTE | 292 filas `PRESENT_UNGRADED` sin negativos, sin salida displacement propia |
| A6 | Verificar pérdida de orden de eventos en entrenador actual | PENDIENTE | Auditoría 17-sep: features idénticas al invertir 292/292 secuencias |

---

## Bloque B — Fase 1: Profesor coherente (Orion D6 + Forge D2, revisa Vigil D5)

| # | Tarea | Estado | Entregable |
|---|-------|--------|------------|
| B1 | Contrastar tesis ICT (SPEC_TESIS_FORMAL.md sección DISPLACEMENT) con detectores existentes | PENDIENTE | Documento de contrastes: velas cerradas tras sweep, cuerpo >70%, 50-70% débil, umbral calibrable |
| B2 | Separar geometría de setup contextual | PENDIENTE | Profesor ya tiene 3 capas (geometry/episode/ict_context) — validar que la separación es correcta |
| B3 | Fijar casos frontera: 0.50, 0.60, 0.70, múltiplo 1.5, rango cero, escala de precio | PENDIENTE | `validate_boundaries()` existe en displacement_teacher.py — correr y documentar |
| B4 | Resolver prioridad de contratos: ¿qué regla gana cuando hay desacuerdo? | PENDIENTE | Contratos: SPEC_TESIS_FORMAL, SETUP_GRAMMAR_SUPERVISION, ENMIENDA_AUTONOMIA |
| B5 | Fijar reloj: available_at, confirmation_time, forma de CANDIDATE vs CONFIRMED | PENDIENTE | Profesor tiene lógica de confirmation_bars pero no está validada con datos reales |
| B6 | Documentar contradicciones resueltas o marcadas "no evaluables" | PENDIENTE | Tabla documento/regla/consumidor/test |

---

## Bloque C — Fase 2: Ejemplos causales (Nexus D4 + Probe D6)

| # | Tarea | Estado | Entregable |
|---|-------|--------|------------|
| C1 | Inventariar fuentes existentes de M15 (parquets en data/raw) | PENDIENTE | Lista de símbolos/TF disponibles con hashes |
| C2 | Cargar periodos continuos en memoria | PENDIENTE | DataFrames cargados + checksums |
| C3 | Comparar episodios positivos, negativos y ambiguos | PENDIENTE | Informe por clase/dirección/periodo |
| C4 | Conteos reales de clases y cobertura | PENDIENTE | Tabla: cuántos STRONG/WEAK/NONE por dirección, por periodo |
| C5 | Ninguna clase evaluada con soporte cero | PENDIENTE | Gate de salida de fase |

---

## Bloque D — Fase 3: Representación (Forge D2 + Helix D3)

| # | Tarea | Estado | Entregable |
|---|-------|--------|------------|
| D1 | Preservar velas, orden, duración, mascaras y contexto conocido | PENDIENTE | Lector/tensor con pruebas de cierre |
| D2 | Normalizar solo con TRAIN | PENDIENTE | Pipeline de normalización documentado |
| D3 | Separar salidas del profesor de entradas del alumno | PENDIENTE | Esquema de features vs targets explícito |
| D4 | Trazabilidad de cada variable a sus fuentes | PENDIENTE | Mapa variable → fuente |
| D5 | Tests FULL/PREFIX | PENDIENTE | Agregar velas futuras no cambia salidas pasadas |

---

## Bloque E — Fase 4: Aprendizaje gradual (Helix D3)

| # | Tarea | Estado | Entregable |
|---|-------|--------|------------|
| E1 | Baseline: regla congelada (profesor como reference) | PENDIENTE | Metricas del profesor sobre corpus |
| E2 | Baseline tabular simple | PENDIENTE | Modelo tabular + metricas |
| E3 | GRU pequeña sobre secuencias causales (32 M15 + resumen HTF) | PENDIENTE | Modelo + learning curves |
| E4 | Primero geometría, después episodios, finalmente contexto | PENDIENTE | Phased training report |
| E5 | 3 semillas (17, 42, 101), hasta 50 epocas, early stopping paciencia 5 | PENDIENTE | Config y resultados por semilla |
| E6 | Semillas fijas, no backtest | PENDIENTE | Gate de reproducibilidad |

---

## Bloque F — Fase 5: Examen independiente (Vigil D5)

| # | Tarea | Estado | Entregable |
|---|-------|--------|------------|
| F1 | Reproducir evaluación sin ver predicción del modelo | PENDIENTE | Pipeline de evaluación blindada |
| F2 | Medir falsos positivos, omisiones, abstenciones | PENDIENTE | Matriz de confusión, PR-AUC, calibración |
| F3 | Ablaciones: historia, HTF, geometría aislada | PENDIENTE | Dictamen por ablación |
| F4 | Panel separado por rubrica (ocultar salidas profesor/modelo/futuro) | PENDIENTE | Rubrica de evaluación |
| F5 | Dictamen: RECOGNITION_SUPPORTED / REVIEW_INSUFFICIENT_EVIDENCE / FAILED_CRITERIA | PENDIENTE | Veredicto documentado |

---

## Bloque G — Fase 6: Entrega educativa (Forge D2 + Ledger D1)

| # | Tarea | Estado | Entregable |
|---|-------|--------|------------|
| G1 | Replay hasta decision_time con zona del impulso | PENDIENTE | Visualización por caso |
| G2 | Ficha por caso con evidencia y razones | PENDIENTE | Documentación por example |
| G3 | Tabla de fallos | PENDIENTE | Diagnóstico de errores |

---

## Bloque H — Criterios de éxito (del plan)

| Métrica | Umbral | Estado |
|---------|--------|--------|
| Precision ≥ 0.85 para STRONG | Investigación | NO MEDIDO |
| Recall ≥ 0.75 para STRONG | Investigación | NO MEDIDO |
| Ambas direcciones | Investigación | NO MEDIDO |
| Cobertura ≥ 0.60 | Investigación | NO MEDIDO |
| IC 95% semiancho ≤ 0.10 | Investigación | NO MEDIDO |
| Superioridad vs tabular | Investigación | NO MEDIDO |

---

## Bloque I — Riesgos activos (del plan + codebase)

| # | Riesgo | Severidad | Mitigación |
|---|--------|-----------|------------|
| I1 | Etiquetas circulares (PRESENT_UNGRADED por presencia del nombre, no por contenido) | ALTA | Fase 1: redefinir etiquetas |
| I2 | Confusión geometría/contexto/outcome | ALTA | Fase 1: separar explícitamente |
| I3 | Futuro disponible antes de cierre | ALTA | Fase 1: fijar reloj |
| I4 | Falta de soporte por clase (292 filas, solo POSITIVO) | ALTA | Fase 2: inventario + posiblemente sintéticos para contraste |
| I5 | Dos detectores distintos sin equivalencia demostrada | MEDIA | Fase 1: resolver cuál es fuente de verdad |
| I6 | Sustitución 1e-9 como calentamiento | MEDIA | Fase 1: decidir comportamiento |
| I7 | Entrenador pierde orden de eventos | ALTA | Fase 3: representación causal correcta |

---

## Estado resumido

```
Fase 1 (Profesor coherente):     0/6 tareas → INICIO
Fase 2 (Ejemplos causales):      0/5 tareas → espera F1 parcial
Fase 3 (Representación):         0/5 tareas → espera F2
Fase 4 (Aprendizaje gradual):    0/6 tareas → espera F3
Fase 5 (Examen independiente):   0/5 tareas → espera F4
Fase 6 (Entrega educativa):      0/3 tareas → espera F5
TOTAL:                           29 tareas pendientes
```

**Siguiente paso inmediato:** resolver A1-A6 (diagnóstico) → B1-B6 (profesor coherente).
