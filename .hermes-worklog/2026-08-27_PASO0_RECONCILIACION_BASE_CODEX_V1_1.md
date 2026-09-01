# Worklog — PASO 0: Reconciliación de la base real de Codex (v1.1)

**Fecha:** 2026-08-27 (UTC-05)
**Rama:** codex/audit-hermes-cert-20260826 @ 602ea75
**Estado:** COMPLETADO (gate PASO 0 superado; no se implementó nada)

## Contexto

La investigación anterior de Hermes (2026-08-27_MARKET_STATE_DEDUCCION.md) se
realizó sobre la base `602ea75`, pero Codex ya construyó una versión posterior
del laboratorio en otra rama/worktree. Antes de diseñar o implementar Market
State, se reconcilió la base real de Codex para evitar duplicar lo ya construido.

## BASE AUTORITATIVA

```text
BRANCH:
codex/visual-replay-wyckoff-v1-1-20260826

COMMIT:
d562ac489b88943e3c92cd4b26f200d5e4b3ec29

WORKTREE:
C:/Users/v_jac/Documents/codex-worktrees/ict-wyckoff-viewer-v1-1

ESTADO:
limpio (sin cambios sin commitear)
```

## CONSERVAR (ya existe en v1.1)

```text
Replay causal vela cerrada      replay.py:636 run_visual_replay
decision_time                   schema.py:248, wyckoff_timeline.py:131
_closed_prefix                  wyckoff_timeline.py:24-28
Timeline por vela               wyckoff_timeline.py:130
Contextos D1/H4/H1/M15/M5/M1    replay.py:30 DEFAULT_TFS
authority_tf                    schema.py:136, replay.py:49
WyckoffSnapshot                 wyckoff_timeline.py:163
Eventos Wyckoff                 wyckoff_timeline.py:173-191
FSM_CONTRACT                    wyckoff_timeline.py:20 (RUNTIME_BASIC_NOT_WYCKOFF_7)
Alineación/conflicto ICT↔Wyckoff snapshot.ict_alignment / snapshot.conflict
Estructura ICT (Swing/BOS/CHOCH) replay.py:706 extract_structure_events
Separación decisión/outcome     schema.py:394-411 (PENDING vs confirmado)
Visor React                     viewer/src/App.jsx
Carriles multi-TF               App.jsx:354-365
Evidencia/source refs           schema.py:355-357
Prefix stability / no-repaint   _closed_prefix + schema.py:249
Determinismo                    stable_sha256 / artifact_content_sha256
```

## EXTENDER (existe parcialmente)

```text
schema v1.1                     añadir entidades persistentes
timeline/replay                 proyectar MarketObject por vela
visor                           dibujar zonas con lifecycle (hoy solo markers)
delta T-1→T                     hoy es delta de campos, no de entidades
deduplicación multi-TF          hoy solo dedup de eventos Wyckoff por key
```

## FALTA REALMENTE

```text
MarketObject projection         el motor YA lo produce; el replay NO lo serializa
Persistent Market State         entidades vivas en T (no existe concepto)
Setup State / Setup Builder     no existe nada de checklist/condiciones
```

## Evidencia clave del gap

- `grep MarketObject|ObjectState|origin_tf|PARTIALLY_MITIGATED|CONSUMED|INVALIDATED`
  en `backtest/` y `viewer/src/` → **0 resultados**.
- `engine/market_object.py:38` define `ObjectState` (CREATED..CONSUMED) y
  `:55` `_ALLOWED_TRANSITIONS`, pero el artifact `VisualBacktest`
  (`schema.py:79-148`) no tiene campo de MarketObject.
- `wyckoff_timeline.py:171` fuerza `range_id=None, episode_id=None` y
  `schema.py:284-285` prohíbe que el runtime básico los rellene → el v1.1
  produce SNAPSHOTS, no entidades persistentes.
- El visor dibuja markers puntuales (`App.jsx:124-177`) y el rango actual como
  3 líneas (`App.jsx:179-193`); no puede representar zonas vivas con lifecycle.

## Conclusión

La hipótesis de Hermes se confirma en lo esencial (MarketObject con lifecycle
ya existe en engine/ y el v1.1 no lo serializa), pero se corrige en el alcance:
NO hace falta "v2 desde cero" ni módulos nuevos (market_state.py/instant.py).
Hace falta EXTENDER el v1.1 con la capa de entidades persistentes + Setup State.

## Estado metodológico corregido

```text
Código real      ✅ COMPLETO
Tesis / SDD       ✅ COMPLETO
Codex v1.1        ✅ RECONCILIADO
Fuentes externas  ⏳ PASO 1 (pendiente)
```

## SIGUIENTE ACCIÓN

PASO 1 — investigación externa y contraste metodológico (no implementar).
