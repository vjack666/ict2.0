# HERMES — START HERE

**Contrato operativo:** HERMES-FVG-OB-001  
**Fecha:** 2026-08-17  
**Estado:** ACTIVO  
**Repositorio:** `vjack666/ict2.0`

## 1. INSTRUCCIÓN ÚNICA

Si recibes la orden **"comienza el plan"**, ejecuta exclusivamente el trabajo definido por este documento y sus documentos normativos. No busques tareas laterales ni amplíes el alcance por iniciativa propia.

## 2. ORDEN DE AUTORIDAD

Lee y respeta, en este orden:

1. `docs/00_HERMES_START_HERE.md` — punto de entrada operativo.
2. `docs/CONTRATO_HERMES_FVG_OB.md` — definición contractual de DONE.
3. `docs/PLAN_HERMES_FVG_OB.md` — fases y gates.
4. `docs/SDD_FVG_OB_ARCHITECTURE_MAP.md` — mapa de arquitectura y archivos afectados.
5. `docs/SDD_FVG_OB_ENGINE.md` — diseño técnico.
6. `docs/INDICE_AUTORIDAD.md` — jerarquía documental de la tesis.
7. `docs/DATA_INVENTARIO.md` — datos disponibles y procedencia.
8. `docs/UMBRAL_CONFIRMACION.md` — umbrales vigentes.

La tesis ICT vigente y sus enmiendas tienen autoridad superior sobre cualquier documento de implementación. **OTE queda fuera del alcance.**

Los documentos históricos, cierres de fases anteriores, reportes antiguos y documentos no enumerados arriba son contexto histórico, no instrucciones. No deben generar trabajo nuevo salvo que un documento normativo los cite explícitamente.

## 3. OBJETIVO

Completar una capa ICT profesional de **FVG + Order Blocks**, integrada con el motor existente de Swing/BOS/CHOCH, liquidez y displacement, con:

- detección correcta;
- ciclo de vida;
- Breakers y BPR/OB+FVG cuando corresponda al contrato;
- lineage causal completo;
- separación candidate/confirmation/tradable;
- anti-look-ahead 100%;
- integración sin regresiones;
- ejecución basada en retest;
- dataset de aprendizaje reproducible;
- ablación baseline vs FVG vs OB vs FVG+OB;
- validación OOS cuando los datos lo permitan.

## 4. REGLA DE NO-DESVIACIÓN

NO:

- introducir OTE, Fibonacci 62–79% ni equivalentes;
- crear reglas no contempladas sin registrar primero una propuesta de cambio;
- hacer refactors no relacionados;
- cambiar métricas objetivo para declarar PASS;
- declarar DONE con un gate rojo;
- eliminar evidencia histórica sin autorización contractual;
- fabricar datos, métricas o resultados;
- saltar una fase porque parezca innecesaria.

Si durante el trabajo aparece una necesidad fuera del alcance, regístrala como **BLOCKER / OUT-OF-SCOPE** y continúa únicamente con el plan vigente.

## 5. CICLO OBLIGATORIO POR CADA FASE Y EXPERIMENTO

Ninguna fase, experimento, auditoría, backtest o cambio relevante se considera cerrado hasta sincronizar la documentación.

```text
AUDIT
  ↓
IMPLEMENT / EXPERIMENT
  ↓
TEST
  ↓
BACKTEST / EVALUATION
  ↓
AUDIT RESULTADO
  ↓
ACTUALIZAR .hermes-index.md
  ↓
ACTUALIZAR .hermes-worklog/<timestamp>_<evento>.md
  ↓
ACTUALIZAR AUDITORÍA / REPORTE CORRESPONDIENTE
  ↓
ACTUALIZAR SDD/PLAN/CONTRATO SI LA EVIDENCIA CAMBIA UNA DECISIÓN
  ↓
COMMIT
  ↓
GATE
  ↓
PASS? ── NO → DIAGNOSE → FIX/REVERT → REPETIR
  │
  YES
  ↓
SIGUIENTE FASE
```

**Si `.hermes-index.md`, auditoría y bitácora no reflejan el resultado real, el gate de la fase es FAIL aunque el código y los tests pasen.**

## 6. `.hermes-index.md` ES EL CUADRO MAESTRO

Después de cada fase/experimento debe quedar actualizado como mínimo:

- fase actual;
- estado `IN_PROGRESS / BLOCKED / PASS / FAIL / DONE`;
- objetivo de la fase;
- trabajo ejecutado;
- tests ejecutados y resultado;
- experimento/backtest ejecutado;
- dataset y ventana temporal;
- configuración/commit probado;
- métricas baseline y variante;
- resultado del gate;
- problemas abiertos;
- decisiones tomadas;
- archivos modificados;
- commit SHA;
- bitácora/reportes relacionados;
- siguiente acción exacta.

No borrar resultados anteriores: mantener historial o enlazar al worklog.

## 7. AUDITORÍA CONTINUA

Cada resultado debe indicar explícitamente:

- qué hipótesis se estaba probando;
- qué cambió;
- qué se esperaba;
- qué ocurrió;
- evidencia reproducible;
- riesgos de leakage/look-ahead;
- conclusión `CONFIRMED / REJECTED / INCONCLUSIVE`;
- impacto sobre el plan.

Una hipótesis rechazada no debe reaparecer posteriormente como hipótesis nueva sin explicar qué cambió.

## 8. POLÍTICA DE ITERACIÓN

El trabajo termina sólo cuando todos los gates contractuales están `PASS` y la documentación está sincronizada.

Si un resultado falla:

1. registrar el fallo;
2. diagnosticar la causa;
3. formular una corrección acotada;
4. implementar;
5. volver a probar;
6. comparar contra el baseline;
7. repetir.

Si después de iteraciones razonables la evidencia demuestra que una hipótesis no aporta edge, documentarla como `REJECTED` y continuar con la siguiente parte del plan, sin manipular los criterios de éxito.

## 9. PRIMERA ACCIÓN

Al recibir **"comienza el plan"**:

1. leer este documento;
2. leer contrato, plan y SDD;
3. comprobar `.hermes-index.md` y último worklog;
4. auditar el estado real del código antes de modificarlo;
5. actualizar `.hermes-index.md` indicando `FASE 0 — AUDIT INICIAL`;
6. ejecutar únicamente la Fase 0 del plan;
7. documentar y cerrar el gate antes de avanzar.

**No empezar por implementar FVG/OB sin completar la auditoría inicial.**
