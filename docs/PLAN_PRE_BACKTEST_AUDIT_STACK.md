# Plan de Auditorías Pre-Backtest — ICT FVG/OB

**Estado:** PROPUESTA NORMATIVA — sustituye el backtest temprano como siguiente objetivo
**Última actualización:** 2026-08-18
**Objetivo:** demostrar que datos, semántica, causalidad, detectores, relaciones y distribución del motor son suficientemente confiables antes de evaluar una estrategia con un backtest.

## 1. Decisión

El backtest deja de ser el siguiente Gate inmediato. Antes se ejecutará una **pila de auditorías pre-backtest**.

El backtest no se elimina: queda condicionado a que la pila pre-backtest pase sus Gates.

## 2. Orden obligatorio

```text
A0 Data Integrity Audit
        ↓
A1 Schema / Canonical Data Audit
        ↓
A2 Temporal & Point-in-Time Audit
        ↓
A3 Semantic / Contract Audit
        ↓
A4 Detector & Metamorphic Audit
        ↓
A5 Cross-Timeframe Alignment Audit
        ↓
A6 Lineage / Causal Audit
        ↓
A7 Funnel Audit
        ↓
A8 Coverage / Regime / Concentration Audit
        ↓
A9 Selection & Experiment Governance Audit
        ↓
BACKTEST ELIGIBLE
```

No se permite saltar A0-A7 para obtener métricas de rentabilidad.

## 3. Auditorías

### A0 — Data Integrity
Verifica existencia, formato, timestamps, duplicados, orden, OHLC invariantes, NaN/inf, gaps, escala, timezone, rango y hash/versionado.

**Gate:** cero corrupción crítica; toda excepción documentada.

### A1 — Schema / Canonical Data
Verifica que todos los loaders produzcan el mismo contrato (`time, open, high, low, close`), unidades de precio consistentes y ninguna ruta alternativa silenciosa.

**Gate:** un único contrato canónico por dataset.

### A2 — Temporal / Point-in-Time
Verifica que cada objeto, feature y relación sólo use información disponible en su `observation_time`. Incluye truncation/prefix invariance y detección de joins futuros.

**Gate:** cero violaciones de causalidad.

### A3 — Semantic / Contract
Compara implementación contra los contratos FVG/OB y la tesis. Detecta ambigüedad, campos obligatorios ausentes, tipos inventados y mezcla de conceptos legacy.

**Gate:** cada detector tiene una definición única y verificable.

### A4 — Detector / Metamorphic
No sólo prueba ejemplos. Prueba propiedades: invariancia por prefijo, monotonicidad temporal, ausencia de duplicados, sensibilidad controlada a modificaciones que deberían/no deberían cambiar el resultado y casos límite.

**Gate:** propiedades críticas PASS.

### A5 — Cross-Timeframe Alignment
Verifica HTF→ITF→EXEC: timestamps, ventanas cerradas, as-of joins, propagación de objetos y ausencia de uso de una vela HTF todavía abierta.

**Gate:** cero alineaciones futuras.

### A6 — Lineage / Causal
Audita `parent → child`, relaciones, huérfanos, ciclos, duplicados y trazabilidad de setups.

**Gate:** todo setup candidato es reconstruible desde sus eventos.

### A7 — Funnel Audit
Mide el embudo causal sin optimizar rentabilidad:

```text
market bars
→ structure
→ BOS/CHOCH/MSS
→ displacement
→ FVG
→ OB
→ FVG+OB / confluence
→ valid lineage
→ candidate setup
```

Cada etapa reporta conteo absoluto, tasa de paso, tasa de rechazo y razones de rechazo. Se segmenta por dirección, timeframe, tipo de OB y contexto.

**Gate:** no se exige una tasa de éxito arbitraria; se exige consistencia, explicabilidad, ausencia de explosiones/colapsos inexplicables y reproducibilidad.

### A8 — Coverage / Regime / Concentration
Audita dónde aparecen los objetos: tendencia, rango, volatilidad, sesión, año, dirección y régimen. Detecta concentración accidental en pocas fechas o periodos.

**Gate:** toda concentración material queda explicada y documentada antes del backtest.

### A9 — Selection / Experiment Governance
Audita que los umbrales no hayan sido elegidos mirando resultados de performance. Registra versiones, parámetros, semillas, datasets y número de experimentos exploratorios.

**Gate:** snapshot congelado de la especificación antes del backtest.

## 4. Auditorías que NO deben adelantarse

Estas pertenecen a una etapa posterior y no se deben presentar como pre-backtest:

- Sharpe/Sortino/Profit Factor.
- PBO/DSR/PSR.
- Monte Carlo de trades.
- Walk-forward de estrategia.
- OOS de performance.
- optimización de parámetros.

Son válidas después de existir una ejecución reproducible y un conjunto de resultados. SMC-SYSTEMS contiene implementaciones de algunas de estas técnicas, pero su existencia no justifica ejecutarlas antes de tener un motor de ejecución estable. Su Completion Report registra, entre otras, PurgedKFold, CVaR, DSR y PBO. Eso es material de validación posterior, no sustituto de las auditorías estructurales. 

## 5. Funnel como Gate central

El Funnel no debe responder "¿gana dinero?". Debe responder:

> ¿El motor transforma el mercado en una población de objetos ICT coherente, causal, reproducible y auditable?

Una tasa de paso alta no es buena por sí misma. Una tasa baja tampoco es mala. El objetivo es detectar comportamientos imposibles, sesgos de implementación, objetos huérfanos, concentración artificial y pérdidas de población no explicadas.

## 6. Criterio de BACKTEST ELIGIBLE

Sólo se habilita backtest cuando:

- A0-A6 = PASS;
- A7 Funnel = PASS;
- A8 = PASS o WARN formalmente aceptado y documentado;
- A9 = PASS;
- dataset y configuración quedan congelados;
- existe evidencia reproducible de los Gates;
- no quedan blockers críticos.

## 7. Referencia comparativa SMC-SYSTEMS

`vjack666/SMC-SYSTEMS` se utiliza como fuente comparativa. Se rescatan ideas sólo si mejoran una auditoría del ICT y pasan pruebas propias. No se copia su arquitectura completa ni se toma su backtest como evidencia de edge del ICT.

El Completion Report de SMC-SYSTEMS documenta validación de integración, split cronológico, backtest, walk-forward y técnicas cuantitativas posteriores; también muestra por qué una métrica de performance puede existir con una muestra pequeña. Esto refuerza nuestra decisión de auditar primero el pipeline y el funnel antes de interpretar performance.
