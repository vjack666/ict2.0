# ICT SYSTEM — Versión ordenada (andamiaje de subagentes)

Carpeta de trabajo nueva, arrancada desde `SMC-SYSTEMS` el 2026-08-15.
Objetivo de esta primera pasada: **reunir los subagentes en una estructura
ordenada y autónoma**, siguiendo el ciclo de migración controlada
(auditar → diseñar → autorizar → ejecutar).

> **Estado: sistema funcional — motor presente y cableado.**
> El motor ICT (`engine/`, `detectors/`, `analysis/`, `agents/`, `orchestration/`)
> ya fue rescatado y arranca dentro de ICT SYSTEM. Los agentes de `analysis.*`
> consumen el motor (`CANONICAL_ENGINE = sequence`); la capa de consenso
> (`AgentOrchestrator`) resuelve imports y produce columnas `agent_*`.
> Fase D (FVG/OB canónicos + lineage causal) = PASS; AHF (navegación MTF) =
> implementado. El motor **NO emite órdenes**: AHF llega a `SETUP_READY` y se
> detiene (`AHF_STATE_NOT_ENTRY`). Puedes verificar con `pytest tests/` (52 PASS)
> y `python -c "import engine.ahf, engine.sequence, agents.orchestrator"`.
>
> 📌 Este README es contexto de arranque, **no autoridad normativa**. La
> autoridad vigente está en `docs/INDICE_AUTORIDAD.md` y los documentos que ese
> índice lista (contratos/SDDs de FVG/OB, MTF, auditoría). Si este README
> contradice un documento de `docs/`, manda el documento de `docs/`.

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
├── governance/      # Agentes de GOBERNANZA (rol + protocolo, solo docs .md)
│   ├── ROLES_GOBERNANZA.md
│   ├── ORQUESTADOR.md
│   ├── PROTOCOLO_AGENTE.md
│   ├── CONTRATO_ORDEN.md
│   ├── investigador.md
│   ├── ingeniero.md
│   ├── auditor_independiente.md
│   ├── memoria_institucional.md
│   ├── cumplimiento_operativo.md
│   └── alertas_tempranas.md
└── docs/             # AUTORIDAD DOCUMENTAL (tesis ICT completa + diccionarios)
    ├── INDICE_AUTORIDAD.md   # que es autoridad vs que se dejo fuera y por que
    ├── 00_HERMES_START_HERE.md   # punto de entrada operativo
    ├── auditoria/          # AUDITORIA_* (FVG/OB, AHF/MTF, Funnel, Fase0, A0-A9, estado)
    ├── contratos/          # CONTRATO_* (AHF, Context State, Multi-TF Layers, Sequential Events, FVG/OB, Funnel, Hermes FVG/OB, MTF Navigation Graph)
    ├── experimentos/       # EXP_* (Sequence×Context State, FVG/OB Causal, Multifactor, Sequential Canonical BOS, Sequential Expectancy Complete)
    ├── planificacion/      # SDD_* (Context State MTF, Funnel Audit, FVG/OB Architecture Map, FVG/OB Engine, FVG/OB Prebacktest Addendum)
    ├── ict/
    │   ├── SPEC_TESIS_FORMAL.md   # Contrato fuente FIRMADO (25 secc) — autoridad maxima
    │   ├── 00_INDICE.md           # Indice de la biblioteca ICT
    │   ├── 01_KILLZONES.md ... 21_POI.md  # Libros de la tesis (setups + narrativa)
    │   └── 20_TESIS_ICT.md       # Sintesis unificadora
    ├── tesis/                    # Hallazgos y SDD de tesis
    │   ├── HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md
    │   ├── HALLAZGOS_SESGO_BACKTEST.md
    │   ├── PLAN_RESCATE_POI_HTF.md
    │   ├── SDD_LTF_ENTRY_LAYER.md
    │   ├── SDD_M2_LINEAGE.md
    │   └── SDD_RESCATE_POI_HTF.md
    ├── reglas/
    │   ├── ICT_RULEBOOK.md         # Diccionario machine-readable de deteccion ICT
    │   └── WYCKOFF_RULEBOOK.md     # Diccionario de deteccion Wyckoff
    ├── wyckoff/                    # Teoria Wyckoff vigente (compras/ventas)
    └── briefs/                     # Briefs de sesion generados
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

## Consumidores internos conocidos

- `orchestration/orchestrator.py` importa de `analysis.*` (ICTAgent, StructureAgent,
  WyckoffAgent, DecisionAgent, DecisionConfig, AnalysisResult) — **resuelve OK**.
- `analysis/ict_agent.py` expone `CANONICAL_ENGINE = sequence` (motor en `engine/`).

> Nota: menciones previas a `orchestration.backtest_validation_graph` /
> `orchestration.harness_adapter` como "dependencias rotas" eran de un estado
> temprano del repo. En el árbol actual **ningún módulo activo los importa**
> (verificado por grep 2026-08-19), por lo que ya no son deuda viva.

## Estado y siguientes pasos

El motor (`engine/`) ya es capa permanente y está cableado a los agentes. El
trabajo en curso (ver `.hermes-index.md` y `docs/`) se centra en:

1. **Auditoría temporal AHF/MTF (TNA)** sobre EURUSD 20Y — navegación, rollback,
   duración por estado, tamaño FVG/OB en pips. **No es backtest.**
2. **SEQUENCE × CONTEXT STATE** — tras TNA, medir si la secuencia bajo contexto
   HTF cambia la distribución del outcome (con stop fijo).
3. **Backtest / Entry** — solo después de cerrar A0-A9 + Funnel + TNA.

El README no define el plan de trabajo; para eso ver
`docs/00_HERMES_START_HERE.md` y `docs/PLAN_HERMES_FVG_OB.md`.
