# SDD — EVOLUCIÓN DEL MOTOR ICT: FVG + ORDER BLOCKS

**Versión:** 1.1  
**Fecha de sincronización:** 2026-08-20  
**Estado:** Contrato de diseño vigente; FVG/OB y lineage estructural implementados, ejecución/backtest aún bloqueados por la pila pre-backtest.
**Fuente de verdad:** `docs/ict/SPEC_TESIS_FORMAL.md` + contratos vigentes y enmienda de eliminación de OTE.

## 1. Propósito

Diseñar una evolución del motor que convierta FVG y Order Blocks en entidades temporales y causales integradas con Swing/BOS/CHOCH, liquidez y displacement.

El diseño debe favorecer aprendizaje posterior: el dataset de señales debe conservar contexto y lineage, no solo la etiqueta final.

## 2. Modelo conceptual

```text
Market Data
   ↓
Swing / Structure
   ↓
Liquidity → Sweep
   ↓
Displacement
   ↓
BOS / CHOCH / MSS
   ↓
PD Arrays
   ├── FVG
   ├── OB
   ├── Breaker
   └── BPR
   ↓
POI / Context State
   ↓
Sequence / MTF navigation
   ↓
Retest / Execution
   ↓
SL / TP / Outcome
```

## 3. Entidades

### FVG

Campos mínimos: identidad, dirección, timeframe, creación/confirmación/tradabilidad, geometría, estado, mitigación, touch, invalidación, edad y lineage.

Detector canónico vigente: tres velas, confirmación cerrada, sin look-ahead.

### Order Block

Campos mínimos: identidad, dirección, timeframe, source candle, creación/confirmación/tradabilidad, geometría, estado, footprint/follow-through, mitigación, invalidación y lineage.

Detector canónico vigente: footprint candle + closed follow-through.

### Breaker

Debe conservar referencia al OB padre y al evento que lo invalidó. No se considera detector terminado solo por existir en `ObjectType`.

### BPR / composite POI

Debe representar relación entre componentes, no duplicarlos.

### POI

POI es un rol asignado a uno o más PD Arrays y debe conservar componentes, TF, dirección, dealing-range context, alineación HTF, displacement, freshness, quality y lineage.

## 4. Lineage

Cada objeto derivado debe poder responder qué sweep, displacement y evento estructural lo precedieron y cuándo se volvió tradable.

La relación es unidireccional respecto al tiempo histórico y auditable.

## 5. Temporalidad

Separar explícitamente:

- HTF: contexto;
- ITF: zona/estructura;
- EXEC/LTF: confirmación y timing.

Un objeto HTF no puede usar información posterior al timestamp de decisión EXEC para validar una señal histórica.

## 6. Ejecución

La ejecución futura debe poder esperar:

`structure confirmation → zone creation → zone becomes tradable → price returns → execution confirmation → entry`.

No se confunde creación de zona con ejecución.

La existencia de FVG/OB, Context State, Sequence COMPLETE o `SETUP_READY` no autoriza por sí sola una orden.

## 7. Calidad

La calidad es explicable y debe poder someterse a ablación. Features potenciales incluyen sweep, displacement, BOS/CHOCH, freshness, overlap, stacking, HTF alignment y edad/mitigación.

No se congela un peso como verdad absoluta antes de validación empírica.

## 8. Backtest y aprendizaje

Las entidades deben ser observables para medir creación, confirmación, primer toque, entrada, mitigación, invalidación, MFE, MAE y outcome R cuando exista una especificación de ejecución congelada.

El backtest permanece bloqueado hasta los gates pre-backtest/TNA definidos por el plan maestro.

## 9. Seguridad contra look-ahead

Toda función que consume datos futuros para confirmar una entidad debe producir timestamp de confirmación. La entidad no participa antes de `tradable_at`.

Tests y auditorías deben mutar/truncar el futuro y comprobar invariancia histórica.

## 10. Compatibilidad

La evolución no debe romper Swing/BOS/CHOCH existentes. El blocker histórico de pivotes BOS no causales fue corregido; cualquier cambio futuro de estructura requiere regresión explícita.

## 11. Observabilidad

Cada señal debe poder explicar, como mínimo:

`structure → liquidity → sweep → displacement → PD array → Context State → sequence/POI → retest → entry → SL → TP`.

Si una señal no puede explicar su lineage, está incompleta para aprendizaje.

## 12. Estado empírico actual

- FVG/OB strict 20Y: PASS + lineage causal.
- Funnel MTF+Sequence 20Y: PASS + gate CI.
- Sequence COMPLETE: n=3, insuficiente para declarar edge.
- Context State × Sequence: `INSUFFICIENT_N`, n=24 depth≥4 deduplicado.
- TNA trace: PASS estratificado; behavioral/full-span pendiente.
- OTE/Fibonacci: prohibidos; dealing range EQ50 only.

Estos resultados son evidencia de integridad/población, no de rentabilidad.

## 13. Setup Builder (capa de composición)

Capa de composición (no ejecución) que ensambla `Setup` ICT/SMC completos a partir de un `MarketState` histórico en T. Diseño ya implementado y verificado en `engine/setup_builder.py` + `engine/market_object.py`; NO duplica lógica de lifecycle ni de detección.

### 13.1 Propósito y alcance

- Componer setups deterministas: `context_htf → poi (ORDER_BLOCK) → refinement (FVG) → confirmation (BOS) → trigger (DISPLACEMENT)`.
- Solo lectura: NO ejecuta lifecycle, NO avanza barras, NO muta `object_state` ni `POI.meta`.
- Linaje (`used_by_setup`) vive en `POI.meta`, fijado por el caller explícito; el `Setup` lo expone de solo lectura.
- Reutiliza `MarketState` + `relate_fvg_ob` (`engine/relations.py`) + navegación MTF; no inventa ontología.

### 13.2 Modelo de datos — `Setup`

`engine/setup_builder.py::Setup` (dataclass) con campos:

- `context_htf: MarketObject | None` — contexto HTF provisto en `ctx` (D1/H4).
- `poi: MarketObject | None` — Order Block HTF (`origin_tf ∈ {D1,H4,H1}`, `Role.POI`).
- `refinement: MarketObject | None` — FVG LTF que refina al POI (`origin_tf ∈ {H1,M15,M5,M1}`, `Role.REFINEMENT`).
- `confirmation: MarketObject | None` — BOS relacionado (`ObjectType.BOS`, misma dirección).
- `trigger: MarketObject | None` — DISPLACEMENT (o FVG `Role.EXECUTION`) relacionado, misma dirección.
- `direction: int` — 1 bullish / -1 bearish / 0 undefined.
- `eligibility: SetupEligibility`, `reason: str`, `meta: dict`, `created_at`.

Serialización JSON-safe vía `to_dict` / `from_dict` (espejo de `MarketObject._normalize_meta`); no importa `backtest/`.

### 13.3 Separación `object_state` vs `setup_eligibility`

Regla de motor: `object_state` pertenece al `MarketObject` y es de SOLO LECTURA para el builder; `setup_eligibility` pertenece al `Setup` y se calcula de forma independiente. Un POI ACTIVE puede dar un setup BLOCKED si el contexto HTF no está alineado (la elegibilidad NO es un reflejo del `object_state`).

`SetupEligibility(str, Enum)`: `ELIGIBLE`, `BLOCKED`, `OUT_OF_CONTEXT`, `SUPERSEDED`.

`build_setup(...)` compone un `Setup` SIN mutar `object_state`; la elegibilidad queda BLOCKED solo si `poi.is_terminal` (INVALIDATED) o `htf_context_valid=False`.

### 13.4 Clasificación de elegibilidad — `classify_eligibility`

Punto único de clasificación (SDD §13.4); `build_setups_at` delega aquí y NO duplica. Precedencia:

1. `SUPERSEDED` — `poi.state == INVALIDATED` (POI superado por el precio).
2. `OUT_OF_CONTEXT` — `ctx is None` (no hay sesgo MTF para evaluar alineación).
3. `BLOCKED` — `_htf_aligned(ctx, direction) == False` (H3: dirección no alineada con sesgo HTF; ej. bearish bajo bullish).
4. `BLOCKED` (si `require_complete=True`) — faltan `confirmation` (BOS) o `trigger` (DISPLACEMENT) (H2: contrato de setup completo).
5. `ELIGIBLE` — `poi` y `refinement` ACTIVE y contexto alineado.

Firma: `classify_eligibility(setup, ctx, *, require_complete: bool = False) -> SetupEligibility`. NO muta los `MarketObjects` referenciados; actualiza `setup.eligibility` / `setup.reason`.

### 13.5 Integración — `build_setups_at` y snapshot histórico

`build_setups_at(ms, t, ctx, *, max_bars_apart=240) -> list[Setup]`:

- Consume `ms.projection_at(t)` — snapshot histórico congelado en T (proyecciones event-sourced, causal / forward-PIT). **NUNCA** `ms.active()` del presente, que miraría el futuro (look-ahead). El filtro `state == ACTIVE` se evalúa DENTRO del snapshot.
- Para cada par `(OB HTF ACTIVE, FVG LTF ACTIVE)` que satisface `relate_fvg_ob(causal_mode="strict", same_direction=True)`, ensambla un `Setup` completo y busca `confirmation` / `trigger` en el snapshot.
- Delega elegibilidad a `classify_eligibility(setup, ctx, require_complete=True)`.

Invariantes de auditoría: determinista, causal, solo lectura; no llama `lifecycle.evaluate / advance_bar / observe`.

`Role.CONFIRMATION` / `Role.TRIGGER` añadidos a `engine/market_object.py::Role` para que el snapshot histórico conserve la intención de cada objeto sin inventar ontología (H2+H3).

### 13.6 Estado de promoción

**PROMOVIDO TRAS REVISIÓN (Codex H1–H4 cerrados), sin CERTIFIED.** El diseño quedó cerrado por los gates H1 (historial causal real en MarketState), H2 (confirmation/trigger canónicos), H3 (dirección vs htf_bias) y H4 (frontera temporal LTF/HTF en lifecycle). La certificación formal queda pendiente del GO del auditor (gates de reproducibilidad/riesgo), conforme a `AGENTS.md`: un diagnóstico/revisión no es promoción. Ver `docs/INDICE_AUTORIDAD.md` (entrada "Capa de composición") y `.hermes-worklog/2026-08-28_SETUP_BUILDER_PLAN.md` (revisión Codex H1–H5).
