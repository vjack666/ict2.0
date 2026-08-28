# Planificación Setup Builder — ICT SYSTEM (2026-08-28)

## [MISSION BRIEF]

```
OBJETIVO LITERAL
    Construir engine/setup_builder.py que componga SETUPs desde MarketState,
    siguiendo la jerarquía ICT de temporalidades (HTF contexto -> POI -> LTF
    refinamiento -> confirmación -> trigger).

TIPO:            IMPLEMENTAR (capa de composición, no ejecución)
ALCANCE:         - Consumir MarketState en T (ya existe, certificable).
                  - Relacionar objetos por origin_tf / parent_object / related_objects.
                  - Producir Setup con setup_eligibility (ELIGIBLE/BLOCKED/
                    OUT_OF_CONTEXT/SUPERSEDED).
                  - Registrar linaje used_by_setup (NO alterar object_state).
NO-OBJETIVOS:    - No ejecuta órdenes.
                  - No hace backtest.
                  - No es la capa de Episodes/funnel de selección (posterior).
                  - No altera object_state (un SETUP no mata objetos).
CRITERIO DE TERMINACIÓN:
                  1. Tests deterministas ensamblan setup completo HTF->POI->
                     refinamiento->confirmación->trigger desde un MarketState.
                  2. setup_eligibility correcto ante contexto HTF cambiado.
                  3. Cero mutación de object_state por Setup Builder.
                  4. Integra con MarketState.snapshot_at(T) (replay causal).
```

## Contexto (Graphify, grafo fresco 5f782c5)

- `graphify update .` ejecutado: grafo ahora en HEAD 5f782c5 (10.388 nodos).
- `MarketState` (engine/market_state.py, community 16) YA EXISTE como nodo.
- `relate_fvg_ob()` (engine/relations.py, community 21) es la relación canónica
  FVG↔OB estricta y causal — reutilizable, no inventar.
- `Setup ICT (M15)` existe solo como *rationale* en plan_emitters.py (código
  legacy en .hermes-cert/, NO activo). No hay Setup Builder vivo en engine/.
- Conclusión del grafo: Setup Builder es una capa NUEVA que se apoya en
  MarketState + relations + mtf_navigation/narrative (contexto HTF). No hay que
  rescatar nada de SMC-SYSTEMS.

## Documentación actualizada (NO creada de cero)

- `docs/planificacion/SDD_FVG_OB_ENGINE.md` §13 — Setup Builder: meta, forma,
  regla de separación object_state vs setup_eligibility, criterio, dependencias.
- `docs/INDICE_AUTORIDAD.md` — sección "Capa de composición del motor"
  (Lifecycle -> Market State -> Setup Builder) añadida; setup_builder.py
  marcado como PENDIENTE.

## Siguiente acción

Implementar engine/setup_builder.py + tests/, luego re-auditar / certificar
(sin push; regla repo). Orden congelado:
  Lifecycle v1 ✅ -> Market State ✅ -> Setup Builder (AHORA) -> Episodes/funnel
  -> experimentos -> IA.

## [CIERRE — Setup Builder integrado (SDD 13.2-13.5)]

**Despliegue CEO (modo agentes en worktrees aislados):**

- Agente 1 (§13.2 Modelo): `wt_model` / `feature/sb-model` -> commit `8ab1ad0` (11 passed). VERIFICADO.
- Agente 2 (§13.3 Separación): `wt_sep` / `feature/sb-separation` -> commit `7da2adb` (8 passed). VERIFICADO.
- Agente 3 (§13.4 Elegibilidad): `wt_elig` / `feature/sb-eligibility` -> commit `7a76f0e` (12 passed). VERIFICADO.
- Agente 4 (§13.5 Integración): `wt_int` / `feature/sb-integration` -> commit `c4ee47a` (17 passed). VERIFICADO.

**Integración:** los 3 agentes editaron el mismo `setup_builder.py` en worktrees distintos.
Fusion manual en `wt_integrate` / `feature/sb-integrate` (modelo + `build_setup` + `classify_eligibility` + `build_setups_at`), commit `1385222`.

**Verificación final (rama principal):**
- `pytest tests/` -> **290 passed, 0 failed, 0 warnings** (era 253 antes).
- 4 test files de Setup Builder: 37 passed combinados.
- `engine/setup_builder.py` con `SetupEligibility`, `Setup`, `build_setup` (§13.3), `classify_eligibility` (§13.4), `build_setups_at` (§13.5).

**Promoción:** merge `--no-ff` a `codex/audit-hermes-cert-20260826` -> commit `8ed647f`. **SIN PUSH** (regla AGENTS.md).

**Worktrees limpiados:** `wt_model`, `wt_sep`, `wt_elig`, `wt_int`, `wt_integrate` removidos tras promoción.

### Siguiente paso
Capa de Episodes / funnel (siguiente eslabón del orden congelado). Setup Builder ya entrega SETUPs deterministas y elegibles; el funnel selecciona y agrupa en episodios para el dataset.
