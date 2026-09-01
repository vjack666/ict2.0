# Agente 1 — Cierre (MODELO DE DATOS Setup Builder)

- **Branch**: `feature/sb-model` (worktree `ICT_SYSTEM_wt_model`)
- **Fecha**: 2026-08-28

## Entregado
- `engine/setup_builder.py`: modelo de datos puro.
  - `SetupEligibility(str, Enum)`: ELIGIBLE / BLOCKED / OUT_OF_CONTEXT / SUPERSEDED.
  - `Setup` (dataclass): id, symbol, direction (1/-1/0), context_htf, poi,
    refinement, confirmation, trigger (todos `Optional[MarketObject]`),
    eligibility, reason, created_at, meta.
  - `to_dict()` / `from_dict()` JSON-safe con `_normalize_meta` (set -> lista
    ordenada, espejo de `MarketObject`).
  - Propiedad `used_by_setup` de SOLO LECTURA que lee `POI.meta['used_by_setup']`;
    NO es campo propio del Setup.
- `tests/test_setup_builder_model.py`: 11 tests (eligibility, construcción,
  validación de direction, round-trip to_dict/from_dict, linaje desde POI.meta,
  invariante de NO mutación de `object_state`).

## Invariantes respetados
- No importa `backtest/`. No toca `lifecycle.py` ni `market_state.py`.
- El Setup NO altera `object_state` de ningún MarketObject (verificado por test).
- `SetupEligibility` hereda de `str` => serializa directo a JSON.

## Verificación
- `C:/Python314/python.exe -m pytest tests/test_setup_builder_model.py -q`
  => **11 passed**.

## Riesgos / notas
- `from_dict` deja `created_at` como string (no rehidrata datetime): decisión
  deliberada de modelo puro (quién compone decide parsear). Round-trip fiel
  del string.
- La validación de `direction` y coerción de `eligibility` viven en
  `__post_init__`; la lógica de composición real la implementan otros agentes.
