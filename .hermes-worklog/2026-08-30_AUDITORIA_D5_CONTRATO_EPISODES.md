# Bitácora — Auditoría independiente D5: contrato + SDD Episodes/Funnel v1

**Fecha:** 2026-08-30
**Agente:** Hermes (director de D2) actuando como revisor D5 independiente del contrato
**Departamentos:** D1 Documentación, D2 Ingeniería, D5 Assurance
**Estado:** COMPLETED — revisión independiente; contrato y SDD reconciliados con la API real de `engine/`; T1.7 PASS (documental, con correcciones aplicadas).
**Referencias:** `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`, `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md`, `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`, `engine/market_state.py`, `engine/setup_builder.py`, `engine/market_object.py`.

## Alcance

Revisión independiente del contrato y SDD de Episodes/Funnel v1 antes de autorizar la implementación de `engine/episodes.py` (gate T1.7 del plan `.hermes/plans/2026-08-30_EPISODES_FUNNEL_V1.md`). No se escribió código de Episodes en esta fase.

## Hallazgos (D5)

Se contrastó el contrato/SDD contra la API real del motor. El diseño causal es sólido (1 Setup = 1 Episode, identidad `sha256`, lineage `context→poi→refinement→confirmation→trigger`, FULL/PREFIX, sin futuro). Se detectaron **5 discrepancias documentales** que habrían forzado a T2 a inventar campos o violar fail-closed:

1. **Interfaz de entrada.** El contrato §3 ponía `build_setups_at(market_state, T, context)` y un campo `observation_time`. La API real es `build_setups_at(ms, t, ctx)` y no existe `observation_time` aparte de `T`. El `decision_time` del Episode es el `T` de entrada. → Corregido: la entrada es un `Setup` compuesto por `build_setups_at`, y `decision_time = T`.
2. **Identidad con componentes faltantes.** `Setup` puede tener `confirmation`/`trigger` en `None` (setup incompleto). La clave canónica original no definía el caso `None`, rompiendo la determinística. → Corregido: sentinel `"NONE"` por componente faltante.
3. **Mapeo de estados.** El contrato §5 listaba estados del Episode (`ACCEPTED/REJECTED/SUPERSEDED`) pero no decía de dónde provienen. La autoridad de elegibilidad es `SetupEligibility` (no reimplementar). → Corregido: mapeo explícito `ELIGIBLE→ACCEPTED`, `SUPERSEDED→SUPERSEDED`, `BLOCKED→REJECTED(SETUP_BLOCKED)`, `OUT_OF_CONTEXT→REJECTED(OUT_OF_CONTEXT)`.
4. **Campo de tiempo.** `available_time` no existe en `MarketObject`; el campo real de disponibilidad es `candidate_time` y `tradable_time`/`confirmation_time` existen. → Corregido: `available_time := candidate_time`; orden `confirmation_time <= tradable_time <= decision_time` sobre el `MarketObject`.
5. **Ambigüedad E2 / FULL/PREFIX.** E2 podía confundirse con el gate G7 de `MarketState`. → Corregido: E2 es determinismo causal del funnel (`build_episodes` sobre datos FULL == truncados en T para varias decisiones T).

## Clasificación de gates (E0–E7) tras revisión

| Gate | Estado | Nota |
|---|---|---|
| E0 Contrato + SDD presentes y enlazados | PASS | reconciliados con la API real |
| E1 Entrada exclusiva `projection_at(T)` | PASS (por diseño) | `build_setups_at` usa `projection_at` internamente |
| E2 FULL/PREFIX literal | PASS (criterio clarificado) | distinto de G7 |
| E3 Identidad estable/idempotencia | PASS (sentinel NONE añadido) | |
| E4 Rechazos/lineage/tiempos completos | PASS (mapeo + campos reales) | |
| E5 Determinismo/checksum | PASS (por diseño) | excluye `generated_at` |
| E6 Suite focal/completa verde | PENDIENTE (T3) | no es responsabilidad de T1.7 |
| E7 Bitácora/índice/graphify/commit | PENDIENTE (T4) | no es responsabilidad de T1.7 |

T1.7 es una revisión **documental**; los gates de ejecución (E6/E7) se cierran en T3/T4.

## Verificación de la capa previa (baseline T0)

Se ejecutó la suite focal de la capa anterior (Lifecycle, MarketObject, MarketState, Setup Builder) para confirmar que la entrada de Episodes está sana:

```
pytest tests/test_lifecycle.py tests/test_market_object_pd_contract.py tests/test_market_state.py tests/test_setup_builder_*.py
→ 94 passed  (HEAD cdc6bc0)
```

Esto reproduce la evidencia "94 passed" de la bitácora pre-Episodes (`2026-08-30_AUDITORIA_PRE_EPISODES_FUNNEL.md`). HEAD ahora `cdc6bc0` (commit del contrato+plan), superior al `1757793` registrado en esa bitácora.

## Riesgos

- El stash `pre-episodes-funnel-local-generated-work-2026-08-30` NO contiene `episodes.py`/`funnel` (solo data/reports/docs); se confirma que no hay autoridad duplicada en `engine/` y no se derivó código de él (cumple SDD padre §10/§11).
- `engine/episodes.py` aún no existe; T2 lo crea bajo write set cerrado.
- E2 se ejecuta en T3 sobre un corpus sintético de `MarketState` (sin descargar datos ni tocar datasets reales).

## Decisión

Contrato y SDD **aprobados para implementación** tras las 5 correcciones documentales. Se autoriza T2 (crear `engine/episodes.py`) bajo el write set cerrado del plan. No se declara `COMPLETED` global hasta E6/E7 en T3/T4.

## Siguiente acción

Iniciar T2: implementar `engine/episodes.py` con `build_episodes(ms, decisions_T, ctx, config)` que (a) consume `build_setups_at`, (b) valida temporalidad/autoridad/lineage fail-closed, (c) forma `episode_id` determinista con sentinel NONE, (d) separa outcomes/labels futuros, (e) produce `FunnelRecord` por etapa con razón explícita.
