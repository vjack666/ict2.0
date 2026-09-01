# T7d — Enmienda PIT + lineage: T7d pasa técnicamente

## Estado

`COMPLETED` (técnico): T7d pasa `PASS_TECHNICAL_BLOCKED_PROVENANCE`. Todos los
gates en `true`; 4 setups completos, 4 elegibles y 4 episodios en enero de
2025. No se promueve nada (provenance bloqueado por diseño).

## Trabajo realizado

Dos enmiendas preregistradas e implementadas para destrabar T7d:

### 1. Enmienda PIT (vela de confirmación no transiciona su objeto)

- **Causa raíz**: `_bar_after_tradable` en `engine/lifecycle.py` usaba
  `bar_time >= tradable_time`. Como `tradable_time` es el timestamp de la vela
  de CONFIRMACIÓN y esa vela se observa exactamente en ese timestamp, `>=` la
  dejaba pasar y el objeto era evaluado contra la vela que lo CREA
  (auto-mitigación): el FVG bull define `zone_low = third.low` (su tercera vela
  SIEMPRE toca la zona) y el OB se confirma con la vela de followthrough que
  recorre la zona del source candle. Resultado: ningún POI/FVG quedaba ACTIVE →
  0 setups.
- **Fix**: frontera estricta `bar_time > tradable_time` (excluye exactamente la
  vela de confirmación, la única observada en `tradable_time`).
- **Preregistro**: `docs/experimentos/EXP_MTF_REPLAY_T7D_CONFIRMATION_BAR_PREREGISTRATION.md`.
- **Test**: `test_confirmation_bar_does_not_transition_its_own_object`.

### 2. Enmienda lineage (parent_object como relación)

- **Causa raíz**: el funnel (`engine/episodes.py`) rechazaba todos los
  candidatos con `MISSING_LINEAGE`. El productor histórico v3 establece lineage
  SOLO vía `MarketObject.parent_object` (FVG/BOS/displacement cuelgan de su OB),
  pero `_related` y el BFS de alcanzabilidad solo miraban `related_objects`
  (vacío en el productor). El contrato §3 reconoce ambas fuentes.
- **Fix**: `_related` ahora acepta `parent_object` como relación; el BFS de
  alcanzabilidad transita también los hijos cuyo `parent_object` apunta al nodo
  actual.
- **Test**: `test_parent_object_lineage_accepted_without_related_objects`.

## Evidencia T7d

- Commit ejecutado: `de24d68` (el audit refleja el commit del código previo;
  el commit de esta enmienda se registra al cerrar).
- Gates: `producer_population`, `january_displacement`, `complete_setups`,
  `eligible_setups`, `episodes`, `no_pretrigger_setup`, `determinism`,
  `full_prefix`, `chunk_manifest` — todos `true`.
- Conteos enero 2025: 20 setup records, 4 completos, 4 elegibles, 4 episodios,
  6 displacement objects, 0 trades.
- Suite completa: 474 passed (472 baseline + 2 nuevos).
- Integridad mecánica: PASS; procedencia formal: `BLOCKED_PROVENANCE`.

## Decisión

T7d queda técnicamente aprobado. El siguiente paso del roadmap es auditar los
gates y verificar la población real antes de expandir el replay preregistrado
hacia el corpus causal 2006–2020.

## Riesgos

- El audit `commit` aún refleja `de24d68`; se debe commitear la enmienda y
  re-ejecutar T7d para que el artefacto apunte al código nuevo.
- No se midió edge, beneficio ni WR; no se entrenó IA; no se operó MT5.