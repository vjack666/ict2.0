# PASO 3 — SDD (Market State + Setup Builder v1.2)

- **Fecha**: 2026-08-27
- **Agente**: Hermes (especificación) — sin implementación
- **Base autoritativa**: `codex/visual-replay-wyckoff-v1-1-20260826` @ `d562ac489b88943e3c92cd4b26f200d5e4b3ec29`
- **Estado**: COMPLETED (SDD creado, DRAFT para revisión)
- **Regla**: READ/COMPARE/TRACE/CLASSIFY/DEDUCE. Nada de código.

---

## 1. Objetivo

Escribir el SDD (Specification-Driven Development) que especifica técnicamente la
arquitectura congelada en el PASO 2: Market State persistente + Setup Builder.

## 2. Entregable

**SDD creado**: `docs/planificacion/SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md`
(en la base autoritativa, worktree de Codex).

Contenido:
- Objetivo y límites (diagnóstico, invariantes heredadas del v1.1).
- Contrato temporal (heredado, sin cambios).
- Arquitectura objetivo: `backtest/market_state.py` (EXTIENDE timeline/replay),
  `backtest/setup_builder.py` (única pieza genuinamente nueva), cambios en
  `schema.py` (→ 1.2), `wyckoff_timeline.py`/`replay.py`, visor `App.jsx`.
- Contrato JSON v1.2 (campos `market_state` y `setups` nuevos).
- Identidad y reproducibilidad (heredado).
- Validación y gates (G0-G9).
- Implicaciones WYCKOFF-7 (permitido por arquitectura, bloqueado por datos).

## 3. Estado

**DRAFT PARA REVISIÓN**. Requiere revisión de Ruben antes de la implementación
(PASO 4).

## 4. Siguiente acción

Esperar aprobación de Ruben para **PASO 4 (implementación M1-M5)**. NO implementar
nada hasta la aprobación.

## Addendum de reconciliación — 2026-08-30

Este worklog conserva el estado histórico de la línea `backtest/` y de su SDD
v1.2 en la rama del visor. Para la rama operativa actual, la autoridad vigente
es `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`
y el plan `.hermes/plans/2026-08-30_POST_A7_ENGINE_STATE_EPISODES.md`.

No debe interpretarse este documento como una orden actual de ejecutar PASO 4:
Lifecycle, MarketState y Setup Builder ya existen en `engine/` y no deben
duplicarse en `backtest/` ni en un segundo motor.
