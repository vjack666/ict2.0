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

100% de los tests anti-look-ahead deben pasar. Una prueba mínima debe demostrar que añadir datos posteriores al timestamp de una decisión no cambia la decisión histórica anterior.

### Gate obligatorio 4 — Integración

FVG/OB deben integrarse con Swing/BOS/CHOCH sin romper los tests existentes.

### Gate obligatorio 5 — Lineage

Una señal candidata debe poder explicar su cadena causal hasta los objetos que la originaron. Una señal sin lineage completo no se considera lista para entrenamiento.

### Gate obligatorio 6 — Ablación

Ejecutar como mínimo baseline Swing/BOS/CHOCH; baseline + FVG; baseline + OB; baseline + FVG + OB. Publicar métricas comparables.

### Gate obligatorio 7 — Evidencia empírica

Objetivo preferente: mejora ≥10% en PF o expectancy en desarrollo; OOS sin degradación >5% frente al baseline cuando exista suficiente data; drawdown no peor en >10%; resultados reproducibles.

Si no se logra una mejora, Hermes debe seguir iterando en detección, clasificación, lineage y ejecución antes de declarar fracaso, salvo que la evidencia demuestre que la hipótesis no aporta edge.

### Gate obligatorio 8 — Documentación y trazabilidad

La documentación forma parte del gate de cada fase y experimento.

Después de **cada fase, experimento, auditoría, backtest, cambio de arquitectura, cambio de umbral o corrección que afecte resultados**, Hermes DEBE actualizar antes de continuar:

1. `.hermes-index.md` — cuadro maestro del estado.
2. `.hermes-worklog/<timestamp>_<evento>.md` — evidencia detallada.
3. La auditoría/reporte correspondiente.
4. SDD, plan o contrato si la evidencia modifica una decisión normativa.

Cada registro debe incluir como mínimo: objetivo, hipótesis, cambios, tests, dataset/ventana, configuración, métricas baseline/variante, resultado del gate, problemas, decisión, archivos modificados, commit SHA y siguiente acción.

**Si `.hermes-index.md`, auditoría o worklog no están sincronizados con la evidencia real, el gate de la fase/experimento es FAIL.**

## 3. Política de iteración

Estado inicial: `IN_PROGRESS`.

```text
AUDIT → IMPLEMENT → TEST → BACKTEST → COMPARE
→ AUDIT RESULTADO → UPDATE INDEX + WORKLOG + REPORTS
→ COMMIT → GATE

PASS → siguiente fase
FAIL → DIAGNOSE → FIX / REVERT → repetir
```

No se permite `DONE` mientras exista un gate obligatorio rojo o documentación desactualizada.

## 4. Política de regresión

Si FVG/OB mejora una métrica pero rompe una funcionalidad previa, se considera FAIL. Si una modificación mejora in-sample pero degrada OOS, no se acepta como mejora final. Si una regla sólo funciona en una ventana temporal, debe etiquetarse como régimen-específica y no convertirse en regla universal sin evidencia.

## 5. Política de datos

Nunca fabricar resultados. Si `data/raw/EURUSD_M5.parquet` no está disponible en el entorno de ejecución, registrar el bloqueo y usar sólo datasets/fixtures existentes. Cuando el dataset sea accesible, auditarlo antes de cualquier conclusión.

## 6. Política ICT

El sistema operativo queda centrado en:

`liquidity + sweep + displacement + structure + FVG + OB + retest + structural execution`.

OTE, Fibonacci 62–79% y equivalentes quedan prohibidos. Premium/Discount puede conservarse como contexto si el SPEC vigente lo exige, pero no puede utilizarse para recrear OTE.

## 7. Política de cambios

Hermes debe preferir cambios pequeños, verificables y reversibles. Cada fase debe poder aislarse mediante tests y commits. No debe reescribir grandes partes del motor sin evidencia de que el diseño actual lo impide. No debe cambiar retrospectivamente los criterios de éxito después de observar resultados.

## 8. Entrega final

La entrega final debe contener código, tests, resultados de backtest, comparación de ablación, reporte OOS si aplica, documentación, auditorías, `.hermes-index.md` actualizado, worklogs completos y commits reproducibles.

El cierre debe indicar explícitamente cada gate como `PASS` o `FAIL` y enlazar los reportes generados.
