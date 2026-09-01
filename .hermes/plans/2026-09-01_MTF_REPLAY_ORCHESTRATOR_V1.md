# Plan ejecutable — MTF Replay Orchestrator v1

**Estado:** COMPLETED T0–T6/T8 — T7 WAITING FOR EXPLICIT GO

**Owner:** D2 Ingeniería; D1 PMO integra; D5 audita independientemente

**Modo:** `LOCAL_ONLY`

**Contrato:** `docs/contratos/CONTRATO_MTF_REPLAY_ORCHESTRATOR_V1.md`

**SDD:** `docs/planificacion/SDD_MTF_REPLAY_ORCHESTRATOR_V1.md`

## Orden para el responsable

Ejecuta este plan hasta cerrar M0–M9. Si una tarea produce una subtarea técnica
necesaria, añádela como `SUB-Tx-n`, asígnale owner, dependencia, write set,
criterio DONE y evidencia; ejecútala sin consultar al humano mientras siga
dentro del objetivo, seguridad y autoridad. Ante una falla: diagnostica causa
raíz, corrige el productor o contrato correcto, repite el gate y continúa.

No cambies criterios para obtener PASS, no ocultes findings y no dupliques
motores. Detente solo si hace falta cambiar objetivo, usar datos no autorizados,
promover, operar MT5, ejecutar una acción destructiva, hacer push o ampliar
presupuesto/seguridad.

## Lista maestra

### T0 — DoR y baseline — D1/D2/D5

- [x] `T0.1` Leer AGENTS, índice, contrato, SDD, auditoría, último worklog, Engram y Graphify.
- [x] `T0.2` Registrar rama/HEAD/status y aislar cambios ajenos.
- [x] `T0.3` Auditar APIs públicas reales de Lifecycle, MarketState, SetupBuilder, Episodes y outcome.
- [x] `T0.4` Auditar el visor del worktree y listar exactamente qué archivos UI son portables.
- [x] `T0.5` D5 revisa contrato contra tesis y emite M0 PASS/REVIEW.

### T1 — Schema 2.0 — D2, auditoría D5

- [x] `T1.1` Definir dataclasses/validadores sin romper schema 1.0.
- [x] `T1.2` Implementar IDs, source refs, lineage y razones canónicas.
- [x] `T1.3` Implementar checksum lógico y manifiesto de chunks.
- [x] `T1.4` Añadir pruebas negativas de futuro, huérfano, ciclo, duplicado y orden.
- [x] `T1.5` Cerrar M1.

### T2 — Reloj causal — D2

- [x] `T2.1` Crear merge streaming por barras cerradas.
- [x] `T2.2` Implementar batch `APPLY→SNAPSHOT→DECISION→EXECUTION→EMIT`.
- [x] `T2.3` Fijar orden estable para cierres simultáneos.
- [x] `T2.4` Probar permutaciones de entrada y ausencia de same-bar fill accidental.
- [x] `T2.5` Cerrar M2.

### T3 — Integración de autoridades — D2/D5

- [x] `T3.1` Consumir MarketState as-of T sin mutarlo desde backtest.
- [x] `T3.2` Consumir SetupBuilder y Episodes sin reconstruir reglas.
- [x] `T3.3` Verificar que M15/M5 no matan objetos H4.
- [x] `T3.4` Implementar cancelación/supersession pre-entry y evidencia post-entry.
- [x] `T3.5` Cerrar M3, M4 y M5 con FULL/PREFIX literal.

### T4 — Determinismo y recursos — D2/D5

- [x] `T4.1` Implementar checkpoints y resume con hashes.
- [x] `T4.2` Implementar snapshots+deltas y chunking.
- [x] `T4.3` Comparar corrida continua vs reanudada.
- [x] `T4.4` Comparar dos corridas y distintos chunk sizes.
- [x] `T4.5` Cerrar M6 y M8 sin cargar corpus completo en RAM.

### T5 — Visor local — D7/D2

- [x] `T5.1` Portar solo UI/utilidades aprobadas del worktree histórico.
- [x] `T5.2` Añadir lector schema 2.0 y compatibilidad histórica rotulada.
- [x] `T5.3` Mostrar carriles TF, estados, setup, Episode, invalidación y trade.
- [x] `T5.4` Implementar carga perezosa por chunks.
- [x] `T5.5` Probar que cursor T no muestra T+1 y cerrar M7.

### T6 — Aceptación técnica — D5

- [x] `T6.1` Ejecutar fixture sintético H4/M15/M5 con todos los caminos críticos.
- [x] `T6.2` Ejecutar suite focal y completa; 0 regresiones.
- [x] `T6.3` Ejecutar FULL/PREFIX en 10/25/50/75/90 % y cortes de transición.
- [x] `T6.4` Validar checksum, import boundaries y `git diff --check`.
- [x] `T6.5` D5 emite M9 GO técnico o findings accionables.

### T7 — Corrida real acotada — requiere GO explícito posterior

- [ ] `T7.1` Pre-registrar dataset, mes, perfil, hashes y criterios; no optimizar.
- [ ] `T7.2` Ejecutar un mes local y generar chunks/visor.
- [ ] `T7.3` Auditar causalidad, recursos y completitud; no medir edge como gate del software.
- [ ] `T7.4` Solo después decidir si ampliar ventana o abrir protocolo científico de edge.

### T8 — Cierre empresarial — D1/D7

- [x] `T8.1` Actualizar contrato/SDD/índice/plan con evidencia real.
- [x] `T8.2` Crear worklog con findings, decisiones, riesgos y siguiente acción.
- [x] `T8.3` Ejecutar Graphify update y guardar memoria duradera en Engram.
- [x] `T8.4` Autoauditoría final y commit local selectivo; sin push.
- [x] `T8.5` Entregar AGENTE/DEPARTAMENTO/TAREA/STATUS/EVIDENCIA/ARCHIVOS/RIESGOS/SIGUIENTE ACCIÓN.

## Criterio de COMPLETED

No queda ninguna tarea ni subtarea abierta de T0–T6 y T8, M0–M9 están PASS y
la evidencia es reproducible. T7 es una autorización separada y no bloquea la
terminación del software si aún no ha recibido GO.
