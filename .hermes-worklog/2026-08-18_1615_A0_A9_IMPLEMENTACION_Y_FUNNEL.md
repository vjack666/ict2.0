# Worklog — A0→A9 + Funnel FVG/OB

**Fecha:** 2026-08-18
**Estado:** IMPLEMENTACIÓN COMPLETA / EJECUCIÓN CI PENDIENTE

## Trabajo

Se implementó una secuencia ejecutable A0→A9 en `audits/codigo/audit_stack.py` y un runner reproducible en `audits/codigo/run_full_stack.py`.

También se añadió `audits/codigo/fvg_ob_funnel.py`, que descarga EURUSD H1/H4/D1 desde `ejtraderLabs/historical-data`, normaliza escala, ejecuta los detectores canónicos FVG y OB y produce `reports/audits/fvg_ob_funnel.json`.

## Auditorías

A0 Data Integrity — implementado.
A1 Schema — implementado.
A2 Point-in-Time — implementado sobre contratos temporales.
A3 Semantics/Contract — implementado.
A4 Detector/Metamorphic — implementado.
A5 Cross-Timeframe — implementado contractualmente.
A6 Lineage/Causal — implementado contra `CausalLink`.
A7 Funnel — engine + runner real FVG/OB.
A8 Coverage/Regime — implementado.
A9 Governance — implementado.

## CI

Se añadió `.github/workflows/hermes-audit-stack.yml` para ejecutar en un runner Ubuntu:

1. setup Python;
2. A0→A9;
3. tests del subsistema;
4. Funnel real FVG/OB H1/H4/D1;
5. artifacts de evidencia.

## Hallazgo crítico de alcance

El Funnel histórico `docs/AUDITORIA_FUNNEL_EURUSD_H1_H4_D1.md` es un funnel de estructura CHOCH/BOS y explícitamente indica que FVG/OB estaban fuera de alcance. Por ello no se reutiliza como si fuera evidencia de FVG/OB. El nuevo runner ejecuta FVG/OB directamente.

## Evidencia y limitación

No se declara PASS del stack en este momento porque el entorno de la sesión no puede clonar/ejecutar el repositorio y la integración GitHub disponible no expone un disparador/ejecución de workflow nueva para este commit. `get_commit_combined_status` no muestra checks todavía. No se inventa un resultado.

## Próximo gate

Ejecutar `.github/workflows/hermes-audit-stack.yml` en GitHub Actions. Si falla, corregir y repetir. Sólo con el run verde se puede marcar A0-A9 PASS y cerrar este ciclo.
