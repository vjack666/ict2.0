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

## OE4–OE6 — Auditoría causal (misión T7e)

### OE4 — Auditoría causal de los 4 setups: PASS

Cada setup elegible se reconstruyó (bar→objeto→tradable_time→primera vela de
lifecycle→parent/related→BFS→setup→eligibility→episodio) y se verificó:

- **PIT**: POI y REF están `ACTIVE` en el decision_time (la vela de confirmación
  no los automitigó).
- **Lineage**: REF.parent = OB, CONF.parent = OB, TRIG.parent = OB — todos
  cuelgan del POI correcto.
- **Temporal**: TRIG (15:15) precede a CONF (15:30) — válido bajo la enmienda H6
  (evidencias hermanas).
- **Sin conexiones accidentales**: los 4 episodios comparten el POI
  (OB_H4_180_BULL) pero se distinguen por refinement (FVG_2710 vs FVG_2711) y
  decision_time (15:30 vs 15:45). 2 refinements × 2 decision_times = 4 episodios.

### OE5 — Auditoría de población (enero 2025): PASS

Funnel completo:

- Productor: 92 objetos (11 OB H4, 4 FVG M15, 71 BOS M15, 6 displacement M15).
- Setups totales: 20 → 4 completos (conf+trig), 16 incompletos.
- Incompletos: 9 sin trigger, 5 sin confirmation+trigger, 2 sin confirmation.
- Elegibles: 4 (todos los completos). Bloqueados: 0.
- Rechazos: 16× `SETUP_BLOCKED` (los incompletos). Episodios: 4. Trades: 0.

El funnel es honesto: los 16 setups incompletos se rechazan por falta de
evidencia (confirmation/trigger), no por lineage/lifecycle. No hay descartes
por lineage/lifecycle — todos los completos pasan.

### OE6 — Regresiones adversariales (PIT + lineage): PASS (9/9)

- **A. PIT**: A1 confirmación en T no transiciona, A2 primera evaluación en T+n,
  A3 vela antes de tradable no transiciona — PASS.
- **B. Lineage**: B1 parent alcanzable, B2 related_objects funciona, B3 parent
  inexistente rechazado, B4 parent cruzado rechazado, B5 ciclo rechazado,
  B6 episodios independientes no se conectan — PASS.

**Hallazgo B5**: el caso de ciclo donde el POI tiene `parent_object` apuntando a
su propio refinement (`poi.parent -> fvg`, `fvg.parent -> poi`) NO se rechazaba.
El DFS de detección de ciclos solo transita aristas salientes y trata la vuelta
como "retorno al padre" legítimo. El productor histórico v3 nunca genera este
caso (nunca setea `parent_object` en el POI), pero OE6 exige fail-closed.

**Fix**: validación 1b en `engine/episodes.py::_check_lineage` — el POI es la
raíz del árbol de lineage y NO debe tener `parent_object`; si lo tiene →
`INVALID_LINEAGE`. Commit `c99d00b`. Test de regresión
`test_lineage_poi_with_parent_rejected`.

**Verificación tras el fix**: suite completa 475 passed (474 + 1 nuevo). T7d
re-ejecutado → `PASS_TECHNICAL_BLOCKED_PROVENANCE`, counts 4/4/4/20/0, checksum
`7cee3645...` (idéntico). El fix no altera la población real.

## Decisión

T7d queda técnicamente aprobado. El siguiente paso del roadmap es auditar los
gates y verificar la población real antes de expandir el replay preregistrado
hacia el corpus causal 2006–2020.

## Riesgos

- El audit `commit` aún refleja `de24d68`; se debe commitear la enmienda y
  re-ejecutar T7d para que el artefacto apunte al código nuevo.
- No se midió edge, beneficio ni WR; no se entrenó IA; no se operó MT5.

## Publicación (push)

- **Instrucción explícita del usuario**: "push" (2026-09-01).
- **Alcance**: rama completa `codex/audit-hermes-cert-20260826` (incluye código
  del motor + evidencia). El usuario eligió "Push rama completa" sobre la
  Opción B (evidencia solo en `cert/`).
- **Push**: `af5ab85..1a02a3e` → `origin/codex/audit-hermes-cert-20260826`.
- **Commits publicados**: 12 (T7b/T7c/T7d + enmiendas PIT/lineage/H6 + OE4-OE6 +
  fix B5 `c99d00b` + worklog `1a02a3e`).
- **Verificación previa**: sin secretos en los archivos pusheados (solo falsos
  positivos: nombres npm, strings de test, tokens de lógica de negocio).
- **Excluidos del push**: `datasets/`, `data/raw/*.parquet`, `.atl/*`,
  `reports/audits/experiments/ai/*` (no relacionados, quedan sin commitear).