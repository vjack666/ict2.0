# Inventario Wyckoff — runtime, legacy, documentación e historia

**Fecha:** 2026-08-20  
**Commit de referencia:** `8e78718`  
**Gate:** WYCKOFF-0 — inventario documentado; consolidación runtime pendiente.

## Hallazgos clasificados

| source_path | símbolo/clase | clasificación | consumidores/imports | acción |
|---|---|---|---|---|
| `analysis/wyckoff_agent.py` | `WyckoffAgent` y métodos `_classify_phase`, `_detect_*` | `ANALYSIS_ONLY` / `LEGACY_COMPAT` | `orchestration/orchestrator.py`, smoke/plot scripts | no copiar; extraer contrato PIT a `engine/Wyckoff`; conservar hasta migrar consumidores |
| `agents/wyckoff_agent.py` | reexport `WyckoffAgent` | `LEGACY_COMPAT` | imports externos potenciales | mantener wrapper solo mientras exista consumidor; no autoridad del brief |
| `orchestration/orchestrator.py` | `AgentOrchestrator` | `LEGACY_COMPAT` | `scripts/smoke_consensus.py`, `scripts/plot_htf_reading.py` | no conectar silenciosamente al snapshot LTF; adaptar después si sigue siendo necesario |
| `analysis/decision_agent.py` | pesos/conflict penalty de agentes | `DUPLICATE` para el nuevo contrato | `orchestration/orchestrator.py` | no usar como política ICT↔Wyckoff canónica; reemplazar por `phase_state` explicable |
| `docs/reglas/WYCKOFF_RULEBOOK.md` | especificación de fases/eventos | `DOCUMENTATION` | biblioteca normativa | conservar como referencia; no contiene API runtime |
| `docs/wyckoff/compras/**` | acumulación, eventos y relación ICT | `DOCUMENTATION` | lectura humana | conservar y citar en el runtime |
| `docs/wyckoff/ventas/**` | distribución, eventos y relación ICT | `DOCUMENTATION` | lectura humana | conservar y citar en el runtime |
| `.hermes/plans/2026-08-20_WYCKOFF_ENGINE_INTEGRATION.md` | contrato de migración | `DOCUMENTATION` | Codex/Hermes | autoridad operativa de esta fase |

## Búsqueda de ramas e historia

- Ramas relevantes: `origin/docs/wyckoff-engine-integration-2026-08-20` y `main`
  apuntan al mismo diseño documental `8e78718`; no apareció un runtime
  alternativo consolidado en otra rama visible.
- `git log --all -S'WyckoffAgent'` devuelve la introducción del agente en
  `0b0c2e8` y el refactor defensivo en `44ad8a3`; no aparece una implementación
  posterior en `engine/`.
- La historia contiene eliminaciones de `ict_backtest/**`, pero no una carpeta
  runtime `smc/` o `ict/` que pueda declararse autoridad Wyckoff actual.
- Las referencias a `scripts/fase_wyckoff_m15.py` en la biblioteca no resuelven
  a un archivo presente en `scripts/`; se clasifican como documentación
  histórica no ejecutable.

## Decisión de migración

Se crea `engine/Wyckoff/` como única autoridad runtime. La nueva API será
read-only, serializable y closed-only. El agente legacy no se elimina todavía
porque `orchestration/orchestrator.py` lo consume; se documenta como wrapper/
compatibilidad y queda fuera de la ruta `daily_motor → brief`.

La nueva capa no usará EMA, OTE, Fibonacci ni stochastic como bias/veto. El
tick-volume será `RELATIVE_ONLY` cuando exista y `UNAVAILABLE` cuando falte.
