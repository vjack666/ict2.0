# SDD — Rescate de la autoridad de POI HTF del backtest al motor (Brecha B, tesis 21 §4)

**Fecha:** 2026-08-07
**Autor:** Hermes (agente) — bajo revisión de Ruben (arquitecto)
**Estado:** SDD de diseño. NO implementado. El código lo ejecuta otro agente.
**Ley respetada:** el motor (`engine/`) es la única fuente de decisión; el backtest
(`ict_backtest/`) solo consume y es desechable. `engine/` NUNCA importa `ict_backtest/`.

---

## 0. Contexto y problema

El 2026-08-05 se borraron 5 módulos de `ict_backtest/` relacionados con POI anclado
HTF: `poi_anchor.py`, `poi_anchor_motor.py`, `poi_filter.py`, `zone_authority.py`,
`htf_pd_index.py`. Razón: estaban acoplados a `ict_backtest.market_object` y vivían en
la capa desechable, violando la Ley Fundamental (motor = fuente única).

Auditoría de viabilidad (2026-08-07, lectura de `git show HEAD:ict_backtest/<f>`):

- Los 5 módulos se importan entre sí; base = `htf_pd_index.py`.
- Solo `poi_anchor.py` (borrado) importaba `ict_backtest.market_object` (el acoplamiento
  prohibido). `poi_filter.py` y `poi_anchor_motor.py` importaban `ict_backtest.htf_pd_index`
  y vivían en el backtest (capa desechable) → correcto borrarlos.
- `htf_pd_index.py` y `zone_authority.py` NO importan nada de `ict_backtest/`: usan
  `detectors.fvg.detect_fvg` + `detectors.ob.detect_order_blocks` (ambos EXISTEN en
  `detectors/`, son del motor) + `pandas`. Son lógica de dominio pura y rescatable.

**Problema de medición que existe HOY en el motor:** `engine/poi_anchor.py::poi_present`
(lines 127-140) es binario y grueso:
- No mira si la zona LTF es un FVG/OB real (solo pregunta "¿hay BOS/CHOCH padre en mi
  dirección y ya cerrado?").
- No distingue tier (T1 BPR > T2 FVG/OB > T3 rejection), no mide stacking, no da peso.
- **Fail-open**: si no hay eventos padre, devuelve `True` (permiso silencioso en símbolos
  con HTF pobre) — `engine/poi_anchor.py:116`.

Esto hace que la "medición de POI" del motor sea un proxy pobre de la autoridad ICT que
la tesis 21 §4 describe (POI respaldado por PD array del HTF, con apilado de capas).

## 1. Decisión de rescate (qué se trae y qué se descarta)

| Módulo borrado | Destino | Motivo |
|---|---|---|
| `htf_pd_index.py` (212 ln) | **RESCATAR → `engine/htf_pd_index.py`** | Lógica pura, depende de `detectors/` (existentes). Construye índice temporal O(n) de PD arrays HTF vigentes, merge_asof closed-only anti look-ahead. |
| `zone_authority.py` (103 ln) | **RESCATAR → `engine/zone_authority.py`** | Calcula autoridad contextual (tier/stacking/confidence_weight/level), determinista, sin indicadores. Es exactamente la "medición de POI" que falta. |
| `poi_anchor.py` (borrado, 88 ln) | **DESCARTAR** | Acplado a `ict_backtest.market_object`; su semántica (anchor_objects marca objeto-por-objeto) ya la cubre de forma más limpia `engine/poi_anchor.py` actual. No reimplantar. |
| `poi_anchor_motor.py` (45 ln) | **DESCARTAR** | Cableado bonus en el backtest. Duplica `engine.poi_anchor.poi_present`. |
| `poi_filter.py` (74 ln) | **DESCARTAR** | Cableado bonus en el backtest (`htf_poi_fn` as_gate). Viola Ley (vive en backtest). El motor ya tiene su hook. |

Consecuencia: se traen SOLO los 2 módulos de percepción (`htf_pd_index`, `zone_authority`)
y se reencausa su import de `ict_backtest.<x>` a `detectors.<x>` / `engine.<x>`. El
backtest, si quiere seguir enriqueciendo su scoring, los IMPORTA del motor (consumidor),
nunca al revés.

## 2. Contrato de los módulos rescatados (lo que debe cumplir el implementador)

### 2.1 `engine/htf_pd_index.py` (migración de `ict_backtest/htf_pd_index.py`)
- Reemplazar `from ict_backtest.market_object import ...` por nada (no lo usa).
- `from detectors.fvg import detect_fvg` + `from detectors.ob import detect_order_blocks`
  (ya existen; verificar firma en `detectors/fvg.py:7` y `detectors/ob.py:7`).
- Conservar: `HtfPdZone` (dataclass), `HtfPdIndex` (build_ltf_map + zones_at O(1)),
  merge_asof **backward** (closed-only anti look-ahead, ya documentado y correcto).
- Conservar el forward-fill de estado "vivo" de la zona HTF (act_*_on hasta invalidación/
  fill) — esto es lo que `engine/poi_anchor.py` actual NO tiene y es la mejora clave.
- NUNCA importa `ict_backtest/`. NUNCA decide dirección/entry/SL/TP (solo percepción).

### 2.2 `engine/zone_authority.py` (migración de `ict_backtest/zone_authority.py`)
- Reemplazar `from ict_backtest.htf_pd_index import HtfPdZone` por
  `from engine.htf_pd_index import HtfPdZone`.
- Conservar `ZoneAuthority` (dataclass: has_htf_anchor, tier, stacking_level,
  confidence_weight, level) y `evaluate_zone_authority(ltf_zone, htf_zones)`.
- Conservar pesos deterministas (base 0.5 + tier hasta 0.3 + stacking hasta 0.2, máx 1.0).
- Regla de hierro: es PESO DE CONFIANZA, NUNCA gate duro (R4 / auditoría Fase E: POI
  como gate duro destruye edge, PF 0.900 vs 1.511). Esto RESPETA la tesis 21 §4
  (POI = bonus) y el G2 del preflight (no revertir decisiones auditadas).

### 2.3 Integración en el motor (dónde se invoca)
- `engine/htf_narrative.py::build_htf_narrative` (hoy marca `poi["anchored"]` en
  `engine/htf_narrative.py:152` con `make_htf_poi_fn`) DEBE, tras el rescate, enriquecer
  el POI con `ZoneAuthority` (`confidence_weight`, `tier`, `level`) en lugar de solo un
  booleano `anchored`.
- `engine/sequence.py` mantiene su hook `poi_present` (bonus, NO gate) pero la fuente de
  `poi_present` puede seguir siendo `engine.poi_anchor.make_htf_poi_fn` (binario, fail-open
  controlado) O pasar a consultar `engine.zone_authority` para el scoring. Decisión del
  implementador: mantener `poi_present` binario para el hook (regresión cero) y AÑADIR el
  `confidence_weight` como metadata enriquecida, sin tocar el gate (G3: no tocar el gate).

## 3. Qué NO se hace (límites del SDD)
- NO se convierte POI en gate duro (T8 queda como bonus, respeta auditoría Fase E y G2/G3).
- NO se reimplanta `anchor_objects` (cadena causal objeto-por-objeto): el motor actual no
  usa `MarketObject` en la capa de POI; rehacer eso es alcance distinto y riesgoso.
- NO se toca `engine/poi_anchor.py` más allá de permitir el enriquecimiento metadata.
- NO se mueve lógica de decisión al backtest.

## 4. Plan de trabajo (ejecuta OTRO agente, no este SDD)

Paso 1 — Crear `engine/htf_pd_index.py` migrando `git show HEAD:ict_backtest/htf_pd_index.py`:
  - Reencausar imports a `detectors.fvg` / `detectors.ob`.
  - `py_compile` + 1 test unitario: construir HtfPdIndex con frames D1/H4/H1 sintéticos,
    `build_ltf_map` sobre un LTF, `zones_at` devuelve la zona vigente correcta (anti
    look-ahead: una zona HTF que cierra DESPUÉS de la vela LTF no aparece).

Paso 2 — Crear `engine/zone_authority.py` migrando `git show HEAD:ict_backtest/zone_authority.py`:
  - Reencausar import a `engine.htf_pd_index`.
  - Test unitario: `evaluate_zone_authority` con zona LTF + 0/1/3 anclas HTF devuelve
    `level` Baja/Media/Alta y `confidence_weight` en [0,1].

Paso 3 — Enriquecer `engine/htf_narrative.py::build_htf_narrative`:
  - Construir `HtfPdIndex` desde los `htf_frames` ya cargados.
  - Para el POI del LTF, llamar `evaluate_zone_authority` y añadir
    `poi["authority"] = {tier, stacking, confidence_weight, level}` además de `anchored`.
  - Regresión cero en el observador (`app_observador/core/engine.py` debe seguir leyendo
    `poi.get("anchored")` y ahora también `poi.get("authority")`).

Paso 4 — Verificación por OJO (Ruben): el observador / un render D1 muestra ahora el
  nivel de autoridad del POI (Alta/Media/Baja) junto al booleano anclado, para que lo
  juzgues contra tu imagen de TradingView.

Paso 5 — Tests: añadir `tests/test_engine_htf_pd_index.py` y
  `tests/test_engine_zone_authority.py`. No romper los tests motor existentes.

## 5. Riesgos y mitigaciones
- `detectors.fvg` / `detectors.ob` pueden tener firma distinta a la asumida en el código
  borrado → el implementador debe leer `detectors/fvg.py:7` y `detectors/ob.py:7` y adaptar
  el llamado (no reimplementar los detectores).
- `merge_asof` exige dtype de tiempo idéntico en ambos extremos → ya normalizado a
  `datetime64[us, UTC]` en el original; conservarlo.
- El `engine/poi_anchor.py` actual y `engine/htf_pd_index.py` ambos definen índices HTF:
  el implementador debe decidir si `engine/poi_anchor` reusa `engine.htf_pd_index` para
  evitar doble cómputo (recomendado: `poi_present` puede quedar como shortcut sobre
  `HtfPdIndex`, pero manteniendo el fail-open controlado para el hook).

## 6. Criterio de done
- `engine/htf_pd_index.py` y `engine/zone_authority.py` existen, importan solo de
  `detectors/` y `engine/` (0 imports de `ict_backtest/`), `py_compile` limpio.
- El motor enriquece el POI con `authority` (tier/stacking/peso) SIN convertirlo en gate.
- Tests nuevos pasan; observador sigue funcionando (regresión cero).
- El backtest, si lo usa, lo importa del motor (consumidor), no al revés.
