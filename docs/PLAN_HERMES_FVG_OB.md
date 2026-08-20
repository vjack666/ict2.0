# PLAN DE TRABAJO HERMES — FVG + ORDER BLOCKS

**Proyecto:** ict2.0  
**Fecha:** 2026-08-17  
**Estado:** AUTORIZADO PARA EJECUCIÓN AUTÓNOMA  
**Owner:** Jack / Hermes  
**Objetivo:** evolucionar el motor ICT existente, que ya dispone de Swing/BOS/CHOCH, para incorporar FVG y Order Blocks como objetos de mercado relacionados causalmente con liquidez, displacement y estructura.

---

## 1. Objetivo final

Construir un motor ICT que no trate FVG/OB como simples booleanos, sino como **objetos de mercado con ciclo de vida, temporalidad, genealogía y relaciones con eventos estructurales**.

Cadena objetivo:

`HTF bias → liquidity → sweep → displacement → BOS/CHOCH/MSS → FVG/OB → POI → retest → entry → structural SL → opposing liquidity TP`

OTE queda fuera del modelo operativo y no puede reintroducirse bajo otro nombre.

---

## 2. Resultado que Hermes debe entregar

Al finalizar, el repositorio debe disponer de:

1. Detector FVG robusto y sin look-ahead.
2. Detector OB robusto y sin look-ahead operativo.
3. Clasificación de OB y Breaker conforme a la tesis vigente.
4. Ciclo de vida de FVG/OB: created, active, mitigated/partially mitigated, invalidated, aged/expired cuando corresponda.
5. Genealogía: sweep → displacement → structure event → FVG/OB → POI.
6. Relación OB + FVG/BPR.
7. Stacking multi-TF sin contaminar el tiempo de ejecución.
8. POI como objeto de calidad, no como filtro duro salvo que un contrato explícito lo establezca.
9. Entrada basada en retorno/retest a la zona, no en el close del BOS.
10. Tests unitarios, de integración, temporales y anti-look-ahead.
11. Backtest con ablación: baseline Swing/BOS/CHOCH vs +FVG vs +OB vs +FVG+OB.
12. Evaluación OOS cuando exista dataset suficiente.
13. Documentación actualizada y bitácora de cada iteración.

---

## 3. Datos

Dataset prioritario: `data/raw/EURUSD_M5.parquet` si está disponible para el entorno de ejecución. Si no está disponible, Hermes debe documentar el bloqueo y utilizar fixtures/datasets existentes para pruebas estructurales; **no debe inventar resultados de backtest**.

La data debe auditarse antes de usarla: OHLC, timestamps, timezone, duplicados, gaps, orden temporal y cantidad de observaciones.

---

## 4. Fases de ejecución

### Fase A — Auditoría

- Mapear engine, detectors, signals, backtest y tests.
- Identificar implementación actual de Swing/BOS/CHOCH.
- Identificar cualquier FVG/OB existente.
- Identificar OTE/Fibonacci residual.
- Documentar puntos de entrada, SL, TP y pipeline.

**Gate A:** no modificar arquitectura sin conocer el flujo real.

### Fase B — Contratos de dominio

Crear/ajustar estructuras para FVG, OB, Breaker, BPR/POI y relaciones.

Cada objeto debe conservar como mínimo: id, dirección, TF, timestamps de creación/confirmación/tradabilidad, límites de zona, estado, edad, mitigación, invalidación y referencias a eventos causales.

**Gate B:** objetos serializables, deterministas y testeables.

### Fase C — Detección

Implementar o corregir FVG y OB usando únicamente información disponible al momento de confirmación.

Separar:

- candidate_time;
- confirmation_time;
- tradable_time.

**Gate C:** suite anti-look-ahead pasa al 100%.

### Fase D — Relación causal

Construir relaciones:

- sweep → displacement;
- displacement → FVG;
- displacement → OB;
- structure event → POI;
- OB + FVG → BPR;
- OB roto + cambio de estructura → Breaker;
- multi-TF stacking.

**Gate D:** ninguna relación puede usar información futura respecto de `tradable_time`.

### Fase E — Ejecución

Cambiar la lógica para que la señal pueda esperar el retorno/retest del POI. No entrar automáticamente en el close del BOS si el contrato de ejecución exige retorno.

SL debe permanecer estructural y TP debe apuntar a liquidez opuesta conforme al contrato vigente.

**Gate E:** tests de secuencia y backtest temporal pasan.

### Fase F — Aprendizaje y ablación

Generar cohortes comparables:

A. Swing + BOS + CHOCH  
B. A + FVG  
C. A + OB  
D. A + FVG + OB  
E. A + sweep + displacement + FVG + OB

Medir al menos: número de trades, win rate, expectancy/R, PF, MFE, MAE, drawdown y distribución de resultados.

**Gate F:** no aceptar una mejora basada únicamente en in-sample.

### Fase G — OOS y robustez

Si hay suficiente historial, separar entrenamiento/desarrollo de OOS. Repetir por ventanas temporales y, cuando sea viable, por régimen.

**Gate G:** el comportamiento debe ser reproducible y no depender de una ventana única.

### Fase H — Documentación y cierre

Actualizar tesis/reglas afectadas, contratos de código, tests y bitácora. Registrar qué se cambió, qué pruebas se ejecutaron y qué resultados se obtuvieron.

**Gate H:** sólo cerrar la tarea cuando todos los gates obligatorios estén verdes.

---

## 5. Bucle autónomo obligatorio de Hermes

Hermes debe trabajar en ciclos:

`INSPECT → IMPLEMENT → TEST → BACKTEST → EVALUATE → FIX → TEST AGAIN`

No debe detenerse después de una implementación si el gate de aceptación falla.

Reglas:

1. Si falla un test funcional → corregir y repetir.
2. Si aparece look-ahead → detener la aceptación de esa implementación, corregir y repetir.
3. Si falla una métrica de calidad → investigar la causa, modificar y repetir.
4. Si una hipótesis no mejora el edge → conservarla sólo si mejora la capacidad estructural sin degradar el baseline; de lo contrario revertirla.
5. No maquillar métricas eliminando trades o cambiando la definición de éxito después de observar resultados.
6. Cada iteración debe quedar registrada.
7. No declarar DONE hasta satisfacer el contrato de aceptación.

---

## 6. Objetivo empírico

El objetivo no es maximizar PF en una sola muestra. El objetivo es **mejorar la calidad del motor mediante información ICT causal y demostrar que FVG/OB aportan valor sin introducir look-ahead ni degradación material del baseline**.

Criterio de aceptación empírico preferente:

- PF o expectancy mejora ≥10% frente al baseline en desarrollo; y
- OOS no presenta degradación >5% frente al baseline en PF/expectancy; y
- drawdown no empeora >10%; y
- la mejora conserva una muestra razonable de operaciones.

Si no se alcanza la mejora cuantitativa, Hermes debe continuar iterando sobre detección, clasificación, lineage y ejecución hasta agotar las hipótesis razonables documentadas. **No puede afirmar éxito sólo porque los tests unitarios pasen.**

Si la evidencia demuestra que una determinada regla reduce el edge, debe eliminarse o degradarse a feature medible en lugar de convertirse en filtro duro.

---

## 7. Prohibiciones

- No OTE.
- No Fibonacci como sustituto de OTE.
- No look-ahead.
- No entrar usando una zona antes de `tradable_time`.
- No usar información HTF futura para validar una entrada histórica.
- No convertir FVG/OB en gates duros sin evidencia y contrato.
- No optimizar parámetros exclusivamente sobre la misma muestra usada para evaluar.
- No modificar el SPEC para hacer que una implementación incorrecta parezca correcta.

---

## 8. Criterio final de DONE

La tarea sólo está DONE cuando:

- código implementado;
- tests verdes;
- anti-look-ahead verde;
- backtest reproducible;
- ablación ejecutada;
- OOS ejecutado cuando los datos lo permitan;
- métricas comparadas contra baseline;
- documentación actualizada;
- bitácora completa;
- cambios comprometidos al repositorio.

Si algún punto falla, Hermes vuelve al ciclo de trabajo.
