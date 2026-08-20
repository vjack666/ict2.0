# SDD — Context State / Multi-Timeframe Navigation

**Estado:** NORMATIVO — arquitectura vigente; no autoriza entry ni entrenamiento multi-TF de ejecución  
**Fecha:** 2026-08-20 (sincronización de estado)  
**Extiende:** `SDD_FVG_OB_ARCHITECTURE_MAP.md`, `PLAN_HERMES_FVG_OB.md`, `SPEC_TESIS_FORMAL.md`  
**Evidencia reciente:** Funnel MTF+Sequence 20Y cerrado con gate CI; TNA trace estratificado PASS; experimento Sequence×Context State INSUFFICIENT_N.

---

## 1. Precisión sobre la evidencia interna (obligatoria)

El experimento multi-factor H1 20Y congelado midió un proxy basado en EMA20/50 y no encontró edge de entrada direccional inmediata a +24 H1.

**No demuestra:** que HTF no tenga edge, que ICT HTF no sirva, ni que la navegación jerárquica esté falsada.

**Norma:** ningún documento posterior puede citar ese experimento como rechazo del HTF ICT. Solo rechaza el proxy EMA para ese outcome/horizonte.

La evidencia posterior cambió el estado de ingeniería: el Context State ya tiene contrato v1, el Funnel MTF+Sequence 20Y está cerrado con gate, y existe una auditoría temporal AHF con PASS de integridad en muestra estratificada. Eso **no** constituye evidencia de edge.

---

## 2. Separación conceptual: no un solo “edge HTF”

El HTF produce **estado de contexto** que condiciona localización, selección, régimen, dirección condicional, trayectoria y riesgo.

```text
HTF → contexto / restricciones
ITF → estructura / zona
EXEC → confirmación / timing
```

### 2.1 Location

HTF responde dónde merece la pena mirar; no produce una entrada automática.

### 2.2 Selection

El contexto puede reducir el universo sin aumentar necesariamente el win-rate bruto.

### 2.3 Regime

HTF etiqueta régimen estructural/geométrico; no se define con EMA normativa.

### 2.4 Conditional direction

Hipótesis medible con estructura/liquidez/dealing range/BOS-CHOCH, no EMA20/50.

### 2.5 Path / target

HTF puede informar trayectorias de liquidez e invalidaciones naturales; todavía no constituye una regla de ejecución.

### 2.6 Risk

El contexto puede cambiar MAE/MFE, distancia a target y riesgo aunque no cambie el hit-rate.

---

## 3. Hipótesis prioritaria

La hipótesis prioritaria sigue siendo:

```text
SEQUENCE (liq → sweep → disp → BOS/CHOCH → OB → FVG → retest)
    +
CONTEXTO HTF (location + regime + constraints)
        ↓
¿cambia la distribución del outcome?
```

Ya existe una primera corrida `SEQUENCE × CONTEXT STATE` en H1 20Y, pero su gate es **INSUFFICIENT_N**: 24 cadenas deduplicadas de depth≥4, con buckets demasiado pequeños para declarar diferencia de distribución.

Por tanto, la hipótesis queda **ABIERTA**, no aceptada ni falsada.

---

## 4. Arquitectura: Market State multinivel

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

La salida normativa es un mapa de restricciones auditable, no un scalar de bias.

---

## 4.1 Navegación jerárquica / AHF

El AHF es una máquina de estados jerárquica dirigida por eventos:

```text
WAIT_D1
  ↓ D1_PASS
D1_LOCKED
  ↓
WAIT_H4
  ↓ H4_PASS
H4_LOCKED
  ↓
WAIT_H1
  ↓ H1_PASS
WAIT_LTF
  ↓ LTF_CONFIRMATION
SETUP_READY
```

Reglas:

1. Una capa inferior solo queda habilitada después de confirmación de la superior.
2. El contexto confirmado queda congelado como snapshot hasta invalidación explícita.
3. La capa activa responde la pregunta operativa; las demás aportan solo snapshots legales.
4. Una invalidación superior retrocede el estado y conserva el evento de transición.
5. No se borra historial para maquillar la trayectoria.
6. `Context State`, `constraints` y `navigation state` no son entradas.
7. El trace debe conservar estado, `active_tf`, contexto confirmado, evento/tiempo de transición, parent state y causa de invalidación.

El AHF está **implementado v1** y existe evidencia de auditoría temporal en `reports/audits/AUDITORIA_TEMPORAL_AHF_RESULT.json`: estado `PASS_TRACE_INTEGRITY`, 750 trazas, 501 transiciones y 193 invalidaciones. Esta evidencia es **estratificada**, no una validación full-span conductual.

---

## 4.2 Anti-look-ahead multi-TF

En el timestamp de decisión `t`:

- solo velas cerradas con `close_time ≤ t`;
- ningún pivot HTF que use futuro respecto de `t`;
- stacking como lectura de estado, no reescritura del pasado;
- cada transición usa evidencia disponible en el snapshot `as-of(t)` de la capa activa y snapshots ya confirmados de ancestros;
- una invalidación usa evidencia posterior a la confirmación, nunca una observación futura introducida retrospectivamente.

El contrato v1 de Context State prohíbe EMA/ATR/OTE como bias normativo y define `location` únicamente como `DISCOUNT | EQ | PREMIUM`.

---

## 5. Matriz de hipótesis

| Tipo | Pregunta | Prioridad |
|---|---|---:|
| Location | ¿POI HTF cambia distribución de R/MAE/path? | Alta |
| Selection | ¿Reduce malas sin destruir buenas? | Alta |
| Regime | ¿El mismo setup cambia por régimen HTF? | Alta |
| Sequence + context | ¿La misma profundidad rinde distinto bajo distinto contexto? | **Máxima** |
| Conditional direction | ¿Long/short según estructura HTF no-EMA? | Media |
| Path | ¿Mejora target/invalidación? | Media |
| Risk | ¿Mejora MAE/R:R/DD? | Media |
| Timing | ¿HTF→LTF mejora timing? | Después |

Métricas mínimas: n efectivo, independencia, baseline LTF-only, intervalos y reglas temporales congeladas. No basta con `end>0` a un horizonte.

---

## 6. Qué queda prohibido / bloqueado

| Acción | Estado |
|---|---|
| EMA20/50 como definición normativa de HTF bias | **Prohibido** como conclusión; solo ablación histórica |
| Declarar edge HTF por el experimento EMA | **Prohibido** |
| Entrenar IA a navegar multi-TF sin contratos PIT/capas | **Bloqueado** |
| Convertir Context State en entrada automática | **Bloqueado** |
| Backtest de rendimiento | **Bloqueado** hasta pila pre-backtest + Funnel + TNA aceptables |

---

## 7. Relación con el plan Hermes

```text
HTF Context State
        ↓
SEQUENCE
        ↓
LTF confirmation / trigger
        ↓
RISK / TARGET
        ↓
OUTCOME
```

La cadena es una arquitectura objetivo de investigación, no una afirmación de edge.

---

## 8. Gate de aceptación documental

PASS documental cuando:

1. el SDD está en `main` y referenciado desde el índice;
2. no trata “siguiente = solo secuencia” como si no existiera evidencia previa;
3. Context State ≠ entry y EMA proxy ≠ HTF ICT;
4. entrenamiento multi-TF no arranca sin contrato de capas + anti-look-ahead;
5. AHF conserva estados, transiciones, snapshots, invalidaciones y lineage.

**Estado actual:** estos requisitos documentales están implementados; los experimentos de comportamiento y el full-span TNA siguen siendo gates empíricos pendientes.

---

## 9. Siguiente trabajo de ingeniería

1. Mantener/fortalecer `CONTRATO_MULTI_TF_LAYERS.md` para roles `htf / itf / exec_tf`.
2. Consolidar Context State mínimo (structure + liquidity + EQ50, sin EMA normativa).
3. Ejecutar TNA **BEHAVIORAL/full-span** y cerrar su gate, sin confundirlo con el TRACE PASS estratificado.
4. Aumentar n de `SEQUENCE × CONTEXT STATE` hasta que los buckets permitan inferencia válida.
5. Solo después de los gates, abrir la especificación de ejecución/backtest.

No queda como tarea “corregir BOS/CHOCH a pivotes 100% causales”: ese blocker fue corregido y la documentación actual debe reflejarlo como resuelto.
