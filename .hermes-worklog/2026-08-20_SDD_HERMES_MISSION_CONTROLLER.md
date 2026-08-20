# Worklog — SDD Hermes Mission Controller

**Fecha:** 2026-08-20
**Tipo:** cambio de arquitectura documental
**Estado:** SDD READY / implementación pendiente

## Objetivo

Definir Hermes como motor autónomo de ejecución de misiones, no solo como
orquestador de agentes.

## Evidencia auditada

- OpenCode SDK `1.17.11` disponible en la instalación local.
- Runtime OpenCode expone 33 agentes.
- Runtime OpenCode expone el modelo `opencode/hy3-free`.
- El repositorio contiene `start_hermes.py` como bootstrap de auditoría, no como
  Mission Controller.
- `.hermes-state/` conserva estado parcial de ejecución y blockers, pero no un
  registro durable de misiones, tareas y sesiones OpenCode.
- Engram ya existe como capa de memoria/sesiones mediante plugin OpenCode.

## Decisiones

1. No añadir Ollama ni otro runtime de modelos.
2. OpenCode es la autoridad de ejecución de agentes y providers.
3. Hermes es la autoridad de misión, estados, recuperación y terminación.
4. Engram es memoria; `.hermes-state` es estado operativo transaccional.
5. Hermes resuelve sin aprobación técnica subordinada.
6. El usuario solo interviene en objetivo, alcance, autoridad, seguridad,
   presupuesto o datos irreversibles.
7. `MISSION_COMPLETE` exige cinco predicados verificables.

## Artefactos

- `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md`
- `.hermes/plans/2026-08-20_HERMES_MISSION_CONTROLLER.md`

## Tests

No se ejecutan tests de runtime en esta fase: solo se crean contratos y plan.
La implementación deberá añadir fake adapter, tests de estados, recuperación,
reanudación y terminación.

## Resultado

**PASS documental:** la arquitectura queda suficientemente especificada para
comenzar MC-0. No se declara implementación completa.

## Siguiente acción

Ejecutar MC-0 y MC-1 en commits separados, manteniendo el estado preexistente
de `.hermes/audit_state.json` fuera de cambios no relacionados.
