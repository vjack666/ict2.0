# INFORME: Comprensión de IA/Neuronas sobre Desplazamiento ICT
# Resultado de diagnóstico ejecutado 2026-09-17

**Objetivo del análisis:** responder "qué es desplazamiento ICT y cómo se usa" con evidencia empírica, no con teoría.

---

## 1. Ecosistema de displacement en ICT SYSTEM (lo que existe)

### Detectores (2 distintos, sin equivalencia demostrada)

| Detector | Lógica | Frecuencia en M5 EURUSD |
|----------|--------|------------------------|
| `detectors/displacement.py` | Geometría pura: cuerpo ≥1.5x rango promedio 14v, mecha <40%, SIN ruptura estructural | 4.82% (2409/50000) |
| `engine/detectors/displacement.py` | Geometría + ruptura de estructura (close rompe prev_high/prev_low) + min 1.5 pips + ratio ≥0.50 | 15.84% (7919/50000) |
| `runtime/ai_learning/displacement_teacher.py` | 3 capas: geometría (0.60/0.50 ratio + rompe estruct) + episodio + contexto ICT | 20.56% (geométrico) / 0.43% (con contexto ICT completo) |

### Consumidores en producción

| Módulo | Uso de displacement |
|--------|---------------------|
| `engine/bias_from_tools.py` | Geometría pura (tools.displacement, SIN ATR) como input al quality_score de BOS |
| `engine/historical_event_objects.py` | MarketObject DISPLACEMENT con role=TRIGGER, hijo de OB H4 (parent_object). Solo se crea si hay OB H4 activo al alcance. |
| `engine/ahf.py` | `bool(ltf.displacement_recent)` como confirmación de entrada (trigger económico) |
| `engine/market_features.py` | Columnas displacement_bullish/bearish/mag sobre cada frame |
| `analysis/ict_agent.py` | Lee displacement del último bar y lo emite como evento DISPLACEMENT en consenso |

### Etiquetado existente (corpus de entrenamiento)

| Split | Filas | displacement_quality |
|-------|-------|---------------------|
| TRAIN | 120 | 100% PRESENT_UNGRADED |
| VALIDATION | 96 | 100% PRESENT_UNGRADED |
| TEST OOS | 76 | 100% PRESENT_UNGRADED |

**Todo el corpus tiene displacement presente, sin negativos. Sin salida neuronal específica para displacement. Sin contraste supervisado fuerte/debil/ausente.**

---

## 2. ¿Qué es desplazamiento ICT? (respuesta empírica)

Según la evidencia del código + datos reales + tesis, desplazamiento ICT es **tres cosas juntas**:

### Capa 1 — Geometría
- Cuerpo grande respecto al rango de la vela (cuerpo/rango ≥ 0.60 = STRONG, 0.50-0.60 = WEAK)
- Mecha reducida (wick_ratio < 0.40) → empuje, no noise
- Dirección clara (close > open para bullish, close < open para bearish)
- Ruptura de estructura previa (close rompe el máximo/mínimo de las N velas anteriores)

**Sin esto → no hay displacement, punto.**

### Capa 2 — Episodio
- Confirmación en siguiente vela(s): el impulso continúa, no retrocede >50% del rango de la vela de displacement
- available_at: momento en que es observable (cierre de la vela de displacement)
- confirmation_time: primera vela que confirma el avance

### Capa 3 — Contexto ICT (lo que diferencia "movimiento grande" de "desplazamiento institucional")
- **Sweep previo**: liquidez colectada antes del impulso (liquidity_sweep_up/down)
- **FVG/OB cercano**: la estructura del mercado (PD Array) apunta en la misma dirección
- **Estructura confirmada**: hay un BOS/CHOCH previo que da contexto de ruptura
- **HTF sesgo**: sesgo de H1/H4/D1 alineado (opcional pero relevante)

**Sin Capa 3 → es solo geometría. No es desplazamiento ICT usable para entrada.**

---

## 3. Evidencia empírica (sobre datos reales EURUSD M5 2022-2026)

### Frecuencias encontradas

| Criterio | % de velas |
|----------|------------|
| Geometría STRONG (cuerpo≥60% + rompe estruct) | 13.97% |
| Geometría WEAK (cuerpo 50-60% + rompe estruct) | 4.30% |
| TOTAL geometría positiva | 18.27% |
| Con CONTEXTO ICT SUPPORTED (sweep + estructura) | **0.43%** |
| Con CONTEXTO ICT NOT_SUPPORTED | 99.17% |

**Hallazgo central:**
- El 18.27% de las velas tiene geometría de displacement (cuerpo grande + ruptura estructural)
- Pero solo el **0.43%** tiene las tres capas juntas (geometría + ruptura + contexto ICT)
- Eso significa: **~98% de los movimientos geométricos fuertes NO son desplazamiento ICT con contexto**

### Comparación de detectores

| Detector | Frecuencia | Qué mide |
|----------|------------|----------|
| det_disp (1.5x, sin ruptura) | 4.82% | Geometría pura (cuerpo/rango + mecha) |
| eng_disp (0.50 + ruptura estructural + pips) | 15.84% | Geometría + ruptura + tamaño absoluto |
| Profesor con contexto ICT | 0.43% | Las 3 capas juntas |

**Discrepancia crítica:** el detector del sistema `detectors.displacement.py` (el que usa `market_features.py:30`) marca 4.82% de velas como displacement pero **no exige ruptura de estructura**. El profesor (0.60/0.50 + rompe estruct) marca 18.27% de geometría pero con contexto ICT solo 0.43%.

---

## 4. ¿Cómo se usa displacement en ICT SYSTEM? (el uso real)

### Como TRIGGER de entrada (AHF)
En `engine/ahf.py:216`:
```python
trig = ltf.answers.get("HAS_TRIGGER")
if trig is True:
    return True
return bool(ltf.displacement_recent)
```
Displacement es un **trigger económico**: confirma la entrada cuando hay secuencia H1 depth/trigger.

### Como MARKET OBJECT (historical_event_objects.py)
- Tipo: DISPLACEMENT
- Role: TRIGGER (no POI, no confirmación)
- parent_object: OB H4 al que evidencia
- lineage_relation: DISPLACEMENT_EVIDENCES_OB_HTF
- Solo se crea si hay OB H4 activo dentro de la ventana (poi_to_child_max_hours=120)

**Displacement por sí solo no genera objeto. Necesita un OB padre H4.**

### Como input al quality_score (bias_from_tools.py)
- `tools.displacement` (geometría pura, sin ATR) corre primero
- El quality_score usa body_ratio + distancia al nivel + rango promedio
- El displacement es input al score del BOS, no es señal por sí solo

### Como evento en consenso (analysis/ict_agent.py)
- Se lee displacement_bullish/bearish del último bar
- Se emite como evento type=DISPLACEMENT en el agente ICT
- Forma parte de la evidencia del consenso multi-agente

---

## 5. Problemas encontrados (para la IA aprender correctamente)

### Problema A — Dos detectores distintos sin equivalencia
`detectors.displacement.py` vs `engine/detectors/displacement.py` tienen lógica diferente y no se ha demostrado equivalencia. `market_features.py:30` importa el primero, el doc dice el materializador usa el segundo.

### Problema B — Sustitución 1e-9 como calentamiento
`detectors/displacement.py:48`: `rng = avg_range.fillna(1e-9)` — cuando no hay 14 velas de historial, el rango promedio se reemplaza por ~cero, haciendo que `body > rng * 1.5` sea casi siempre TRUE en las primeras velas. **Falsos positivos artificiales.**

### Problema C — Corpus sin negativos
Las 292 filas etiquetadas (TRAIN+VAL+TEST) tienen displacement_quality=PRESENT_UNGRADED al 100%. **No hay ejemplos NEGATIVOS en el corpus supervisado.** El modelo no puede aprender lo que NO es displacement.

### Problema D — Sin salida neuronal específica
El modelo actual no tiene una salida específica para displacement. La etiqueta PRESENT_UNGRADED se materializa por presencia del nombre en un conjunto, no por contenido medible.

### Problema E — Pérdida de orden de eventos
Auditoría del 17-sep: features idénticas al invertir 292/292 secuencias. El entrenador actual pierde el orden de eventos.

### Problema F — Geometría sin contexto = ruido
Solo 0.43% de velas tiene la tríada completa. 18.27% tiene geometría pero sin contexto ICT. Si se entrena solo con geometría, el modelo aprenderá a detectar "movimiento grande" pero no "desplazamiento ICT con contexto".

---

## 6. Respuesta a "cómo se usa" — el flujo real

```
D1 sesgo (bias_from_tools_htf)
  → H4 sesgo
    → H1 sesgo
      → M5/M15 trigger
        → displacement_recent (bool)
          → confirmación de entrada (AHF step)
            → si hay OB H4 padre → MarketObject DISPLACEMENT (TRIGGER)
              → lineage: DISPLACEMENT_EVIDENCES_OB_HTF
```

Displacement es **el último eslabón**, no el primero. No es la señal principal, es la confirmación de que el impulso institucional está presente en el TF de ejecución.

---

## 7. Implicaciones para el entrenamiento de IA

Para que la IA comprenda desplazamiento al 100%, necesita aprender las tres capas:

1. **Geometría** (fácil): cuerpo/rango, mecha, dirección, ruptura de estructura → ~18% de velas, learnable con datos puramente OHLC
2. **Episodio** (medio): confirmación, avance neto, retroceso → requiere mirar varias velas futuras desde decision_time
3. **Contexto ICT** (difícil): sweep, FVG/OB, estructura, HTF → requiere múltiples TF y detectors del sistema

**El problema central del corpus actual:**
- 292 filas etiquetadas pero 100% positivo (PRESENT_UNGRADED)
- Sin negativos, sin contraste fuerte/debil/ausente
- Sin salida neuronal específica para displacement
- El modelo actual aprende "setup_quality general" no "reconocimiento de displacement"

**Para entrenar reconocimiento de displacement real:**
- Necesita corpus con NEGATIVOS (geometría sin contexto = NO displacement ICT)
- Necesita salidas separadas: geometric_strength (NONE/WEAK/STRONG), direction (UP/DOWN/NONE), ict_context (SUPPORTED/NOT_SUPPORTED/PENDING/UNKNOWN)
- Necesita profesor coherente (Fase 1 del plan) con casos frontera resueltos
- Necesita datos con contexto real calculado por los detectores del sistema

---

## 8. Estado actual de la comprensión

| Aspecto | Estado |
|---------|--------|
| ¿Qué es geometría de displacement? | Comprendido, detectores existentes lo miden |
| ¿Qué es ruptura de estructura? | Comprendido, requerido por profesor y engine/detectors |
| ¿Qué es contexto ICT? | Comprendido conceptualmente, pero detectores dispersos |
| ¿Qué es la tríada completa? | Medido empíricamente: 0.43% de velas |
| ¿El corpus actual es suficiente? | NO — 100% positivo, sin negativos, sin salida específica |
| ¿El modelo actual reconoce displacement? | NO — aprende setup_quality general, no displacement específico |
| ¿Hay contradicciones en detectores? | SÍ — dos detectores distintos, umbral 0.50 vs 0.60, 1e-9 bug |

---

## 9. Próximos pasos (de la lista de trabajo)

### Inmediatos (Bloque A — diagnóstico, completados)
- [x] A1: Mapear detectores — 2 detectores distintos identificados
- [x] A2: Contradicción umbral 0.50 vs 0.60 — confirmada
- [x] A3: Bug 1e-9 — confirmado, falsos positivos en primeras 14 velas
- [x] A4: Equivalencia detectores — NO existe
- [x] A5: Corpus — 292 filas 100% PRESENT_UNGRADED sin negativos
- [x] A6: Pérdida orden eventos — confirmada por auditoría

### Fase 1 — Profesor coherente (urgente)
- [ ] B1: Contrastar tesis ICT (SPEC_TESIS_FORMAL.md sección DISPLACEMENT) con detectores
- [ ] B2: Separar geometría de setup contextual — el profesor ya lo hace, validar que es correcto
- [ ] B3: Validar fronteras con datos reales — CORRIDO (0.60/0.50 ratio, wick 0.40, fronteras OK)
- [ ] B4: Fijar prioridad de contratos — qué regla gana cuando hay desacuerdo
- [ ] B5: Fijar reloj (available_at, confirmation_time) — profesor tiene lógica, validar con datos
- [ ] B6: Documentar contradicciones resueltas

### Fase 2 — Ejemplos causales (después de F1)
- [ ] C1-C5: Inventario de fuentes, episodios positivos/negativos/ambiguos, conteos por clase

### Fase 3 — Representación (después de F2)
- [ ] D1-D5: Lector/tensor, normalización TRAIN-only, separar salidas profesor de entradas alumno

### Fase 4 — Aprendizaje gradual (después de F3)
- [ ] E1-E6: Baseline regla congelada, tabular, GRU, 3 semillas, early stopping

### Fase 5 — Examen independiente (después de F4)
- [ ] F1-F5: Reproducir evaluación, medir FP/omisiones/abstenciones, ablaciones, dictamen

### Fase 6 — Entrega educativa (después de F5)
- [ ] G1-G3: Replay, ficha por caso, tabla de fallos

---

## 10. Conclusión

**La IA NO comprende actualmente qué es desplazamiento ICT.** Comprende "movimiento grande con cuerpo dominante" (geometría) pero no la tríada completa (geometría + ruptura de estructura + contexto narrativo ICT).

La evidencia empírica muestra que **0.43% de velas** tiene la tríada completa. El corpus de entrenamiento actual no tiene negativos, no tiene salida específica para displacement, y tiene un bug (1e-9) que genera falsos positivos.

El plan maestro (PLAN_APRENDIZAJE_DESPLAZAMIENTO_V1.md) existe y está aprobado como planificación, pero **ninguna fase se ha ejecutado**. Las fases 1 y 2 pueden avanzar en paralelo inmediatamente.

**La diferencia entre "IA que detecta velas grandes" y "IA que reconoce desplazamiento ICT con contexto" es el 99.57% de las velas que tienen geometría pero no contexto.**
