# Worklog — Plan de integración Wyckoff en engine

**Fecha:** 2026-08-20  
**Estado:** OBJETIVO PUBLICADO — implementación inicial ejecutada; gates finales abiertos

## Hallazgo inicial

Se revisó la arquitectura de lectura LTF/MTF y el inventario Wyckoff antes de prescribir una migración.

### Código localizado en `main`

- `analysis/wyckoff_agent.py`: agente analítico existente con fase, Spring, Upthrust, SOS, SOW, LPS, LPSY, esfuerzo/resultado, tick-volume y stochastic exhaustion.
- `agents/wyckoff_agent.py`: stub/compatibilidad legacy.
- No existe actualmente una carpeta runtime `engine/Wyckoff/`.
- La punta actual tampoco presenta un árbol de código `smc/` o una carpeta runtime `ict/`; el trabajo futuro debe buscar esos módulos en ramas e historia Git antes de declararlos ausentes.

### Documentación localizada

- `docs/reglas/WYCKOFF_RULEBOOK.md`: diccionario operacional conceptual.
- `docs/wyckoff/compras/**`: acumulación/compras y relación Wyckoff↔ICT.
- `docs/wyckoff/ventas/**`: distribución/ventas y relación Wyckoff↔ICT.
- `docs/wyckoff/06_relacion_ict.md` y equivalentes de compras/ventas establecen que Wyckoff aporta contexto y que ICT aporta la precisión; el conflicto debe quedar transparente.

## Decisión de arquitectura

Wyckoff se integra como una **capa especializada de lectura** dentro del motor único:

```text
HTF/Context State
    ↓
ITF/POI/Sequence
    ↓
Wyckoff evidence layer
    ↓
LTF ICT confirmation
```

No se autoriza un segundo motor, segundo Context State, segunda FSM o hard veto universal.

## Objetivo operativo

Clasificar la relación ICT/Wyckoff como:

```text
PRO_TREND
COUNTERTREND
TRANSITION
NEUTRAL
```

con `authority_tf` explícito y evidencia resoluble.

## Siguiente agente

Codex/Hermes debe ejecutar `.hermes/plans/2026-08-20_WYCKOFF_ENGINE_INTEGRATION.md`, actualizar el SDD/Plan LTF, migrar/extraer módulos después del inventario, probar PIT/determinismo/lineage, integrar el snapshot y dejar un worklog final con archivos movidos, módulos nuevos, wrappers, tests, resultados y limitaciones.

Este worklog no declara la integración PASS; documenta únicamente el diseño y el objetivo publicado.

## Iteración runtime — 2026-08-20

### Inventario y decisión

- Inventario registrado en `reports/audits/wyckoff_runtime_inventory_2026-08-20.md`.
- `analysis/wyckoff_agent.py` queda clasificado como `ANALYSIS_ONLY`/
  `LEGACY_COMPAT`; no se copió a runtime.
- `agents/wyckoff_agent.py` queda como compatibilidad porque todavía existen
  consumidores en `orchestration/orchestrator.py`.
- No se encontró una autoridad histórica runtime `smc/` o `ict/` reutilizable.

### Módulos runtime creados

Se creó `engine/Wyckoff/` como autoridad única de lectura:

- `types.py`: `WyckoffSnapshot`, eventos, fases, estados y `VolumeMode`.
- `phases.py`: clasificación causal de fase/rango sobre el prefijo cerrado.
- `events.py`: Spring, Upthrust, SOS, SOW, LPS/LPSY observables.
- `effort_result.py`: tick-volume relativo o `UNAVAILABLE`.
- `classifier.py`: `PRO_TREND`, `COUNTERTREND`, `TRANSITION`, `NEUTRAL`.
- `adapter.py`: integración read-only D1/H4/H1/M15 con Context State.

La capa no usa EMA/OTE/Fibonacci/stochastic como bias o veto, no crea AHF ni
Sequence paralelos y no cambia `direction_hint`.

### Integración producida

- `daily_motor.py` conserva `wyckoff` dentro del snapshot sin autorizar entrada.
- `scripts/brief_lunes.py` construye Wyckoff desde el mismo feed/decision time y
  lo muestra junto a Context State, Sequence, FVG/OB y retest.
- Muestra MT5 EURUSD: Context State `BULLISH`; Wyckoff D1
  `DISTRIBUTION / COUNTERTREND`; `authority_tf=D1`; conflicto explícito;
  resultado LTF `WAIT_LTF_CONFIRMATION`.

### Validación

- Pruebas dirigidas Wyckoff + motor: `20 passed, 1 warning`.
- Suite completa: `68 passed, 1 warning`.
- PIT y determinismo sintético cubiertos; no se declara PASS final.

### Gates actuales

| Gate | Estado |
|---|---|
| WYCKOFF-0 inventario | `PASS` |
| WYCKOFF-1 runtime | `IN PROGRESS` — wrappers legacy aún tienen consumidores |
| WYCKOFF-2 LTF/MTF | `IN PROGRESS` — snapshot integrado, AHF/POI ITF completo pendiente |
| WYCKOFF-3 clasificación | `IN PROGRESS` — cobertura base; ampliar eventos/estados |
| WYCKOFF-4 retest/lineage | `PARTIAL` |
| WYCKOFF-5 histórico + MT5 | `PENDING` |
