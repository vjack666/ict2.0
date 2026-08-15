# Plan de trabajo — Rescate de autoridad de POI HTF (SDD_RESCATE_POI_HTF.md)

**Fecha:** 2026-08-07 · **Rama:** feature/backtest-ict
**Ejecuta:** OTRO agente (este archivo es plan, NO escribe código).
**Ley:** motor = fuente única; backtest desechable; 0 imports de `ict_backtest/` en `engine/`.

## Origen de los módulos (confirmado por auditoría)
- `git show HEAD:ict_backtest/htf_pd_index.py`  → rescate a `engine/htf_pd_index.py`
- `git show HEAD:ict_backtest/zone_authority.py` → rescate a `engine/zone_authority.py`
- `git show HEAD:ict_backtest/poi_anchor.py`     → DESCARTAR (acoplado a market_object)
- `git show HEAD:ict_backtest/poi_anchor_motor.py` → DESCARTAR (bonus en backtest)
- `git show HEAD:ict_backtest/poi_filter.py`     → DESCARTAR (bonus/gate en backtest)

## Pasos (DUMI, un agente los corre en orden)
1. Migrar `htf_pd_index.py` → `engine/htf_pd_index.py`
   - Importar de `detectors.fvg` / `detectors.ob` (leer firmas en detectors/fvg.py:7,
     detectors/ob.py:7). Conservar HtfPdZone, HtfPdIndex, merge_asof backward closed-only.
   - Test: build_ltf_map + zones_at anti look-ahead (zona HTF posterior a la vela LTF no aparece).
2. Migrar `zone_authority.py` → `engine/zone_authority.py`
   - Importar de `engine.htf_pd_index`. Conservar ZoneAuthority + evaluate_zone_authority.
   - Test: 0/1/3 anclas → level Baja/Media/Alta, confidence_weight en [0,1].
3. Enriquecer `engine/htf_narrative.py::build_htf_narrative`
   - Construir HtfPdIndex desde htf_frames; añadir `poi["authority"]` (tier/stacking/peso/level)
     sin tocar el gate (poi_present sigue bonus, fail-open controlado).
   - Regresión cero en `app_observador/core/engine.py` (lee anchored + authority).
4. Verificación por OJO (Ruben): observador/render D1 muestra nivel de autoridad POI.
5. Tests: `tests/test_engine_htf_pd_index.py`, `tests/test_engine_zone_authority.py`.

## Restricciones
- NO gate duro de POI (tesis 21 §4 + auditoría Fase E: PF 0.900 vs 1.511).
- NO reimplantar anchor_objects (cadena causal objeto-por-objeto).
- NO tocar lógica de decisión del backtest.
- py_compile limpio en cada archivo tocado; no romper tests motor existentes.

## Verificación final esperada
Motor mide autoridad de POI (Alta/Media/Baja con peso) en lugar de solo booleano binario
fail-open. Backtest lo consume como bonus. Sin violar la Ley.
