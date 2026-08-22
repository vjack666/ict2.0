# TNA behavioral/full-span — prueba FULL-vs-PREFIX

**AGENTE:** Codex — Auditor de reproducibilidad  
**DEPARTAMENTO:** D5 — Risk & Assurance  
**TAREA:** Demostrar que TNA/AHF conserva el mismo `MarketState` y decisión point-in-time en FULL y PREFIX.  
**STATUS:** BLOCKED — la corrección causal pasa las pruebas disponibles, pero falta cobertura exhaustiva y la metadata del snapshot no coincide.

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

## Bloqueadores

1. `metadata.json` declara H1=124390 y H4=32137; los CSV versionados contienen H1=124377 y H4=32133.
2. La comparación histórica ejecutada es una muestra directa, no los 124377 prefijos.
3. No se generó el trace AHF full-span sobre un snapshot con metadata consistente.

## Veredicto

La fuga causal encontrada quedó corregida y la evidencia sintética/histórica muestreada es PASS. El gate normativo permanece **BLOCKED**; no hay base para promoción ni para declarar equivalencia full-span exhaustiva.

## Siguiente acción

Resolver la metadata/procedencia sin modificar silenciosamente datasets; después ejecutar el auditor full-span autorizado y añadir el resultado exhaustivo al artefacto versionado.

## Replay exhaustivo adicional

- `scripts/audit/tna_full_prefix_exhaustive.py` cubrió las **124377** decisiones H1.
- Validó **33198** publicaciones de swings, **1427** cadenas secuenciales y **0** fallos de cutoff temporal.
- `causal_replay=PASS`; la comparación directa continúa en **5/5** puntos y por eso `full_prefix=UNPROVEN`.
- Artefacto: `reports/audits/tna_full_prefix_exhaustive_2026-08-22.json`.
- El gate continúa bloqueado por metadata inconsistente y por falta de comparación directa de cada prefijo.
