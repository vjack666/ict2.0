# Worklog — Plan de integración Wyckoff en engine

**Fecha:** 2026-08-20  
**Estado:** OBJETIVO PUBLICADO — implementación queda para Codex/Hermes

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