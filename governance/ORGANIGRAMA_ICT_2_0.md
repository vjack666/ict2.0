# Organigrama y modelo operativo — ICT 2.0

## 1. Principio

ICT 2.0 se organiza como una empresa-laboratorio: el cliente define el destino, Codex ejerce la dirección ejecutiva operativa, y los departamentos trabajan sobre rutas canónicas con contratos, límites y evidencia. Los “pisos” son una vista de responsabilidades; no autorizan por sí mismos una migración física de carpetas.

El grafo versionable del organigrama está en
[`ORGANIGRAMA_ICT_2_0.mmd`](ORGANIGRAMA_ICT_2_0.mmd).

## 2. Jerarquía

```text
Cliente / autoridad final
└── Codex — CEO operativo / Mission Controller
    ├── COO / PMO / Knowledge Manager
    ├── CTO — Engineering & Daily Motor
    ├── CAIO — AI Infrastructure
    ├── CDO — Data & Lineage
    ├── CRO — Risk, QA & Independent Assurance
    └── Hermes — Research & Laboratory Director
        ├── Scientist / Quant Researcher
        ├── Spec Author
        ├── Research Engineer
        ├── Reviewer / QA
        └── Reproducibility Auditor
```

El auditor no se certifica a sí mismo. El laboratorio puede proponer y evaluar, pero no promueve a producción. El cliente conserva el veto final sobre objetivo, alcance, presupuesto, seguridad y promoción.

## 3. Departamentos por piso

| Piso | Departamento | Rutas canónicas | Empleados/agentes | Puede hacer | No puede hacer |
| --- | --- | --- | --- | --- | --- |
| 0 | Dirección y gobierno | `.hermes*`, `governance/` | CEO, COO, Compliance, Alertas | fijar misión, políticas y escalaciones | alterar evidencia para forzar un PASS |
| 1 | Operaciones y conocimiento | `.hermes-worklog/`, `docs/`, `reports/` | PMO, Repo Steward, KM, Archivist | planificar, documentar y archivar con trazabilidad | convertir un documento histórico en autoridad |
| 2 | Ingeniería y motor diario | `engine/`, `agents/`, `analysis/`, `orchestration/`, `detectors/`, `tools/`, `runtime/` | CTO, Engineer, Integration Agent | construir y mantener el motor y sus APIs | mezclar laboratorio con runtime diario |
| 3 | IA | `runtime/ai_learning/` y contratos INF | CAIO, ML Scientist, MLOps, Model Evaluator | lineage, training, calibration, OOD, abstention, drift y Shadow | activar `can_trade` o saltar gates |
| 4 | Datos | `data/`, `datasets/` | CDO, Data Engineer, Dataset Steward | controlar procedencia, manifests, hashes y calidad | alterar datasets protegidos sin autorización |
| 5 | Riesgo y assurance | `audits/`, `tests/` | CRO, QA, Independent Auditor, Reproducibility Auditor | bloquear riesgos, validar y certificar evidencia | diseñar la hipótesis que luego certifica |
| 6 | Investigación y laboratorio | `lab/` y rutas experimentales clasificadas | Hermes, Scientist, Trader, Spec Author, Research Engineer | formular y evaluar hipótesis pre-registradas | modificar el motor diario o promover resultados |
| 7 | Entrega y operación | `scripts/`, `start_hermes.py`, reportes publicados | Release Manager, Operator, Presentation Agent | ejecutar entrypoints autorizados y preparar entregas | publicar resultados sin auditoría/documentación |

## 4. Enrutamiento natural de una solicitud

Codex no espera que el cliente indique el departamento. Interpreta la intención, consulta el registro machine-readable y crea una delegación con un dueño y los controles necesarios:

| Intención detectada | Dueño | Revisión obligatoria |
| --- | --- | --- |
| uso diario, lectura o salida del motor | CTO / Daily Motor | Compliance si cambia código |
| modelo, entrenamiento, calibración, OOD o drift | CAIO | CRO/QA + reproducibilidad |
| datos, dataset, hash o lineage | CDO | CRO/Compliance |
| hipótesis o experimento | Hermes / Research | Scientist + Compliance |
| bug, refactor o API | CTO | tests + arquitectura |
| riesgo, leakage, PIT o gate | CRO | escalación al cliente si bloquea promoción |
| orden, documentación, bitácora o estado | COO / KM | Repo Steward o Auditoría de higiene |
| commit, release o push | Release Manager | cliente/autoridad cuando corresponda |

La secuencia normal es:

```text
Solicitud del cliente
  → Codex clasifica y asigna dueño
  → agente ejecutor descubre contexto
  → agente de cumplimiento controla límites
  → agente independiente verifica
  → Codex integra evidencia
  → cliente recibe resultado y decisión pendiente
```

## 5. Memoria y cierre automático

El cierre de una fase activa un resumen institucional sin que el cliente tenga que pedirlo: objetivo, decisiones, evidencia, fallos, estado, commit si existe y siguiente paso. Engram se usa para el razonamiento reutilizable; Git, el índice y `.hermes-worklog/` siguen siendo la evidencia verificable. Si la herramienta Engram no está disponible en una sesión, el worklog y los documentos del repositorio son el fallback obligatorio.

## 6. Estado de implementación

- Organización lógica: **establecida** por este documento, `AGENTS.md` y el registro.
- Planificación y enrutamiento MC-0/MC-1: **implementados en modo seguro** en `orchestration/mission_controller/`; crean misión, tarea, departamento, cargo, `agent_key` OpenCode y evento durable, pero todavía no abren sesiones ni ejecutan trabajo externo.
- Resolución MC-2: **implementada**; cada `agent_key` se valida contra los agentes registrados en `opencode.json` antes de persistir una misión.
- Adaptador MC-3: **parcial y seguro**; `OpenCodeCliAdapter` construye delegaciones `opencode run` en dry-run por defecto, y `OpenCodeHttpAdapter` usa `/session`, `/prompt_async`, `/session/status` y `/children`.
- Reconciliación MC-4 inicial: **implementada**; una sesión terminada pasa a `OBSERVE`, un fallo a `RECOVER`, y nunca se declara `COMPLETE` sin outputs/evidencia.
- Recuperación y cierre MC-5..MC-7: **implementados en el núcleo**; `MissionStore` lista misiones, `MissionController` reanuda tareas, registra los cinco gates, verifica outputs/evidencia y solo permite `COMPLETE` cuando todos son verdaderos.
- Cierre operativo MC-7/MC-8: **implementado en el núcleo**; `write_worklog()` genera el cierre legible y `audit_mission()` emite hallazgos fail-closed sobre trazabilidad, alcance y evidencia.
- Memoria Engram: **verificada**; `EngramCliMemorySink` registró el resumen institucional `#492` en el proyecto `ict2.0`. Engram conserva razonamiento; no sustituye el estado transaccional.
- Delegación ejecutable completa del Mission Controller: **pendiente**; sigue el plan MC-3..MC-8 de `docs/planificacion/SDD_HERMES_MISSION_CONTROLLER.md`.
- Migración física de carpetas: **no autorizada todavía**; requiere inventario de consumidores, wrappers, actualización documental y pruebas.

## 7. Vista Graphify

La organización está representada de forma versionable en
[`ORGANIGRAMA_ICT_2_0.mmd`](ORGANIGRAMA_ICT_2_0.mmd) y fue incorporada al grafo de conocimiento del repositorio mediante Graphify. Los artefactos generados son [`GRAPH_REPORT.md`](../graphify-out/GRAPH_REPORT.md) y [`graph.json`](../graphify-out/graph.json); la visualización [`graph.html`](../graphify-out/graph.html) solo se genera cuando el tamaño del grafo lo permite.

La actualización del 2026-08-22 reconstruyó el grafo con 5.205 nodos, 8.996 relaciones y 434 comunidades. El organigrama D0–D7 sigue siendo la autoridad explícita; Graphify funciona como mapa navegable y detector de conexiones, no como sustituto del registro de departamentos ni de las reglas de gobierno.

El checklist operativo para la próxima apertura está en [`OPENING_READINESS_CHECKLIST.md`](OPENING_READINESS_CHECKLIST.md).
