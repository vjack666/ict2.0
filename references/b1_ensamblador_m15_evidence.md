# Ensamblador M15 Evidence — Aprendizaje de sesión

> **Nota:** Este archivo documenta lo que se descubrió y verificó en la sesión
> 2026-09-11 sobre el ensamblador de evidencia M15 para el corpus B1.
> Es una referencia técnica, no una habilidad persistente.
> Para adoptarlo como skill, usar: `hermes curator adopt b1-canonico-corpus-autoreparacion-v1`

## Resumen

Se creó `engine/m15_evidence_assembler.py` que produce los 5 campos de
evidencia M15 que exige el evaluador canónico. Combina:

- `engine.historical_event_objects.build_historical_event_objects` — BOS, displacement, FVG/OB
- `detectors.liquidity_context.canonical_sweep` — SWEEP
- `_check_retest` interno — retest

## Estado de verificación

| Verificación | Resultado |
|--------------|-----------|
| Tests sintéticos (7 tests) | ✅ PASS |
| Smoke test 100 DT reales (2022-2025) | ✅ PASS |
| Informe final | `reports/b1/AUTOREPARACION_CICLO_1_FINAL.json` → PASS |
| Corpus hash | `6cb73ac5c6aa89e95b2c01d32aa822` |

## Pitfall crítico — Normalización de timestamp

**Problema encontrado:** Los parquets de M15/H1/H4/D1 usan columna `\"time\"`
(nombre diferente a `\"timestamp\"`). Si se normaliza `timestamp` DESPUÉS de
recortar el dataframe, el dataframe recortado pierde la columna `timestamp`
y el ensamblador falla con `KeyError: 'timestamp'`.

**Solución:** Normalizar `timestamp` desde `time` en el dataframe COMPLETO
antes de cualquier recorte:

```python
m15['timestamp'] = pd.to_datetime(m15['time'], utc=True, errors='coerce')
m15_before = m15.loc[m15['timestamp'] <= decision_time].copy()
```

No usar `m15['time'] <= decision_time` para recortar y luego intentar
acceder a `timestamp` — el recorte con `time` deja sin la columna `timestamp`
normalizada.

## Verificación local

```bash
.venv/Scripts/python.exe scripts/test_assembler.py   # Tests sintéticos 7/7
.venv/Scripts/python.exe scripts/smoke_fix_v2.py      # Smoke test 100 DT
cat reports/b1/AUTOREPARacion_CICLO_1_FINAL.json | python -m json.tool
```

## Scripts generados esta sesión

- `scripts/test_assembler.py` — Tests sintéticos (7 tests)
- `scripts/smoke_fix_v2.py` — Smoke test con datos reales
- `engine/m15_evidence_assembler.py` — Ensamblador canónico (nuevo)
- `reports/b1/AUTOREPARacion_CICLO_1_FINAL.json` — Informe de ciclo PASS
- `reports/b1/OBJETIVO1_MAPA_DETECTORES.json` — Mapeo 7 detectores
- `reports/b1/OBJETIVO2_DISENIO_ENSAMBLADOR.json` — Diseño ensamblador
