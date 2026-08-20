# SDD — Hermes Mission Controller

**Proyecto:** `vjack666/ict2.0`
**Fecha:** 2026-08-20
**Versión:** 1.0
**Estado:** NORMATIVO — diseño autorizado; implementación pendiente
**Plan de implementación:** `.hermes/plans/2026-08-20_HERMES_MISSION_CONTROLLER.md`

## 1. Propósito

Este documento define el diseño del **Hermes Mission Controller**, un motor de
ejecución autónoma de misiones técnicas. Hermes no será únicamente un
orquestador que delega prompts: debe conservar el objetivo, ejecutar un plan,
observar resultados, corregirse, verificar evidencia y reanudar una misión
después de una interrupción.

La misión termina por evidencia verificable, no porque un agente haya devuelto
texto.

## 2. Decisiones arquitectónicas

```text
Hermes Mission Controller
        │
        ├── MissionStore
        │      ├── objective
        │      ├── plan
        │      ├── tasks
        │      ├── decisions
        │      ├── evidence
        │      ├── blockers
        │      └── completion_state
        │
        ├── AgentRegistryResolver
        │
        ├── OpenCodeAdapter
        │        └── OpenCode SDK 1.17.11
        │                └── hy3-free / otros providers
        │
        ├── Mission Loop
        │        ├── PLAN
        │        ├── EXECUTE
        │        ├── OBSERVE
        │        ├── VERIFY
        │        ├── DELEGATE
        │        ├── RECOVER
        │        └── COMPLETE
        │
        └── Persistence / Resume
                 ├── Engram
                 └── .hermes-state/
```

La separación de autoridad es obligatoria:

| Capa | Responsabilidad | No puede hacer |
|---|---|---|
| OpenCode | Ejecutar sesiones, agentes y modelos configurados | Declarar completa una misión |
| Agent Registry | Resolver un nombre de agente a su configuración vigente | Crear una segunda configuración normativa de modelos |
| Hermes | Gobernar objetivo, estado, plan, delegación, recuperación y gates | Elegir proveedor por acoplamiento interno cuando OpenCode ya lo resuelve |
| Engram | Memoria de sesiones, decisiones y aprendizajes persistentes | Ser la única fuente de estado transaccional de una misión |
| `.hermes-state/` | Estado operativo durable y reanudable | Sustituir la evidencia detallada del worklog |
| `.hermes-worklog/` | Evidencia humana y auditable de cambios y gates | Actuar como cola mutable de tareas |

Hermes no incorpora Ollama ni otro runtime de modelos. El modelo concreto se
resuelve en OpenCode. El identificador `opencode/hy3-free` puede estar
configurado allí, pero Hermes trabaja con `agent` y `task`, no con un proveedor
hardcodeado.

## 3. Alcance

### Incluido

- Misiones técnicas de uno o varios pasos.
- Plan persistente y tareas con dependencias.
- Delegación a agentes ya registrados en OpenCode.
- Ejecución síncrona o asíncrona.
- Estados de espera, recuperación y reanudación.
- Evidencia de comandos, tests, artefactos y decisiones.
- Gates de terminación y consistencia.
- Reintentos limitados, diagnóstico y elección autónoma entre alternativas.
- Escalamiento humano solamente en fronteras de autoridad.

### Fuera de alcance

- Entrenar, hospedar o administrar modelos.
- Crear un registro paralelo de agentes o proveedores.
- Convertir Engram en base de datos transaccional de la misión.
- Ejecutar órdenes de trading.
- Saltarse contratos de datos, seguridad, Git o auditoría del repositorio.
- Declarar éxito por calidad subjetiva del texto producido por un agente.

## 4. Definiciones

| Término | Definición |
|---|---|
| Mission | Objetivo de alto nivel con alcance, autoridad, política de terminación y evidencia requerida |
| Task | Unidad ejecutable que puede delegarse, verificarse y reanudarse independientemente |
| Decision | Elección registrada entre alternativas, con motivo y evidencia |
| Evidence | Referencia verificable a archivo, test, comando, reporte, commit o resultado observado |
| Blocker | Condición que impide avanzar y que puede requerir recuperación o escalamiento |
| Agent session | Sesión de OpenCode asociada a una tarea concreta |
| Technical subordinate decision | Decisión reversible dentro del objetivo, alcance, autoridad, seguridad, presupuesto y datos autorizados |

## 5. Contrato de misión

Toda misión debe poder representarse como un registro serializable. Los campos
son normativos aunque la implementación pueda usar dataclasses o esquemas JSON.

```json
{
  "mission_id": "MC-2026-08-20-0001",
  "objective": "Completar el SDD de Context State MTF",
  "scope": {
    "workspace": "ICT SYSTEM",
    "allowed_roots": ["docs/", ".hermes/", ".hermes-state/"],
    "excluded_roots": ["data/", "secrets/"]
  },
  "authority": {
    "owner": "user",
    "autonomy_policy": "technical_subordinate_decisions",
    "escalation_boundaries": ["OBJECTIVE", "SCOPE", "AUTHORITY", "SECURITY", "BUDGET", "IRREVERSIBLE_DATA"]
  },
  "phase": "PLAN",
  "status": "RUNNING",
  "plan": [],
  "tasks": [],
  "decisions": [],
  "evidence": [],
  "blockers": [],
  "completion_state": {
    "objective_satisfied": false,
    "required_tests_pass": false,
    "evidence_recorded": false,
    "no_unresolved_blockers": false,
    "artifacts_consistent": false,
    "mission_complete": false
  },
  "resume": {
    "last_checkpoint": null,
    "active_task_id": null,
    "opencode_session_ids": [],
    "attempts": 0
  }
}
```

El registro debe incluir `schema_version`, `created_at`, `updated_at`,
`controller_version` y `git_head` en la implementación real.

## 6. Contrato de tarea

```json
{
  "task_id": "MC-2026-08-20-0001-T03",
  "mission_id": "MC-2026-08-20-0001",
  "kind": "IMPLEMENT | INVESTIGATE | TEST | REVIEW | DOCUMENT | GATE",
  "title": "Validar determinismo del snapshot",
  "status": "PENDING",
  "depends_on": ["MC-2026-08-20-0001-T02"],
  "assigned_agent": "auditor",
  "opencode_session_id": null,
  "attempt": 0,
  "inputs": [],
  "outputs": [],
  "evidence_refs": [],
  "blocker_refs": [],
  "next_action": null,
  "started_at": null,
  "completed_at": null
}
```

Una tarea no puede marcarse `COMPLETE` sin `outputs` o `evidence_refs`, salvo
que su tipo sea una tarea de control que documente explícitamente por qué no
produce artefacto.

## 7. Máquina de estados de la misión

```text
PLAN
  ↓
DELEGATE → EXECUTE → OBSERVE → VERIFY
  ↑          │          │         │
  │          └──────────┴─────────┘
  │                    FAIL
  │                     ↓
  └────────────────── RECOVER
                         │
                         ├── retry / diagnose / alternate_agent
                         ├── WAITING_FOR_AGENT
                         ├── WAITING_FOR_TEST
                         ├── WAITING_FOR_REVIEW
                         ├── WAITING_FOR_EXTERNAL_REASONING
                         └── ESCALATE

VERIFY ── todos los gates PASS ──→ COMPLETE
```

Estados mínimos:

| Estado | Entrada | Salida válida |
|---|---|---|
| `PLAN` | Objetivo aceptado y alcance resuelto | Tareas persistidas y ordenadas |
| `DELEGATE` | Tarea ejecutable sin bloqueo | Sesión OpenCode creada |
| `EXECUTE` | Sesión activa | Resultado o error observable |
| `OBSERVE` | Resultado disponible | Evidencia y estado de tarea actualizados |
| `VERIFY` | Artefactos producidos | PASS, FAIL o diagnóstico |
| `RECOVER` | FAIL, timeout, crash o inconsistencia | Reintento, nueva estrategia o blocker |
| `WAITING_FOR_AGENT` | Sesión asíncrona pendiente | Evento de sesión o timeout |
| `WAITING_FOR_TEST` | Test pesado o externo pendiente | Resultado de test |
| `WAITING_FOR_REVIEW` | Revisión obligatoria pendiente | Dictamen de reviewer |
| `WAITING_FOR_EXTERNAL_REASONING` | Evidencia no resoluble localmente | Fuente o intervención autorizada |
| `ESCALATED` | Cruce de frontera humana | Decisión del usuario |
| `COMPLETE` | Todos los gates de terminación PASS | Misión cerrada e inmutable salvo nueva misión |
| `FAILED` | No existe recuperación válida | Fallo documentado, no éxito implícito |

Un estado `WAITING_*` no significa misión terminada. Debe conservar la
condición de despertar, el timestamp del último evento y la acción de
reanudación.

## 8. Delegación a OpenCode

El adaptador debe exponer una interfaz estable y agnóstica del proveedor:

```text
list_agents() -> AgentDescriptor[]
create_session(agent, title, mission_id, task_id) -> SessionRef
delegate(session_ref, prompt, mode) -> DelegationRef
get_session_status(session_ref) -> SessionStatus
get_session_children(session_ref) -> SessionRef[]
resume(session_ref, prompt) -> DelegationRef
subscribe_events() -> EventStream
```

El adaptador usa el SDK OpenCode disponible en la instalación. El flujo
normativo es equivalente a:

```text
session.create
session.promptAsync({ agent, prompt })
event/session.status o session.idle
session.messages / resultado
```

Hermes nunca debe depender de la forma interna de `hy3-free`, Groq, OpenRouter
u otro proveedor. La resolución `agent → model/provider` queda en OpenCode.

El prompt delegado debe incluir siempre:

- `mission_id` y `task_id`;
- objetivo y alcance relevante;
- contrato de salida estructurado;
- archivos o artefactos autorizados;
- prohibiciones aplicables;
- condición de éxito de la tarea;
- instrucción para devolver evidencia y siguiente acción;
- instrucción de no declarar completa la misión.

## 9. Política de autonomía y escalamiento

Hermes **no solicita aprobación humana para decisiones técnicas subordinadas**.
Debe investigar, comparar, elegir, implementar, probar y corregir dentro del
contrato de misión.

| Frontera | Acción autónoma permitida | Escalar al usuario |
|---|---|---|
| `OBJECTIVE` | Descomponer y aclarar internamente | Cambiar el objetivo o declarar otro resultado |
| `SCOPE` | Elegir archivos y rutas dentro de raíces autorizadas | Ampliar raíces, incluir otro repositorio o tocar datos excluidos |
| `AUTHORITY` | Elegir implementación compatible | Cambiar la fuente normativa o crear una nueva autoridad |
| `SECURITY` | Aplicar correcciones seguras y detenerse ante riesgo | Leer/exponer secretos, cambiar permisos o relajar controles |
| `BUDGET` | Reintentar dentro de límites configurados | Aumentar presupuesto, usar proveedor con coste o proceso pesado no autorizado |
| `IRREVERSIBLE_DATA` | Usar copias y operaciones reversibles | Borrar, sobrescribir datos valiosos o cambiar historia Git |

Una pregunta al usuario que no pertenezca a estas fronteras es un fallo de
orquestación: Hermes debe resolverla mediante evidencia, un agente adicional,
un test o una alternativa reversible.

## 10. Persistencia, checkpoints y reanudación

### Fuente de estado

- `.hermes-state/missions/<mission_id>.json`: snapshot transaccional de la
  misión.
- `.hermes-state/missions/<mission_id>.events.jsonl`: eventos append-only para
  reconstrucción y diagnóstico.
- `.hermes-worklog/<timestamp>_HERMES_MISSION_<id>.md`: evidencia legible y
  resumen de cada gate.
- Engram: memoria de sesiones, decisiones y contexto entre conversaciones.

El JSON de misión es la autoridad operativa. Engram no puede cambiar el estado
de una misión sin que Hermes lo valide y persista primero.

Después de cada transición durable, Hermes debe escribir un checkpoint con:

```text
mission_id, phase, status, active_task_id, last_event_id,
opencode_session_ids, attempts, blockers, completion_state, git_head
```

Al iniciar o reiniciar:

1. cargar la misión más reciente;
2. validar el esquema y el `git_head` observado;
3. detectar sesiones OpenCode activas, terminadas o perdidas;
4. reconciliar tareas con eventos antes de delegar otra vez;
5. reanudar desde la primera tarea no terminal;
6. registrar la recuperación en el worklog.

No se permite duplicar una delegación si existe una sesión durable para la
misma tarea en estado activo o cuyo resultado todavía no fue reconciliado.

## 11. Recuperación y reintentos

Cada fallo debe clasificarse:

```text
AGENT_ERROR
TIMEOUT
TEST_FAILURE
CONTRACT_FAILURE
ARTIFACT_INCONSISTENCY
AUTHORITY_CONFLICT
SECURITY_BLOCK
EXTERNAL_DEPENDENCY
```

La recuperación sigue este orden:

1. conservar el resultado y la evidencia del fallo;
2. diagnosticar con el agente adecuado;
3. elegir una alternativa reversible;
4. reintentar con límite de intentos;
5. cambiar de agente o estrategia si la evidencia lo justifica;
6. escalar solo si se cruza una frontera humana;
7. marcar `FAILED` si no existe recuperación válida.

Un retry no puede ocultar el intento anterior ni sustituir un resultado FAIL
por PASS. Las tareas deben ser idempotentes o declarar explícitamente su
estrategia de compensación.

## 12. Condición de terminación

La única definición válida es:

```text
MISSION_COMPLETE =
    objective_satisfied
    AND required_tests_pass
    AND evidence_recorded
    AND no_unresolved_blockers
    AND artifacts_consistent
```

La implementación debe materializar cada predicado como booleano o resultado
estructurado en `completion_state`. `MISSION_COMPLETE` solo puede pasar a
`true` cuando los cinco predicados son `true` y existe una evidencia final que
los referencia.

No son condiciones de terminación:

- respuesta satisfactoria de un agente;
- ausencia temporal de errores;
- tests no ejecutados;
- texto que "parece correcto";
- una rama de ejecución abandonada;
- un blocker sin dueño;
- una decisión pendiente de documentación.

## 13. Gates obligatorios

| Gate | Pregunta | Evidencia mínima |
|---|---|---|
| `MC-0` | ¿Objetivo y límites están definidos? | Mission record válido |
| `MC-1` | ¿El plan es ejecutable? | Tasks, dependencias y agentes resolubles |
| `MC-2` | ¿La delegación es trazable? | Session/task/mission IDs |
| `MC-3` | ¿El resultado cumple el contrato? | Output estructurado y artefactos |
| `MC-4` | ¿Los tests requeridos pasan? | Comandos y reportes reproducibles |
| `MC-5` | ¿La misión sobrevive a reinicio? | Test de checkpoint y resume |
| `MC-6` | ¿No hay conflicto de autoridad o seguridad? | Auditoría de límites |
| `MC-7` | ¿La terminación es consistente? | `completion_state` completo y worklog |

Un gate FAIL devuelve la misión a `RECOVER` o `ESCALATED`; nunca permite
`COMPLETE` por omisión.

## 14. Seguridad y permisos

- Hermes no lee secretos para descubrir proveedores.
- El adaptador no imprime API keys, headers ni respuestas de autenticación.
- Los agentes reciben solo las raíces de trabajo autorizadas.
- El agente delegado no puede ampliar su alcance declarativamente.
- Push, reset, rebase destructivo, borrado y acceso a datos sensibles siguen
  las políticas de permisos existentes.
- Las operaciones largas deben ser cancelables y dejar checkpoint.
- Un resultado de agente se trata como dato no confiable hasta pasar VERIFY.

## 15. Observabilidad

Cada misión debe permitir responder:

```text
¿Qué objetivo tenía?
¿Qué tareas se ejecutaron?
¿Qué agente y sesión produjo cada resultado?
¿Qué decisiones tomó Hermes y con qué evidencia?
¿Cuántos retries hubo?
¿Qué tests pasaron o fallaron?
¿Qué bloqueos existieron?
¿Por qué terminó o por qué no terminó?
```

Los eventos deben incluir `event_id`, `timestamp`, `mission_id`, `task_id`,
`phase`, `status_before`, `status_after`, `actor`, `summary` y referencias a
artefactos. Nunca se debe almacenar una respuesta completa de modelo como
única evidencia de una decisión.

## 16. Testing del controlador

La implementación debe incluir como mínimo:

- validación de esquemas de Mission/Task/Decision/Evidence;
- transiciones válidas e inválidas de la máquina de estados;
- deduplicación de delegaciones tras reinicio;
- reanudación después de `session.idle`, timeout, error y crash;
- retry bounded y clasificación de fallos;
- decisión autónoma subordinada sin pregunta humana;
- escalamiento al cruzar `OBJECTIVE`, `SCOPE`, `AUTHORITY`, `SECURITY`,
  `BUDGET` o `IRREVERSIBLE_DATA`;
- `MISSION_COMPLETE` falso si falta cualquiera de sus predicados;
- determinismo del MissionStore;
- no exposición de secretos en logs;
- adapter contract test con un fake de OpenCode SDK;
- integración read-only contra el SDK real, sin enviar prompts en CI.

## 17. Compatibilidad con ICT SYSTEM

Hermes Mission Controller puede ejecutar tareas del repositorio, pero no
redefine sus autoridades de dominio:

```text
Context State → engine/mtf_navigation.py
AHF           → engine/ahf.py
Sequence      → engine/sequential_events.py
Lineage       → engine/lineage.py
Wyckoff       → engine/Wyckoff/
Daily read    → engine/daily_motor.py
Agents API    → agents/
Orchestration → orchestration/
```

Una misión que cambie una de estas autoridades debe declarar el cambio,
actualizar su SDD/contrato correspondiente y ejecutar los gates de dominio.

## 18. Criterio de aceptación del SDD

Este SDD queda listo para implementación cuando:

- el MissionStore y sus estados estén implementados;
- el adapter pueda usar OpenCode SDK sin conocer providers;
- una misión fake pueda recorrer PLAN → DELEGATE → VERIFY → COMPLETE;
- una misión con FAIL pueda RECOVER y continuar sin intervención técnica;
- un reinicio pueda reanudar sin duplicar tareas;
- una frontera humana produzca `ESCALATED` con evidencia;
- la condición `MISSION_COMPLETE` sea demostrable por tests;
- documentación, índice y worklog estén sincronizados.
