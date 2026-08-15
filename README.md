# ICT SYSTEM — Versión ordenada (andamiaje de subagentes)

Carpeta de trabajo nueva, arrancada desde `SMC-SYSTEMS` el 2026-08-15.
Objetivo de esta primera pasada: **reunir los subagentes en una estructura
ordenada y autónoma**, siguiendo el ciclo de migración controlada
(auditar → diseñar → autorizar → ejecutar).

> ⚠️ **Estado: andamiaje, NO sistema funcional.**
> Estos agentes son **consumidores del motor** (`ict_backtest.canonical`,
> `detectors`, `engine`). En esta carpeta aislada aún NO se copió el motor,
> así que los imports de `analysis.*` / `orchestration.*` / `agents.*` solo
> resolverán una vez que en fases siguientes se traiga el motor al árbol.
> La copia fue literal y verificada contra el origen; no se reescribió lógica.

## Estructura

```
ICT SYSTEM/
├── agents/          # SHIMs de compatibilidad (2 líneas) → reexportan de analysis/ y orchestration/
│   ├── base.py
│   ├── ict_agent.py
│   ├── decision_agent.py
│   ├── structure_agent.py
│   ├── wyckoff_agent.py
│   └── orchestrator.py
├── analysis/        # IMPLEMENTACIÓN REAL de los agentes de análisis/código
│   ├── __init__.py
│   ├── base.py               # AnalysisResult, AgentProtocol
│   ├── ict_agent.py          # ICTAgent  (escora de bias/confianza; NO decide trades)
│   ├── decision_agent.py     # DecisionAgent, DecisionConfig, DecisionRecord
│   ├── structure_agent.py    # StructureAgent
│   └── wyckoff_agent.py      # WyckoffAgent
├── orchestration/   # Orquestador + grafo de validación
│   ├── __init__.py
│   ├── orchestrator.py       # AgentOrchestrator, AGENT_COLUMNS
│   └── README.md             # (del origen) notas del orquestador
└── governance/      # Agentes de GOBERNANZA (rol + protocolo, solo docs .md)
    ├── ROLES_GOBERNANZA.md
    ├── ORQUESTADOR.md
    ├── PROTOCOLO_AGENTE.md
    ├── CONTRATO_ORDEN.md
    ├── investigador.md
    ├── ingeniero.md
    ├── auditor_independiente.md
    ├── memoria_institucional.md
    ├── cumplimiento_operativo.md
    └── alertas_tempranas.md
```

## Mapa de imports (contratos de los subagentes)

| Módulo en `agents/` (SHIM) | Reexporta desde | Símbolos públicos |
|---|---|---|
| `agents/base.py` | `analysis.base` | `AnalysisResult`, `AgentProtocol` |
| `agents/ict_agent.py` | `analysis.ict_agent` | `ICTAgent`, `CANONICAL_ENGINE` |
| `agents/decision_agent.py` | `analysis.decision_agent` | `DecisionAgent`, `DecisionConfig`, `DecisionRecord` |
| `agents/structure_agent.py` | `analysis.structure_agent` | `StructureAgent` |
| `agents/wyckoff_agent.py` | `analysis.wyckoff_agent` | `WyckoffAgent` |
| `agents/orchestrator.py` | `orchestration.orchestrator` | `AgentOrchestrator`, `AGENT_COLUMNS` |

Consumidores internos conocidos (en el origen `SMC-SYSTEMS`):
- `orchestration/orchestrator.py` importa de `analysis.*` (ICTAgent, StructureAgent,
  WyckoffAgent, DecisionAgent, DecisionConfig, AnalysisResult).
- `legacy/harness/__main__.py` y `scripts/live_market_read.py` importan
  `orchestration.backtest_validation_graph` / `orchestration.harness_adapter`.

## Dependencias rotas / pendientes (NO copiadas)

Estos módulos son importados por consumidores legacy pero **NO existen en
`orchestration/` activo** — solo viven en `legacy/` del repo origen:

- `orchestration/backtest_validation_graph.py` → existe solo en `legacy/orchestration/`
- `orchestration/harness_adapter.py` → existe solo en `legacy/**/harness_adapter.py`

Decisión de orden: **no se copiaron** para no arrastrar código legacy roto al
andamiaje limpio. Resolver en una fase posterior (promover a capa permanente o
eliminar el consumidor). Ver auditoría de consumidores en `SMC-SYSTEMS`.

## Siguientes fases sugeridas (fuera de alcance de esta pasada)

1. Traer el **motor** (`engine/`) como capa permanente — es la única fuente de
   decisión; los agentes de `analysis/` lo consumen, no lo reimplementan.
2. Resolver `backtest_validation_graph` / `harness_adapter` (promover de legacy o
   cortar el import).
3. Copiar `detectors/`, `signals/`, `ict_backtest/` según el mismo principio de
   fachada-sobre-borrado y matriz de 12 dimensiones.
4. (`agents/governance/` del origen ya está en `governance/` aquí, fuera de la
   carpeta de código, porque es dominio de rol/protocolo, no de ejecución.)
```
