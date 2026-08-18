# SDD — Context State / Multi-Timeframe Navigation

**Estado:** NORMATIVO (borrador de arquitectura — **no** autoriza entrenamiento multi-TF ni entry)  
**Fecha:** 2026-08-18  
**Extiende:** `SDD_FVG_OB_ARCHITECTURE_MAP.md`, `PLAN_HERMES_FVG_OB.md`, `SPEC_TESIS_FORMAL.md`  
**Motivo:** separar *contexto HTF* de *timing LTF* antes de que cualquier agente “se pasee” entre temporalidades.

---

## 1. Precisión sobre la evidencia interna (obligatoria)

El experimento multi-factor H1 20Y (**congelado**: `docs/EXP_MULTIFACTOR_H1_20Y.md`) midió:

```text
alineación EMA20/50 H4+D1 + FVG → outcome +24 H1  ≈ 50% (a veces peor)
```

### Lo que **sí** demuestra

- El **proxy** `EMA20 > EMA50` como “HTF bias” **no** produjo edge de **entrada direccional inmediata** tras un FVG a +24 H1.

### Lo que **no** demuestra

| Afirmación incorrecta | Por qué es incorrecta |
|-----------------------|------------------------|
| “HTF no tiene edge” | Solo se probó un proxy pobre |
| “ICT HTF no sirve” | No se midió structure/POI/dealing range/liquidity HTF |
| “Multi-TF está falsado” | Se falsó co-ocurrencia de flags + EMA, no navegación jerárquica |

**Norma:** ningún documento posterior puede citar el EXP multi-factor como rechazo del HTF ICT; solo como rechazo del proxy EMA para entry edge a +24 H1.

---

## 2. Separación conceptual: no un solo “edge HTF”

El HTF **no** debe modelarse como:

```text
HTF → “compra ahora”
```

Se modela como productor de **estado de contexto** que condiciona localización, selección, régimen, dirección condicional, trayectoria y riesgo.

### 2.1 Location edge (localización)

HTF responde: *si busco operaciones, ¿dónde merece la pena mirar?*

```text
D1 zona / POI / dealing range
        ↓
      H4 estructura interna
        ↓
   H1 / M15 trigger
```

No es entry edge. Es restricción espacial del universo.

### 2.2 Selection edge (selección)

HTF puede no mover 50% → 60% en cada señal, pero sí:

```text
10.000 señales LTF  →  2.000 situaciones con contexto admisible
```

Reduce el universo; el LTF decide el timing dentro de ese subconjunto.

### 2.3 Regime edge (régimen)

HTF etiqueta el **tipo de mercado**, no el signo de las próximas 24 velas:

| Ejemplo estado | Lectura |
|----------------|---------|
| D1 tendencia + H4 expansión + H1 retroceso | Un régimen |
| D1 rango + H4 compresión + H1 reversión | Otro régimen |

La IA puede cambiar política (umbral, tamaño, si opera) según régimen.

### 2.4 Conditional direction edge (dirección condicional)

Hipótesis medible (con proxies **no-EMA**):

```text
P(outcome | HTF_bullish, setup_long)
  vs
P(outcome | HTF_bearish, setup_long)
```

HTF bias debe construirse con **estructura / liquidez / dealing range / BOS-CHOCH / displacement**, no con EMA20/50 como definición operativa.

### 2.5 Path / target edge (trayectoria)

HTF informa **objetivos e invalidaciones naturales**:

```text
D1 POI  →  H4 liquidity pool  →  H1 setup  →  target = siguiente liquidez HTF
```

Aporta ENTRY / TARGET / INVALIDATION, no solo dirección del close +24.

### 2.6 Risk edge (riesgo)

Incluso con win-rate similar, setups en POI D1 vs mitad de rango pueden diferir en MAE, MFE, distancia a target, stop estructural y sizing.

HTF puede mejorar el **perfil de riesgo** sin mejorar el hit-rate.

---

## 3. Hipótesis prioritaria para ICT 2.0

Encadena evidencia interna ya obtenida:

```text
FVG solo              ≈ 50%
OB→FVG causal         ≈ 50%   (lineage sí; predictivo aislado no)
Flags co-ocurrentes   ≈ 50%   (congelado)
Secuencia COMPLETE    n insuficiente
```

**Siguiente hipótesis (la más alineada con el motor):**

```text
SECUENCIA (liq → sweep → disp → BOS/CHOCH → OB → FVG → retest)
    +
CONTEXTO HTF (location + regime + constraints)
        ↓
¿cambia la distribución del outcome
 (win, R, MAE/MFE, path a liquidez)?
```

No se prueba con más flags EMA. Se prueba con **estado multinivel + secuencia**.

---

## 4. Arquitectura: Market State multinivel (no un scalar bias)

```text
                    MARKET STATE
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
         D1             H4             H1/LTF
      CONTEXTO       ESTRUCTURA        SETUP
          │              │              │
       POI/rango      BOS/CHOCH     Displacement
       Liquidez       Liquidez      FVG/OB
       Bias           Bias          Retest
          │              │              │
          └──────────────┼──────────────┘
                         ▼
              DECISIÓN / POLÍTICA (no entry automática)
```

### 4.1 Mapa de restricciones (salida preferida del HTF)

En lugar de `bias = 0.72`, el HTF emite **constraints** auditables:

```text
D1:
  direction = bullish | bearish | range | unknown
  poi_zones = [...]
  liquidity_targets = [...]
  dealing_range = {...}

H4:
  structure = ...
  state = expansion | retracement | compression | ...

H1:
  sequence_depth = ...
  active_fvg / ob / links = ...

LTF:
  waiting_retest = true | false
```

Flujo de decisión:

```text
CONTEXTO → RESTRICCIONES → OPORTUNIDAD → TRIGGER → RISK/TARGET → OUTCOME
```

### 4.2 Navegación jerárquica temporal (definición de “pasearse”)

**No** es concatenar features D1+H4+H1 en un vector tabular.

**Sí** es un grafo/árbol de preguntas:

```text
D1  → ¿Hay contexto relevante?
H4  → ¿Dónde estoy dentro del contexto?
H1  → ¿Hay estructura / secuencia?
LTF → ¿Hay trigger / retest?
```

La IA **sube o baja** de TF según la pregunta; no “mezcla” timestamps de velas no cerradas.

### 4.3 Anti-look-ahead multi-TF (norma)

Al timestamp de decisión en TF de ejecución \(t\):

- Solo velas **cerradas** de HTF con `close_time ≤ t`.
- Ningún pivot HTF centrado que use barras futuras respecto de \(t\).
- El stacking es **lectura de estado**, no reescritura del pasado LTF.

Hasta que exista contrato ejecutable de capas `htf / itf / exec_tf` separados (deuda en tesis formal), el “paseo” de la IA **no está autorizado** en código de producción ni en entrenamiento con labels de entry.

---

## 5. Matriz de hipótesis a medir (orden de investigación)

| Tipo de edge | Pregunta operativa | Prioridad |
|--------------|-------------------|-----------|
| Location | ¿Setups dentro de POI HTF tienen mejor distribución (R/MAE/path)? | Alta |
| Selection | ¿El filtro HTF reduce malas sin destruir buenas (n y calidad)? | Alta |
| Regime | ¿El outcome del mismo setup cambia por estado HTF? | Alta |
| Sequence + context | ¿La misma profundidad de secuencia rinde distinto bajo distinto contexto HTF? | **Máxima** |
| Conditional direction | ¿Long vs short según estructura HTF (no EMA)? | Media |
| Path | ¿Mejora la elección de target/invalidación HTF? | Media |
| Risk | ¿Mejora MAE/R:R/DD sin subir win-rate? | Media |
| Timing | ¿La navegación HTF→LTF mejora el punto de entrada? | Tras las anteriores |

**Métricas mínimas por hipótesis:** n efectivo, independencia, stop/target fijos cuando se hable de R, baseline LTF-only, intervalos; no solo `end>0` a +24.

---

## 6. Qué queda prohibido / bloqueado

| Acción | Estado |
|--------|--------|
| Usar EMA20/50 como definición normativa de HTF bias | **Prohibido** como conclusión de tesis; solo ablación histórica |
| Declarar edge HTF por el EXP multi-factor | **Prohibido** |
| Entrenar IA a “pasearse” multi-TF sin este SDD + contrato de capas + PIT | **Bloqueado** |
| Convertir Context State en señal de entrada automática | **Bloqueado** (igual que FVG_OB_CAUSAL ≠ entrada) |
| Backtest de rendimiento multi-TF | Sigue sujeto a pila A0–A9 + gates del plan |

---

## 7. Relación con el plan Hermes

| Fase plan | Cómo encaja este SDD |
|-----------|----------------------|
| D (relación causal) | Secuencia + lineage LTF |
| D-extension / sequential engine | Objeto de timing |
| **Este SDD** | Capa de **contexto** antes de E (ejecución) |
| E (retest entry, SL/TP) | Consume restrictions HTF + trigger LTF |
| F–G (ablación / OOS) | Miden la matriz de la §5 |

Cadena objetivo actualizada (lectura, no implementación completa):

```text
HTF Context State (location, regime, constraints)
        ↓
SEQUENCE (liq → sweep → disp → BOS/CHOCH → OB → FVG → retest)
        ↓
LTF confirmation / trigger
        ↓
RISK / TARGET (path HTF)
        ↓
OUTCOME (medible; no asumido)
```

---

## 8. Gate de aceptación de este documento

PASS documental cuando:

1. Este archivo esté en `main` y referenciado desde `.hermes-index.md`.
2. El índice deje de tratar “siguiente = solo secuencia” como si no estuviera explorada.
3. Quede explícito: **Context State ≠ entry**; **EMA proxy ≠ HTF ICT**.
4. Ningún entrenamiento multi-TF arranque sin contrato de capas + anti-look-ahead cruzado.

---

## 9. Siguiente trabajo de ingeniería (después de este SDD)

1. `CONTRATO_MULTI_TF_LAYERS.md` — `htf` / `itf` / `exec_tf`, timestamps cerrados.  
2. Implementar **Context State** mínimo (structure + liquidity HTF, sin EMA normativa).  
3. Experimento: `SEQUENCE depth ≥ k × Context State` → distribución de outcome (con stop fijo).  
4. Solo entonces: políticas de navegación para la IA (grafo de contexto), no labels de “buy/sell” crudos multi-TF.
