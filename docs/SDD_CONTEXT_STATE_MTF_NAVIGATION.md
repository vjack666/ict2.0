# SDD — Context State / Multi-Timeframe Navigation

**Estado:** NORMATIVO (borrador de arquitectura — **no** autoriza entrenamiento multi-TF ni entry)  
**Fecha:** 2026-08-18  
**Extiende:** `SDD_FVG_OB_ARCHITECTURE_MAP.md`, `PLAN_HERMES_FVG_OB.md`, `SPEC_TESIS_FORMAL.md`  
**Motivo:** separar *contexto HTF* de *timing LTF* y formalizar la navegación jerárquica antes de que cualquier agente “se pasee” entre temporalidades.

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

### 4.3 AHF — Adaptive Hierarchical MTF Funnel

**Definición normativa:** el Funnel MTF no es un loop secuencial que recorre todos los timeframes en cada vela. Es una **máquina de estados jerárquica, dirigida por eventos**, que navega top-down entre capas temporales. Cada capa tiene condiciones de entrada, condiciones de confirmación y reglas explícitas de invalidación.

La progresión canónica es:

```text
WAIT_D1
  │ D1_PASS
  ▼
D1_LOCKED
  ▼
WAIT_H4
  │ H4_PASS
  ▼
H4_LOCKED
  ▼
WAIT_H1
  │ H1_PASS
  ▼
WAIT_LTF
  │ LTF_CONFIRMATION
  ▼
SETUP_READY
  ▼
OUTCOME
```

Reglas obligatorias:

1. **Una capa inferior sólo queda habilitada después de que la capa superior alcance su estado de confirmación.**
2. Mientras una capa está `LOCKED`, su contexto confirmado se conserva como snapshot y no se reescribe retroactivamente por eventos LTF.
3. La capa activa es la única que responde a la pregunta operativa actual; las demás sólo aportan el estado ya confirmado que sea legal leer.
4. Una invalidación de una capa superior puede hacer retroceder el estado a esa capa:

```text
LTF → H1_INVALIDATED → WAIT_H1
H1  → H4_INVALIDATED → WAIT_H4
H4  → D1_INVALIDATED → WAIT_D1
```

5. El retroceso debe quedar registrado como evento de transición; no se permite “borrar” el contexto previo para maquillar la trayectoria.
6. `Context State`, `constraints` y `navigation state` **no son entradas**. La entrada sólo puede existir después de que E/F definan un trigger y una regla de ejecución explícitos.
7. El AHF debe conservar `state`, `active_tf`, `confirmed_context`, `transition_event`, `transition_time`, `parent_state` e `invalidation_reason` para auditoría.

Ejemplo conceptual:

```text
D1 confirma contexto bullish + POI
        ↓
D1_LOCKED
        ↓
H4 busca estructura compatible
        ↓
H4 confirma → H4_LOCKED
        ↓
H1 busca secuencia
        ↓
H1 confirma profundidad k
        ↓
LTF busca retest/trigger
```

La navegación es **dirigida por preguntas**: la máquina no inspecciona ciegamente todos los TF; resuelve la pregunta de la capa activa y sólo al resolverla habilita la siguiente.

### 4.4 Anti-look-ahead multi-TF (norma)

Al timestamp de decisión en TF de ejecución `t`:

- Solo velas **cerradas** de HTF con `close_time ≤ t`.
- Ningún pivot HTF centrado que use barras futuras respecto de `t`.
- El stacking es **lectura de estado**, no reescritura del pasado LTF.
- Una transición de estado sólo puede utilizar evidencia disponible en el snapshot `as-of(t)` de la capa activa y los snapshots ya confirmados de sus ancestros.
- La invalidación de una capa sólo puede ocurrir por evidencia posterior al momento de confirmación, nunca por una observación futura introducida retrospectivamente.

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
5. La semántica AHF quede versionada: estados, transiciones, snapshots, retroceso por invalidación y evidencia de transición.

---

## 9. Siguiente trabajo de ingeniería (después de este SDD)

1. `CONTRATO_MULTI_TF_LAYERS.md` — `htf` / `itf` / `exec_tf`, timestamps cerrados.  
2. Implementar **Context State** mínimo (structure + liquidity HTF, sin EMA normativa).  
3. Implementar el contrato ejecutable AHF: estados, transiciones, snapshots `as-of`, invalidaciones y lineage de navegación.  
4. Corregir **BOS/CHOCH a pivotes 100% causales** antes de autorizar entrenamiento/navegación IA.  
5. Experimento: `SEQUENCE depth ≥ k × Context State` → distribución de outcome (con stop fijo).  
6. Solo entonces: políticas de navegación para la IA (grafo de contexto), no labels de “buy/sell” crudos multi-TF.
