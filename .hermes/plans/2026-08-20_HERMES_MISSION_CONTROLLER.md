# Plan — Hermes Mission Controller

**Fecha:** 2026-08-20
**Estado:** AUTORIZADO PARA IMPLEMENTACIÓN POR FASES
**SDD:** `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md`
**Objetivo:** convertir Hermes en un motor persistente de ejecución autónoma de misiones, usando OpenCode como runtime de agentes/modelos y sin añadir Ollama ni otro proveedor local.

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
