# TNA behavioral/full-span — hallazgo FULL-vs-PREFIX

**Fecha:** 2026-08-22  
**Agente:** Codex — Auditor de reproducibilidad  
**Departamento:** D5 — Risk & Assurance  
**Estado:** BLOCKED — el gate full-span no puede certificarse todavía  
**Commit base:** `7e69a0c743e185de2b134852dfe5bff44bcd0286`

## Objetivo

Demostrar con evidencia reproducible si la navegación AHF/MTF conserva el mismo
estado point-in-time cuando se ejecuta sobre el dataset completo o únicamente
sobre el prefijo disponible hasta la barra de decisión.

## Evidencia ejecutada

- `C:\Python314\python.exe -m pytest tests\test_mtf_navigation.py tests\test_ahf.py tests\test_sequential_events.py -q`
  → **12 passed**.
- `C:\Python314\python.exe -m pytest tests\test_phase_c_detectors.py tests\test_fvg_ob_relations.py tests\test_audit_subsystem.py tests\test_audit_stack.py -q`
  → **20 passed**.
- Probe independiente sobre diez series sintéticas de `run_sequential(return_history=True)`:
  `depth_by_bar` y `complete_by_bar` FULL-vs-PREFIX → **10/10 sin violaciones**.
- Probe independiente sobre `MTFNavigator` con cinco series sintéticas y 350
  decisiones → **348 iguales, 2 divergencias**.
- La primera divergencia reproducida aparece en la barra 79: la ejecución full
  contiene una zona `SSL/EQL` con `bar_index=79`; el prefijo no la contiene.
- Monkey-patch temporal, sin editar archivos, publicando el swing en su barra
  de confirmación `conf` → **350/350 comparaciones iguales**.

## Causa técnica

`engine/mtf_navigation.py::_causal_swings` detecta un pivot usando barras a la
derecha hasta `conf`, pero devuelve `j` como índice del swing. El snapshot luego
filtra por `j <= asof_bar`. Eso permite que una ejecución full publique en una
decisión un pivot cuya confirmación ocurrió después de esa decisión.

El patrón causal correcto ya existe en `detectors/bos.py`: publica el pivot en
la barra de confirmación y mantiene separada la formación del pivot.

## Alcance de los artefactos existentes

`reports/audits/temporal/tna_20y.json` registra 124.377 barras, zero
`asof_violations` y estado `OK` en todas las barras, pero no ejecuta la
equivalencia FULL-vs-PREFIX estricta del `MTFNavigator` completo. Por tanto,
ese PASS es evidencia auxiliar, no cierre del gate normativo.

## Bloqueadores

1. La implementación actual tiene una divergencia FULL-vs-PREFIX reproducible.
2. El snapshot CSV no coincide con `datasets/eurusd_dukascopy_20y/SHA256SUMS`.
3. `metadata.json` declara H1=124.390 mientras el CSV contiene 124.377 filas.
4. No existe todavía un artefacto AHF canónico full-span certificado.

## Veredicto

**No demostrado / no promovible:** el gate TNA behavioral/full-span no pasa en
el estado actual. Sí queda demostrada la causa y una corrección candidata en
memoria, pero no se aplicó al repositorio ni se ejecutó la corrida de 20 años.

## Siguiente acción

Aplicar una corrección revisada que conserve `formation_bar` y `confirmation_bar`,
añadir un test estricto FULL-vs-PREFIX para `MTFNavigator`, verificar todos los
tests y solo después resolver la procedencia del snapshot y ejecutar el runner
AHF full-span autorizado.

## Archivos relevantes

- `engine/mtf_navigation.py`
- `detectors/bos.py`
- `tests/test_mtf_navigation.py`
- `tests/test_sequential_events.py`
- `scripts/audit/tna_audit_runner.py`
- `reports/audits/temporal/tna_20y.json`
- `audits/PLAN_AUDITORIA_TEMPORAL_AHF.md`
