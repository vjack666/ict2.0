# Worklog — Organigrama operativo ICT 2.0

**Fecha:** 2026-08-22  
**Misión:** convertir la estructura del repositorio en una organización por departamentos, con Codex como CEO operativo y el usuario como cliente.  
**Estado:** COMPLETED — organización lógica; migración física pendiente de auditoría.

## Evidencia inicial

- Se inspeccionó el árbol real del repositorio y el estado Git antes de editar.
- `agents/` y `orchestration/` son capas activas y se conservaron.
- `docs/REPOSITORY_ORDER.md` exige separación lógica antes de cualquier movimiento físico.
- `opencode.json` contiene configuración local del servidor MCP Engram para el proyecto `ict2.0`.

## Trabajo realizado

- Se creó `AGENTS.md` como ley operativa persistente para Codex y agentes delegados.
- Se creó `governance/ORGANIGRAMA_ICT_2_0.md` con pisos, departamentos, roles, límites, enrutamiento y cierre de memoria.
- Se creó `governance/DEPARTMENT_REGISTRY.json` como registro machine-readable.
- Se añadió `tests/test_department_registry.py` para comprobar cobertura de departamentos, rutas existentes y controles obligatorios.
- Se actualizaron `README.md` y `docs/INDICE_AUTORIDAD.md` para enlazar la nueva capa organizativa.
- Se implementó `orchestration/mission_controller/` para enrutar solicitudes y persistir misiones/tareas MC-0/MC-1 sin abrir sesiones externas.
- Se separó el cargo funcional del `agent_key` OpenCode para que la futura delegación sea trazable.
- Se implementó MC-2 con `AgentRegistryResolver`, validando los `agent_key` contra `opencode.json` antes de crear una misión.
- Se añadió `OpenCodeCliAdapter` para construir delegaciones contractuales en dry-run, con ejecución de procesos desactivada por defecto.
- Se añadió normalización de eventos JSONL, extracción de `provider_session_id` y base para resume cuando el proveedor entregue un ID real.
- Se verificó la API local real de OpenCode y se implementó `OpenCodeHttpAdapter` con creación de sesiones, `prompt_async`, estado, hijos, polling y resume.
- Se implementó reconciliación de tareas en `MissionController`: `RUNNING`/`WAITING_FOR_AGENT`, `OBSERVE` tras finalizar, `RECOVER` tras fallo y prohibición de completar sin evidencia.
- Se añadió recuperación tras reinicio, listado durable de misiones, gates explícitos, verificación de outputs/evidencia y cierre condicionado por los cinco predicados normativos.
- Se añadió `write_worklog()` para cierres legibles y `audit_mission()` para hallazgos fail-closed de trazabilidad y límites.
- Se implementó `EngramCliMemorySink` y se verificó el guardado real del resumen institucional en Engram: observación `#492`, proyecto `ict2.0`.
- Se certificó el primer circuito end-to-end seguro del Mission Controller: misión `MC-20260822-164150-f48c89`, D0/COO, delegación OpenCode dry-run, cinco gates verdaderos, auditoría sin hallazgos y memoria Engram `#494`.

## Decisión de seguridad

No se movieron carpetas. La analogía empresarial queda implementada como una capa de responsabilidad sobre rutas canónicas, evitando romper imports, runners o workflows.

## Próxima acción

Completar el backend live-events/resume de OpenCode y mantener Engram como memoria de razonamiento, no como fuente de estado transaccional.

## Graphify

- Skill instalada en `.codex/skills/graphify/` con integración project-scoped para Codex.
- Actualización incremental ejecutada sobre el repositorio el 2026-08-22.
- Resultado: 5.205 nodos, 8.996 relaciones y 434 comunidades.
- `graphify-out/graph.json` y `graphify-out/GRAPH_REPORT.md` quedaron regenerados.
- La visualización HTML no se regeneró porque el grafo supera el límite automático de 5.000 nodos; no afecta al grafo ni al reporte.
- El organigrama canónico continúa en `governance/ORGANIGRAMA_ICT_2_0.mmd` y `governance/DEPARTMENT_REGISTRY.json`.

## Preparación de apertura

- Se creó `governance/OPENING_READINESS_CHECKLIST.md` para separar controles de fin de semana de la operación de mercado.
- La apertura queda bloqueada si falla auditoría, trazabilidad, datos, PIT/leakage, OOD/drift, permisos o `can_trade`.
- Se implementó `scripts/opening_readiness.py`, comprobación local fail-closed que no conecta al mercado ni habilita trading.
