# Organigrama y modelo operativo — ICT 2.0

> Enmienda vigente de Ruben (2026-09-11): se autoriza avanzar autonomamente con entrenamiento y evaluacion de IA sobre datos existentes e inmutables. No se requiere una nueva autorizacion humana para cada fase. La ausencia de licencia o permiso escrito de Dukascopy deja de ser un bloqueo interno y no se solicitara licencia. Rige `docs/contratos/ENMIENDA_AUTONOMIA_ENTRENAMIENTO_20260911.md` sobre las restricciones anteriores de este documento. Los controles tecnicos se verifican durante el trabajo; sus fallos se reportan sin alterar datos ni fabricar certificaciones. Esta autorizacion no habilita trading ni promocion automatica a produccion.


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

## 7. Comparativo contra organigrama visual del 2026-09-20

La imagen previa marcaba el estado global como **EN DESARROLLO**, fase actual
**Integración Detectores -> MarketState** y progreso estimado **~35%**. Tras
los cierres del 2026-09-21, el estado correcto es:

```text
Fase actual: Mision 1 F2-F5 completada en shadow diagnostico
Progreso global estimado: ~72%
Siguiente hito: productor historico real seis-TF sobre fuente original
```

La subida de progreso no significa edge ni operación. Significa que el cableado
estructural llegó hasta Episodes/Funnel, backtest económico aislado, dataset IA
y entrenamiento shadow, todo con `can_trade=false`.

| Bloque de la imagen previa | Estado 2026-09-20 | Estado actual 2026-09-21 | Evidencia |
| --- | --- | --- | --- |
| 1. Datos | mayormente completo; versionado en progreso | **Completo para misión shadow**; fuente real pendiente para productor histórico final | manifiestos, `EURUSD.zip` protegido, hashes previos |
| 2. Detectores ICT | completo | **Completo como insumo** | detectores y tests existentes |
| 3. Inventario de eventos | completo | **Completo como inventario; no equivale a funnel real** | `ICT_EVENT_INVENTORY_AB_20260920.*` |
| 4. MarketState | puente en desarrollo | **Implementado + causal replay + linaje snapshot** | `engine/market_state.py`, `engine/daily_motor.py` |
| 5. Secuencias ICT | sin completar | **Avanzado / Phase-1 seis-TF instalada** | `engine/sequence.py`, `tests/test_sixtf_causal_sequence_phase1.py` |
| 6. Lifecycle | parcial/sin completar | **Implementado/revisado; integración completa real aún protegida por gates** | `engine/lifecycle.py`, tests de lifecycle/MarketState |
| 7. Funnel y episodios | sin completar | **Completo en capa v1 + Misión 1 shadow F2** | `engine/episodes.py`, `engine/mission1_six_tf_pipeline.py` |
| 8. Auditoría científica | sin completar | **Avanzada; FULL/PREFIX y regresión relacionada PASS en misión shadow** | 51 tests relacionados PASS, Graphify actualizado |
| 9. Inteligencia artificial | sin completar | **Shadow diagnostic completo; no productivo** | `mission1_dataset.json`, `mission1_training.json` |
| 10. Ejecución MT5 | sin completar | **No promovida; permanece bloqueada para trading** | `can_trade=false` |
| 11. Documentación y soporte | parcial | **Actualizada y versionada** | SDD, plan, worklogs, índice, commit `16deb66b` |

### Estado operativo por bloque

| # | Área | Estado actual | Semáforo | Próxima condición real |
| --- | --- | --- | --- | --- |
| 1 | Datos | Fuente preservada; no se fabricó M1 ni se modificó ZIP | 🟢 | usar fuente original en productor histórico real |
| 2 | Detectores ICT | Insumos disponibles | 🟢 | mantener regresiones |
| 3 | Inventario eventos | Conteos A/B preservados; no son setup/funnel | 🟢 | consumirlos solo si pasan replay causal |
| 4 | MarketState | Causal, point-in-time, con snapshot/lineage | 🟢 | productor histórico seis-TF real |
| 5 | Secuencias ICT | Multi-vela y seis-TF Phase-1 cerrada | 🟢 | conectar a episodios reales |
| 6 | Lifecycle | Contratos y tests existentes; no promoción operativa | 🟡 | replay integral por TF/fuente real |
| 7 | Funnel/Episodios | v1 implementado + Misión 1 F2 shadow PASS | 🟢 | reemplazar fixture contractual por productor histórico real |
| 8 | Auditoría científica | FULL/PREFIX shadow y regresión relacionada PASS | 🟢 | auditoría sobre datos reales completos |
| 9 | IA | Dataset + baseline shadow PASS; accuracy 0.333 | 🟡 | modelo real sólo tras dataset histórico causal |
| 10 | Ejecución MT5 | No autorizada / `can_trade=false` | 🔴 | requiere certificación, no parte de esta misión |
| 11 | Documentación | SDD, plan, worklog, índice y grafo actualizados | 🟢 | mantener bitácora por cada fase |

## 8. Vista Graphify

La organización está representada de forma versionable en
[`ORGANIGRAMA_ICT_2_0.mmd`](ORGANIGRAMA_ICT_2_0.mmd) y fue incorporada al grafo de conocimiento del repositorio mediante Graphify. Los artefactos generados son [`GRAPH_REPORT.md`](../graphify-out/GRAPH_REPORT.md) y [`graph.json`](../graphify-out/graph.json); la visualización [`graph.html`](../graphify-out/graph.html) solo se genera cuando el tamaño del grafo lo permite.

La actualización del 2026-09-21 reconstruyó el grafo con 17.147 nodos, 28.697 relaciones y 1.394 comunidades. El organigrama D0–D7 sigue siendo la autoridad explícita; Graphify funciona como mapa navegable y detector de conexiones, no como sustituto del registro de departamentos ni de las reglas de gobierno.

El checklist operativo para la próxima apertura está en [`OPENING_READINESS_CHECKLIST.md`](OPENING_READINESS_CHECKLIST.md).
