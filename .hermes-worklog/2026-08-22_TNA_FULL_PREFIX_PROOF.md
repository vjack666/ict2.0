# TNA behavioral/full-span — prueba FULL-vs-PREFIX

**AGENTE:** Codex — Auditor de reproducibilidad  
**DEPARTAMENTO:** D5 — Risk & Assurance  
**TAREA:** Demostrar que TNA/AHF conserva el mismo `MarketState` y decisión point-in-time en FULL y PREFIX.  
**STATUS:** PASS — equivalencia temporal FULL/PREFIX demostrada por inducción de capas y metadata raw/clean reconciliada.

## Cambios causales

- `engine/mtf_navigation.py::_causal_swings` publica el pivot en `confirmation_bar`, no en la barra de formación.
- `engine/sequential_events.py::_causal_swings` aplica la misma regla.
- `engine/sequential_events.py::_build_eq_pools` congela el pool con los primeros toques confirmados y evita que swings futuros reescriban su nivel o `form_bar`.
- `scripts/diag_causal_violation.py` corta cada timeframe por timestamp y no confunde dos capas ausentes (`None`) con una diferencia.

## Evidencia

- `C:\Python314\python.exe -m pytest tests -q` → **70 passed**, 1 warning no relacionado.
- Test sintético de `MarketState` completo: todos los prefijos cubiertos por el test son idénticos FULL/PREFIX.
- Probe histórico directo con cinco decisiones (2017, 2018, 2019, 2023 y 2024) → **5 checked, 0 violations**.
- Reporte reproducible: `reports/audits/tna_full_prefix_2026-08-22.json`.
- `SHA256SUMS` coincide con los blobs Git; el hash del checkout difiere por `core.autocrlf=true` (CRLF).

## Bloqueadores históricos — resueltos

1. `metadata.json` mezclaba conteo raw con CSV limpios: corregido con `n_raw`, `n_clean`, `n` y `removed_bad_ohlc`.
2. La equivalencia full-span se demuestra por comparación streaming de todas las capas en las 124377 decisiones; no se ejecutó un backtest de performance.
3. Los CSV no se modificaron; SHA256 de los blobs Git coincide con `SHA256SUMS`.

## Veredicto

La fuga causal encontrada quedó corregida. La evidencia streaming demuestra equivalencia FULL/PREFIX por inducción de capas y, tras la fe de erratas, el gate TNA queda **PASS**. Esto no constituye promoción ni habilita por sí solo el backtest.

## Siguiente acción

Avanzar al gate `Sequence × Context` con n suficiente; mantener el backtest bloqueado hasta cerrar el resto de gates pre-backtest.

## Replay exhaustivo adicional

- `scripts/audit/tna_full_prefix_exhaustive.py` cubrió las **124377** decisiones H1.
- Validó **33198** publicaciones de swings, **1427** cadenas secuenciales y **0** fallos de cutoff temporal.
- `causal_replay=PASS`; la comparación directa continúa en **5/5** puntos y por eso `full_prefix=UNPROVEN`.
- Artefacto: `reports/audits/tna_full_prefix_exhaustive_2026-08-22.json`.
- El artefacto histórico fue bloqueado por metadata inconsistente; la metadata ya fue reconciliada en la errata posterior.

## Corrección MTF adicional

- `engine/mtf_navigation.py::_eq_pools` ahora congela los primeros toques confirmados y no permite que un swing futuro reescriba una zona histórica.
- El probe histórico directo posterior a esta corrección mantuvo **5 checked, 0 violations**.
- El replay exhaustivo regenerado mantiene `causal_replay=PASS`, con `full_prefix=UNPROVEN` hasta completar la comparación directa.

## Comparador streaming FULL/PREFIX

- `scripts/audit/tna_streaming_prefix_compare.py` procesa cada timeframe una sola vez en el lado PREFIX.
- Cobertura: **124377/124377** decisiones H1, **0** divergencias de `LayerSnapshot`.
- Puntos de control exactos de `MarketState.to_dict()`: **7/7** iguales.
- Reporte: `reports/audits/tna_streaming_prefix_2026-08-22.json`.
- Resultado del cierre streaming: `full_prefix=PASS_BY_LAYER_INDUCTION`; `gate=PASS` con `metadata_count_field=n_clean`.
- Verificación exacta adicional: 9/9 secuencias de swings/zonas idénticas y 7/7 `MarketState.to_dict()` iguales en puntos de control.
- Regresión final: **72 passed**, 1 warning Pandas no relacionado.

## Cierre operativo de sincronización — 2026-08-22

- Graphify code-only actualizado desde HEAD `d04e1e8`: **3956 nodos, 6078 aristas, 371 comunidades**; no se usó extracción semántica LLM.
- `.hermes-index.md` sincronizado con `PASS_BY_LAYER_INDUCTION` y `gate=PASS`.
- Engram actualizado en el proyecto `ict2.0` con la decisión y el límite de procedencia.
- Los artefactos de grafo y esta documentación quedan incluidos en el commit autorizado de cierre; datasets sin cambios.

## Recierre TNA tras fe de erratas — 2026-08-22

- Metadata canónica: `n_clean` = H1 124377, H4 32133, D1 6258; `n_raw` conservado como H1 124390, H4 32137, D1 6258.
- CSV sin cambios; SHA256 de los blobs Git coincide con `SHA256SUMS`.
- `C:\Python314\python.exe -m pytest tests/test_tna_streaming_prefix.py -q` → **1 passed**.
- `C:\Python314\python.exe scripts/audit/tna_streaming_prefix_compare.py` → **124377/124377**, 0 divergencias, 9/9 eventos, 7/7 estados exactos, `metadata_consistent=true`, `gate=PASS`.
- Fe de erratas: `reports/audits/2026-08-22_METADATA_ERRATA_EURUSD.md`.
