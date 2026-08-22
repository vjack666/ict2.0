# Plan — Hermes Mission Controller

**Fecha:** 2026-08-20
**Estado:** AUTORIZADO PARA IMPLEMENTACIÓN POR FASES; HERMES RESERVADO AL LABORATORIO Y CODEX/EQUIPO RESERVADO A LA INFRAESTRUCTURA IA
**SDD:** `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md`
**Objetivo:** 🎯 construir la infraestructura de IA de ICT 2.0 para aprender qué señales de ICT + Wyckoff aportan valor real, combinarlas, estimar probabilidad/confianza y abstenerse cuando el mercado esté fuera de su dominio conocido. Hermes continúa exclusivamente con el laboratorio y los experimentos; Codex/equipo multiagente construye la infraestructura, consume resultados certificados y no reemplaza GEN-000.

## Resultado final

Hermes debe poder recibir un objetivo técnico, construir un plan, delegar a
agentes registrados en OpenCode, ejecutar y observar resultados, recuperarse de
fallos, reanudar después de reinicio y volver solo cuando:

```text
objective_satisfied
AND required_tests_pass
AND evidence_recorded
AND no_unresolved_blockers
AND artifacts_consistent
```

## Reglas de ejecución

1. El SDD es la autoridad del controlador.
2. OpenCode resuelve agente, provider y modelo.
3. Hermes no hardcodea `hy3-free`; solo usa nombres de agentes y contratos.
4. Hermes resuelve autónomamente decisiones técnicas subordinadas.
5. Solo escala por objetivo, alcance, autoridad, seguridad, presupuesto o
   datos irreversibles.
6. Engram es memoria; `.hermes-state` es estado operativo.
7. Cada fase termina con tests, evidencia, worklog e índice sincronizados.
8. No se declara `COMPLETE` por una respuesta textual de un agente.

## Frontera de trabajo: laboratorio e infraestructura

Este plan conserva las fases de implementación del controlador `MC-0..MC-8` y
separa dos carriles que no deben duplicarse:

| Carril | Responsable | Puede hacer | No puede hacer |
|---|---|---|---|
| Laboratorio y experimentos B0–B8 | Hermes | Ejecutar, observar, certificar y documentar experimentos | Delegar a Codex el mismo experimento o alterar el protocolo certificado |
| Infraestructura IA | Codex/equipo multiagente | Construir contratos, modelos, checkpoints, fusión, confianza, OOD/drift, shadow y observabilidad | Lanzar runners de Hermes, modificar sus datasets/resultados o declarar evidencia no certificada |

La infraestructura solo consume resultados certificados de Hermes mediante
artefactos en disco. `FAIL`, `INCONCLUSIVE` y `BLOCKED` se conservan y no se
convierten en datos de entrenamiento válidos por conveniencia.

### Arquitectura objetivo de la infraestructura

```text
artefactos certificados de Hermes
  → contrato de features ICT + Wyckoff
  → encoders/modelos y checkpoints versionados
  → score fusion calibrado
  → probabilidad + confianza + abstención
  → OOD/drift y dominio conocido
  → logger de Shadow Mode
  → futura propuesta advisory para bias_from_tools
```

Las señales contempladas son Swing, Liquidez, Sweep, BOS/CHOCH, FVG/OB,
contexto HTF y Wyckoff. Su valor no se asume por estar disponible: la evidencia
de aporte incremental proviene únicamente de los resultados certificados del
laboratorio.

### Gates de infraestructura Codex

| Gate | Entrega | Criterio |
|---|---|---|
| `INF-0` | Adaptador de resultados certificados | Rechaza artefactos sin manifest, hash, commit o veredicto |
| `INF-1` | Contrato de features y labels | Esquema versionado, PIT-aware y compatible con los resultados recibidos |
| `INF-2` | Registro de modelos y checkpoints | Reproducibilidad, lineage, seed y rollback |
| `INF-3` | Score fusion | Pesos aprendidos solo en TRAIN y evaluación OOS |
| `INF-4` | Confianza y abstención | Umbrales calibrados; salida `ABSTAIN` fuera de confianza |
| `INF-5` | OOD y drift | Detecta dominio no conocido y cambios de distribución |
| `INF-6` | Shadow Mode y observabilidad | `can_trade=false`, logs completos y métricas de latencia/calibración |
| `INF-7` | Adaptador futuro | Integración reversible y advisory en `bias_from_tools` |
| `INF-8` | Auditoría final | Tests, artefactos consistentes y aprobación explícita |

### Estado de implementación INF-0/INF-1

`runtime/ai_learning/certified_artifacts.py` implementa el consumidor
read-only y `runtime/ai_learning/` expone el contrato versionado `1.0`. El
adaptador acepta únicamente `verdict == PASS`, valida los diez campos del
handoff y rechaza rutas absolutas, traversal, hashes inválidos y timestamps no
ISO-8601. La prueba de contrato está en
`tests/test_ai_learning_certified_manifest.py`.

La auditoría actual de Hermes `EXP_A1_audit.json` se rechaza deliberadamente
por no incluir todos los campos del handoff (`experiment_id`, `scope`,
`metrics`, `artifact_paths` y `certifier`, entre otros). No se crean aliases ni
se modifica el artefacto del laboratorio para hacerlo pasar.

El flujo del carril Codex es:

```text
leer artefacto certificado → validar contrato → construir/testear infraestructura
→ registrar checkpoint → revisión independiente → siguiente gate
```

### Contrato de handoff Hermes → Codex

Un resultado solo puede cruzar la frontera si incluye `experiment_id`,
`verdict`, `gate`, `dataset_hash`, `code_commit`, `scope` (símbolo/TF/período),
`metrics`, `artifact_paths`, `produced_at` y `certifier`. Codex debe conservar
la referencia exacta al artefacto y no reescribir su contenido.

### Reglas de coordinación y documentación

1. Hermes continúa exclusivamente con el laboratorio y sus experimentos.
2. Codex/equipo no modifica runners, datasets, protocolos ni resultados de
   Hermes; solo consume artefactos certificados.
3. Un agente no certifica su propio trabajo.
4. Cada componente de infraestructura registra commit, configuración,
   checkpoint, tests y evidencia.
5. GEN-000 conserva la autoridad hasta completar todos los gates y Shadow Mode.
6. Cada cambio actualiza el plan, el SDD, el worklog y el cuadro de Hermes;
   `push` requiere autorización explícita.

## Fases y gates

### MC-0 — Contrato y preflight

- Leer el SDD completo.
- Confirmar rutas de estado, worklog y autoridad.
- Definir el esquema versionado de Mission, Task, Decision, Evidence y Blocker.
- Definir límites de reintento, timeout y concurrencia.

**Gate MC-0:** esquemas y políticas documentados; ninguna ambigüedad sobre
quién gobierna modelos, memoria, estado y misión.

### MC-1 — MissionStore

- Crear almacenamiento durable bajo `.hermes-state/missions/`.
- Implementar snapshots, eventos append-only y checkpoints.
- Validar esquema, versiones y migración explícita.
- Implementar carga, actualización idempotente y reconstrucción.

**Gate MC-1:** crash/restart test reconstruye la misión sin perder tareas,
decisiones, blockers ni evidencia.

### MC-2 — AgentRegistryResolver

- Leer la configuración efectiva de OpenCode sin duplicarla.
- Resolver agentes por nombre y comprobar que estén disponibles.
- Rechazar agentes inexistentes o incompatibles con el tipo de tarea.
- Mantener provider/model como metadato observado, no como autoridad Hermes.

**Gate MC-2:** resolver los agentes existentes, incluyendo `architect`,
`auditor`, `conductor`, `discoverer`, `documenter`, `implementer`,
`researcher` y `scout`, sin copiar su configuración al repositorio.

### MC-3 — OpenCodeAdapter

- Integrar el SDK OpenCode 1.17.11.
- Implementar creación de sesión, prompt asíncrono, estado, mensajes,
  children y eventos.
- Asociar cada sesión con `mission_id` y `task_id`.
- Añadir fake adapter para tests deterministas.
- Definir conexión a servidor existente o lifecycle controlado del SDK.

**Gate MC-3:** una tarea fake se delega y se reconcilia con session/task IDs;
CI no envía prompts reales.

### MC-4 — Mission Loop

- Implementar PLAN, DELEGATE, EXECUTE, OBSERVE, VERIFY, RECOVER y COMPLETE.
- Implementar estados WAITING y condición de despertar.
- Resolver tareas por dependencias, no por orden textual.
- Prohibir transición directa a COMPLETE desde respuesta de agente.

**Gate MC-4:** misión fake completa un ciclo positivo y una misión con FAIL
entra en RECOVER y continúa sin preguntar una decisión técnica subordinada.

### MC-5 — Recuperación y reanudación

- Clasificar errores de agente, timeout, test, contrato, autoridad y seguridad.
- Implementar retry bounded, diagnóstico y cambio de estrategia.
- Reconciliar sesiones activas, idle, error y perdidas tras reinicio.
- Evitar duplicar delegaciones.

**Gate MC-5:** reiniciar durante cada estado WAITING y demostrar reanudación
determinista; el intento anterior queda visible.

### MC-6 — Verificación y terminación

- Implementar evaluadores de objective, tests, evidence, blockers y artifacts.
- Registrar predicados individuales de `completion_state`.
- Implementar gate final y estado FAILED cuando no exista recuperación.
- Crear reportes de misión y worklog.

**Gate MC-6:** no existe ruta de código que permita `MISSION_COMPLETE=true`
con un predicado falso o ausente.

### MC-7 — Integración ICT SYSTEM

- Añadir una misión de prueba contra una tarea documental de bajo riesgo.
- Validar que no se modifiquen Context State, AHF, Sequence, Lineage o Wyckoff
  fuera del alcance explícito.
- Conservar `agents/` y `orchestration/` como APIs activas.
- Integrar `start_hermes.py` únicamente después de pasar los gates anteriores.

**Gate MC-7:** ejecución read-only y luego una misión controlada producen
evidencia completa, sin segundo motor de mercado ni orden de trading.

### MC-8 — Operación y cierre

- Actualizar documentación, índice, contrato y worklog.
- Añadir guardas CI para esquemas, estados inválidos y secretos.
- Publicar commit reproducible.
- Marcar el plan COMPLETE solo con evidencia de todos los gates MC-0..MC-7.

**Gate MC-8:** `MISSION_COMPLETE` del propio desarrollo del controlador cumple
los cinco predicados normativos.

## Orden de delegación recomendado

```text
discoverer → architect → implementer → auditor → tester/verify → documenter
```

`conductor` coordina ejecución de tareas ya aprobadas, no sustituye al Mission
Controller. `researcher` se usa cuando la evidencia externa o comparativa es
necesaria. Ningún agente puede declarar completa la misión.

## No objetivos

- No crear modelos locales.
- No copiar `opencode.json` al repo.
- No introducir un segundo Engram.
- No usar respuestas de Hy3Free como evidencia suficiente sin verificación.
- No dar permisos globales nuevos a agentes.
- No alterar la política de ejecución de trading.

## Artefactos obligatorios por fase

| Artefacto | Ubicación |
|---|---|
| SDD | `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md` |
| Estado de misión | `.hermes-state/missions/<mission_id>.json` |
| Eventos | `.hermes-state/missions/<mission_id>.events.jsonl` |
| Worklog | `.hermes-worklog/<timestamp>_HERMES_MISSION_<id>.md` |
| Tests | `tests/` |
| Reporte de verificación | `reports/` o `.hermes-worklog/` según el gate |
| Adaptador INF-0/contrato INF-1 | `runtime/ai_learning/certified_artifacts.py` |
| Tests INF-0/INF-1 | `tests/test_ai_learning_certified_manifest.py` |
