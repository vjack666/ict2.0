# Temporal Episode v1 — estado FASE 3 / FASE 4

**Fecha:** 2026-09-18  
**Rama:** `codex/temporal-episodes-v1-20260918`  
**Estado:** IMPLEMENTED_NOT_CERTIFIED

## FASE 3 — contrato temporal

Cerrada a nivel de código/documentación con una corrección causal adicional
detectada durante la revisión.

### Hallazgo crítico

`candidate_time` no puede equivaler universalmente a `available_at`.

Los productores canónicos FVG/OB usan `candidate_time` como ancla inicial del
patrón:

- FVG: primera vela del patrón de 3 velas;
- OB: vela footprint anterior al follow-through.

Por tanto, usar candidate_time como disponibilidad habría introducido
look-ahead.

### Política corregida

```text
available_at =
    tradable_time
    -> confirmation_time
    -> creation_time
    -> candidate_time
```

Se preservan por separado:

```text
candidate_time
confirmation_time
tradable_time
```

El contrato normativo, `engine.episodes.available_time()`,
`engine.setup_builder._obj_time()` y el SDD quedaron alineados.

## Productores auditados

- ORDER_BLOCK: productor canónico encontrado.
- FVG: productor canónico encontrado.
- BOS: productor histórico + sequence encontrados.
- DISPLACEMENT: productor histórico + sequence encontrados.
- LIQUIDITY: productor sequence encontrado; temporalidad legacy por creation.
- SWEEP: productor sequence encontrado; temporalidad legacy por creation.
- RETURN: productor sequence encontrado; temporalidad legacy por creation.
- CONTRACT: productor sequence encontrado; temporalidad legacy por creation.
- CHOCH: no productor MarketObject independiente certificado.
- BREAKER: no productor canónico certificado.
- BPR: no productor canónico/definición autoritativa certificado.

CHOCH/BREAKER/BPR permanecen `RESEARCH_REQUIRED`; no se inventa semántica.

## FASE 4 — implementación

Añadido:

`scripts/lab/experiments/mt_temporal_episode_materializer.py`

La capa:

1. consume `engine.episodes` + `MarketState.projection_at(T)`;
2. no recalcula detectores ni lifecycle;
3. conserva lineage;
4. ordena eventos por available_at y parent-depth en empates;
5. separa candidate/confirmed/tradable;
6. falla cerrado ante futuro/lineage fuera del snapshot;
7. registra Wyckoff solo si existe contexto causal;
8. mantiene trading/entrenamiento deshabilitados.

## Tests añadidos

`tests/test_temporal_episode_materializer.py`

Cobertura prevista:

- available_at consumer-safe;
- fallback legacy;
- orden parent-before-child con mismo timestamp;
- order reversal;
- future candidate fail-closed;
- FULL/PREFIX;
- future injection invariance;
- Wyckoff missing explícito;
- Wyckoff preservado cuando se provee;
- FVG no disponible en primera vela ancla;
- OB espera follow-through;
- setup_builder usa tradable_time para orden operativo.

## Limitación actual de certificación

GitHub Actions no registra ejecuciones para la rama/PR en este repositorio.
Por eso esta entrega NO declara tests PASS.

```text
FASE_3 = IMPLEMENTED
FASE_4 = IMPLEMENTED
TEST_EXECUTION = PENDING
READY_FOR_TEMPORAL_BASELINE = NO
READY_FOR_GRU = NO
READY_FOR_DEMO = NO
can_trade = false
entry_authorized = false
```

El siguiente paso es ejecutar los tests focales y el piloto real de 20–50
episodios con datos locales/read-only, corregir cualquier gate fallido y solo
entonces certificar FASE 4.
