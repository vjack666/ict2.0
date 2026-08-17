# CONTRATO HERMES — FVG + ORDER BLOCKS

**Contrato:** HERMES-FVG-OB-001  
**Fecha:** 2026-08-17  
**Estado:** ACTIVO  
**Repositorio:** `vjack666/ict2.0`

## 1. Misión

Implementar y validar una capa ICT de FVG + Order Blocks integrada con el motor existente de Swing/BOS/CHOCH, liquidez y displacement.

Hermes tiene autorización para iterar de forma autónoma hasta cumplir los gates de este contrato.

## 2. Definición de éxito

### Gate obligatorio 1 — Corrección funcional

- FVG bullish/bearish correcto según el contrato vigente.
- OB bullish/bearish correcto según el contrato vigente.
- Breaker correctamente relacionado con su OB padre.
- Estados de ciclo de vida correctos.
- BPR/OB+FVG correctamente representado.

### Gate obligatorio 2 — Temporalidad

Cada entidad debe distinguir creación, confirmación y momento tradable. Ninguna señal puede usar la entidad antes de que esté confirmada y disponible.

### Gate obligatorio 3 — Anti-look-ahead

100% de los tests anti-look-ahead deben pasar.

Una prueba mínima debe demostrar que añadir datos posteriores al timestamp de una decisión no cambia la decisión histórica anterior.

### Gate obligatorio 4 — Integración

FVG/OB deben integrarse con Swing/BOS/CHOCH sin romper los tests existentes.

### Gate obligatorio 5 — Lineage

Una señal candidata debe poder explicar su cadena causal hasta los objetos que la originaron. Una señal sin lineage completo no se considera lista para entrenamiento.

### Gate obligatorio 6 — Ablación

Ejecutar como mínimo:

- baseline Swing/BOS/CHOCH;
- baseline + FVG;
- baseline + OB;
- baseline + FVG + OB.

Publicar métricas comparables.

### Gate obligatorio 7 — Evidencia empírica

Objetivo preferente:

- mejora ≥10% en PF o expectancy en desarrollo;
- OOS sin degradación >5% frente al baseline cuando exista suficiente data;
- drawdown no peor en >10%;
- resultados reproducibles.

Si no se logra una mejora, Hermes debe seguir iterando en detección, clasificación, lineage y ejecución antes de declarar fracaso, salvo que la evidencia demuestre que la hipótesis no aporta edge.

### Gate obligatorio 8 — Documentación

Actualizar SDD, contratos afectados, tests y bitácora. Registrar cada experimento que afecte a las métricas.

## 3. Política de iteración

Estado inicial: `IN_PROGRESS`.

Bucle obligatorio:

```text
AUDIT
  ↓
IMPLEMENT
  ↓
TEST
  ↓
BACKTEST
  ↓
COMPARE
  ↓
PASS? ── YES → DOCUMENT → DONE
  │
  NO
  ↓
DIAGNOSE
  ↓
FIX / REVERT
  ↓
REPEAT
```

No se permite `DONE` mientras exista un gate obligatorio rojo.

## 4. Política de regresión

Si FVG/OB mejora una métrica pero rompe una funcionalidad previa, se considera **FAIL**.

Si una modificación mejora in-sample pero degrada OOS, no se acepta como mejora final.

Si una regla sólo funciona en una ventana temporal, debe etiquetarse como régimen-específica y no convertirse en regla universal sin evidencia.

## 5. Política de datos

Nunca fabricar resultados.

Si `data/raw/EURUSD_M5.parquet` no está disponible en el entorno de ejecución, registrar el bloqueo y usar sólo datasets/fixtures existentes. Cuando el dataset sea accesible, auditarlo antes de cualquier conclusión.

## 6. Política ICT

El sistema operativo queda centrado en:

`liquidity + sweep + displacement + structure + FVG + OB + retest + structural execution`.

OTE, Fibonacci 62–79% y equivalentes quedan prohibidos.

Premium/Discount puede conservarse como contexto si el SPEC vigente lo exige, pero no puede utilizarse para recrear OTE.

## 7. Política de cambios

Hermes debe preferir cambios pequeños, verificables y reversibles. Cada fase debe poder aislarse mediante tests y commits.

No debe reescribir grandes partes del motor sin evidencia de que el diseño actual lo impide.

## 8. Entrega final

La entrega final debe contener:

- código;
- tests;
- resultados de backtest;
- comparación de ablación;
- reporte OOS si aplica;
- documentación;
- bitácora;
- commit(s) reproducibles.

El mensaje final de cierre debe indicar explícitamente cada gate como `PASS` o `FAIL` y enlazar los reportes generados.
