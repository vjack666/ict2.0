# HERMES — START HERE

**Contrato operativo:** HERMES-FVG-OB-001  
**Fecha:** 2026-08-17  
**Estado:** ACTIVO  
**Repositorio:** `vjack666/ict2.0`

## 1. INSTRUCCIÓN ÚNICA

Si recibes la orden **"comienza el plan"**, ejecuta exclusivamente el trabajo definido por este documento y sus documentos normativos. No busques tareas laterales ni amplíes el alcance por iniciativa propia.

### Guardia de intención

La frase **"comienza el plan"** es necesaria para activar este plan. Si el usuario
entrega otra misión —por ejemplo configuración, arquitectura, datos,
documentación, auditoría o lifecycle— el objetivo literal de esa misión tiene
prioridad sobre el plan activo y sobre cualquier experimento pendiente.

`edge`, `backtest`, `experimento`, `hipótesis`, `expectancy`, `PF`, `WR`, `OOS`,
entrenamiento o rentabilidad son un carril científico explícito. No deben
introducirse como criterio de éxito en tareas que no los soliciten.

## 2. ORDEN DE AUTORIDAD

Lee y respeta, en este orden:

1. `docs/00_HERMES_START_HERE.md` — punto de entrada operativo.
2. `docs/contratos/CONTRATO_HERMES_FVG_OB.md` — definición contractual de DONE.
3. `docs/PLAN_HERMES_FVG_OB.md` — fases y gates.
4. `docs/planificacion/SDD_FVG_OB_ARCHITECTURE_MAP.md` — mapa de arquitectura y archivos afectados.
5. `docs/planificacion/SDD_FVG_OB_ENGINE.md` — diseño técnico.
6. `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md` — SDD vigente de la misión post-A7.
7. `.hermes/plans/2026-08-30_POST_A7_ENGINE_STATE_EPISODES.md` — plan operativo vigente para Hermes y Codex.
8. `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md` — contrato de la siguiente capa.
9. `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md` — diseño técnico de Episodes/Funnel.
10. `.hermes/plans/2026-08-30_EPISODES_FUNNEL_V1.md` — lista ejecutable con subtareas dinámicas.
11. `docs/contratos/CONTRATO_MTF_REPLAY_ORCHESTRATOR_V1.md` — contrato de la capa consumidora posterior a Episodes.
12. `docs/planificacion/SDD_MTF_REPLAY_ORCHESTRATOR_V1.md` — diseño técnico del reloj causal MTF.
13. `.hermes/plans/2026-09-01_MTF_REPLAY_ORCHESTRATOR_V1.md` — lista ejecutable y gates M0–M9.
14. `docs/INDICE_AUTORIDAD.md` — jerarquía documental de la tesis.
15. `docs/DATA_INVENTARIO.md` — datos disponibles y procedencia.
16. `docs/UMBRALES_CONFIRMACION.md` — umbrales vigentes.
17. `docs/auditoria/AUDITORIA_FASE0_FVG_OB.md` — auditoría inicial vigente y blockers de entrada.

La tesis ICT vigente y sus enmiendas tienen autoridad superior sobre cualquier documento de implementación. **OTE queda fuera del alcance.**

`vjack666/SMC-SYSTEMS` es una fuente comparativa externa, nunca autoridad normativa. `ict_backtest/` no es una dependencia vigente y no debe restaurarse.

Los documentos históricos, cierres de fases anteriores, reportes antiguos y documentos no enumerados arriba son contexto histórico, no instrucciones. No deben generar trabajo nuevo salvo que un documento normativo los cite explícitamente.

## 2.1 Misión post-A7 vigente

Cuando la misión sea la capa posterior al Funnel A7, la referencia obligatoria es
el SDD de `Lifecycle → MarketState → Setup Builder` y su plan operativo asociado.
La implementación canónica está en `engine/`. El SDD histórico del visor en otra
rama no autoriza cambios en `engine/` ni la creación de un segundo motor.

`Episodes/Funnel` ya está implementado y revisado. La misión posterior es
`MTF Replay Orchestrator`: consumidor aislado en `backtest/`, con schema 2.0 y
visor local. Su implementación comienza por T0/M0 del plan 2026-09-01 y no
autoriza edge, entrenamiento, MT5 ni órdenes.

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
- saltar una fase porque parezca innecesaria;
- copiar código externo sólo porque parezca más completo.

Si durante el trabajo aparece una necesidad fuera del alcance, regístrala como **BLOCKER / OUT-OF-SCOPE** y continúa únicamente con el plan vigente.

## 4.1 DIRECCIÓN DE MISIÓN, AUTOAUDITORÍA Y MULTIAGENTES

El agente encargado de la tarea asume el papel de director del departamento asignado. Es responsable de coordinar el alcance, distribuir subtrabajos, integrar resultados y entregar una salida completa y verificable.

Antes de comenzar, debe leer el contexto relevante de Engram y Graphify, junto con la bitácora, el índice y los contratos aplicables. Al finalizar, debe guardar en Engram el resultado verificado, decisiones, hallazgos, riesgos y siguiente acción.

Cuando sea posible, debe usar multiagentes en paralelo para tareas independientes, con write sets separados y sin duplicar trabajo. Si una tarea depende de otra, debe respetar la dependencia y esperar la evidencia necesaria antes de integrar.

Antes de declarar `COMPLETED`, el encargado debe autoauditar objetivo, contrato, SDD, gates, artefactos, documentación y estado Git. Si encuentra un error o faltante corregible, debe corregirlo o complementarlo en la misma misión y repetir la verificación.

## 5. POLÍTICA DE RESCATE DE CÓDIGO EXTERNO

Antes de incorporar cualquier componente de `SMC-SYSTEMS` o de un histórico del proyecto:

```text
CANDIDATO
 ↓
COMPARAR CON TESIS ICT
 ↓
COMPARAR CON IMPLEMENTACIÓN ACTUAL
 ↓
TEST DE EQUIVALENCIA / SUPERIORIDAD
 ↓
ANTI-LOOK-AHEAD
 ↓
AISLAR MÍNIMO NECESARIO
 ↓
TESTS
 ↓
COMMIT
```

No importar módulos completos ni dependencias innecesarias. No importar OTE/Fibonacci/indicadores sólo porque estén acoplados al candidato. Si el candidato no demuestra ventaja, se rechaza y se documenta.

## 6. CICLO OBLIGATORIO POR CADA FASE Y EXPERIMENTO

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

El cierre exige bitácora actualizada, Graphify actualizado, commit local selectivo y verificación final de `git status`. El `push` queda bloqueado hasta una auditoría independiente y una instrucción explícita de publicación.

## 7. `.hermes-index.md` ES EL CUADRO MAESTRO

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

## 8. AUDITORÍA CONTINUA

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

## 9. POLÍTICA DE ITERACIÓN

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

## 10. PRIMERA ACCIÓN

Al recibir **"comienza el plan"**:

1. leer este documento;
2. leer contrato, plan y SDD;
3. comprobar `.hermes-index.md` y último worklog;
4. leer `docs/auditoria/AUDITORIA_FASE0_FVG_OB.md` y sus decisiones;
5. comprobar que Fase 0 esté marcada como `COMPLETADA` en el índice;
6. ejecutar únicamente la siguiente fase autorizada por `.hermes-index.md`;
7. documentar y cerrar el gate antes de avanzar.

**Fase 0 ya está completada. La siguiente fase autorizada es Fase B.**
