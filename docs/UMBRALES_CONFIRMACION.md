# Calibración de umbrales de confirmación — BOS / CHOCH / SWING

**Fecha:** 2026-08-17  
**Base:** eventos EURUSD M15/H1/H4/D1 (Yahoo + lógica geométrica alineada a Hermes)  
**Objetivo:** subir precisión de “confirmación real” sin matar recall en HTF.

---

## 1. Problema

Los umbrales actuales de Hermes/motor son **demasiado permisivos en LTF**:

| TF | k actual (excursión) | Precision actual | Confirm base rate |
|----|----------------------|------------------|-------------------|
| M15 | 2.0 R | **28.9%** | 22.4% |
| H1  | 1.8 R | **23.6%** | 18.3% |
| H4  | 1.5 R | 37.5% (n=8) | 27.3% |
| D1  | 1.0 R | 50.0% | 47.4% |

En M15/H1, casi todo lo que “pasa” el k sigue siendo **reclaim** (~75–80%). El gate no discrimina.

---

## 2. Umbrales recomendados (producción)

### 2.1 Excursión mínima para marcar CONFIRM (`EXCURSION_K`)

| TF | k actual | **k calibrado** | Precision esperada | Recall | F1 | Notas |
|----|----------|-----------------|--------------------|--------|-----|-------|
| **M15** | 2.0 | **4.0** | ~37% | ~85% | 0.52 | Mejor F1 k-only; age≤20 ayuda poco |
| **H1**  | 1.8 | **5.0** | ~61% | ~85% | 0.71 | Salto grande de calidad |
| **H4**  | 1.5 | **3.0** | ~100%* | ~100%* | — | *n=3; usar 2.5 si quieres más muestra |
| **D1**  | 1.0 | **2.0** | ~69–71% | ~93% | 0.79–0.81 | age≤30 mejora un poco |

**Regla de código sugerida:**

```python
EXCURSION_K = {
    "M5":  4.5,   # extrapolado (más ruido que M15)
    "M15": 4.0,
    "H1":  5.0,
    "H4":  3.0,
    "D1":  2.0,
}
```

### 2.2 Modos de umbral (usar según contexto)

| Modo | Uso | M15 | H1 | H4 | D1 |
|------|-----|-----|----|----|-----|
| **SCAN** (detección amplia) | inventariar eventos | 2.0 | 1.8 | 1.5 | 1.0 |
| **CONFIRM** (calibrado) | nature label / score | **4.0** | **5.0** | **3.0** | **2.0** |
| **PREMIUM** (alta precisión) | setups que mueven bias | **6.0** | **8.0** | **4.0** | **3.0** |

- **SCAN** = lo que ya tienes (no tirar eventos del log de aprendizaje).  
- **CONFIRM** = gate para `label_confirm=1` y para modular bias.  
- **PREMIUM** = solo eventos que pueden empujar `bias_from_tools` / narrativa.

### 2.3 Clases de score híbrido (0–100)

Sustituir el piso over-calibrado (`is_real +70 → casi todo premium`).

| Clase | Score | Condición adicional obligatoria | Acción en motor |
|-------|-------|----------------------------------|-----------------|
| **premium** | ≥ **90** | nature=confirm (k PREMIUM o k CONFIRM + HTF a_favor) | puede modular bias |
| **useful** | **70–89** | nature=confirm (k CONFIRM) | aviso fuerte, no bias solo |
| **noise** | **< 70** | reclaim / range / sin excursion | ignorar en bias |

Proxy empírico (excursion→score ≈ `clip(exc/10*100, 0, 100)`):

- H1 `premium≥85`: n=9, **confirm 88.9%** → usable.  
- M15 `premium≥85`: n=63, confirm solo **47.6%** → en LTF hace falta **HTF a_favor** o subir a ≥90 + confirm.

**Recomendación LTF (M15/H1):**  
`premium` solo si `score≥90 AND nature=confirm AND htf_bias a_favor`.

### 2.4 CHOCH vs BOS

| Evento | Confirm rate observado | Política |
|--------|------------------------|----------|
| CHOCH M15/H1 | ~22% | **Nunca** mueve bias solo; requiere BOS posterior o nature PREMIUM |
| BOS M15/H1 | ~17–22% | Igual de ruidoso en LTF; filtrar por k CONFIRM + HTF |
| CHOCH/BOS D1 | ~46–47% | Sí puede informar `build_daily_bias` con k≥2.0 |

Alineado a SPEC/Hermes: *CHOCH sin BOS posterior → solo aviso*.

### 2.5 Filtros secundarios (opcionales)

| Filtro | Valor sugerido | Efecto |
|--------|----------------|--------|
| `parent_age` max | M15: **20** barras; D1: **30** | Evita rupturas de swings muy viejos |
| `body_ratio` min | **0.0** en gate confirm (no ayuda mucho en esta data) | Displacement (≥0.5–0.6) mejor como **bonus de score**, no veto |
| BOS validate mode | **`sustained`** (3 cierres en contra) | Ya calibrado por Hermes: 99%→76% invalid |
| Horizonte nature | M15:40, H1:30, H4:20, D1:10 | Mantener |

---

## 3. Mapeo al motor (dónde tocar)

```
tools/
  choch_quality.py      ← EXCURSION_K + umbrales premium/useful/noise
  bos_validate.py       ← default mode="sustained"
  teacher_rubric.py     ← alinear k CONFIRM con rúbrica humana

engine/
  bias_from_tools.py    ← solo premium + HTF a_favor afectan bias
  htf_narrative.py      ← CHOCH = aviso; BOS premium HTF = estructura
```

**Shadow mode (recomendado antes de producción):**

1. Calcular `nature` y `class` con umbrales nuevos.  
2. Loguear Δ vs umbrales viejos.  
3. **No** cambiar `bias` hasta gate B8 del pipeline.

---

## 4. Tabla rápida para copiar al código

```python
# Umbrales de confirmación calibrados 2026-08-17
EXCURSION_K_SCAN = {"M5": 2.0, "M15": 2.0, "H1": 1.8, "H4": 1.5, "D1": 1.0}
EXCURSION_K_CONFIRM = {"M5": 4.5, "M15": 4.0, "H1": 5.0, "H4": 3.0, "D1": 2.0}
EXCURSION_K_PREMIUM = {"M5": 6.0, "M15": 6.0, "H1": 8.0, "H4": 4.0, "D1": 3.0}

SCORE_PREMIUM = 90
SCORE_USEFUL = 70

PARENT_AGE_MAX = {"M15": 20, "H1": 30, "H4": 40, "D1": 30}

# Política bias
# - CHOCH: nunca bias solo
# - BOS/CHOCH premium: solo si htf_bias alineado (a_favor)
# - noise: excluir de narrativa de sesgo
```

---

## 5. Evidencia resumida

| TF | p50 excursion CONFIRM | p50 excursion RECLAIM | Separación |
|----|----------------------|----------------------|------------|
| M15 | 7.30 R | 3.24 R | Clara a partir de ~4 R |
| H1  | 8.73 R | 2.82 R | Clara a partir de ~5 R |
| H4  | 4.23 R | 1.75 R | Clara a partir de ~3 R (n bajo) |
| D1  | 3.67 R | 1.72 R | Clara a partir de ~2 R |

Hermes (M5, data real): **92.8% reclaim** → coherente con M15/H1 aquí (75–82% reclaim).

---

## 6. Próximo paso operativo

1. Aplicar `EXCURSION_K_CONFIRM` en el etiquetado nature (no en el detector de eventos).  
2. Recalcular `human_score` / `choch_class` con `SCORE_PREMIUM=90`.  
3. Comparar distribución premium/useful/noise vs teacher rubric (~80% noise objetivo en LTF).  
4. Retomar pipeline B4 con estos k fijos.  
5. Promover al motor solo tras shadow + walk-forward.

Archivos de soporte:
- `reports/threshold_calibration.json` — métricas del grid search  
- `models/events_{TF}.csv` — eventos usados  
- `reports/LEARNING_REPORT.md` — contexto del modelo
