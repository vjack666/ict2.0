# Bitácora — Auditoría A0–A9 + Funnel FVG/OB 20Y

**Fecha:** 2026-08-18 16:05 UTC-5  
**Autor:** Hermes  
**Data:** Dukascopy EURUSD H1/H4/D1 2006-01-01 → 2025-12-31 (20 años)

## Trabajo
1. Descargados 20Y H1/H4/D1 (dukascopy-node).
2. Limpieza A0: 13 barras H1 + 4 H4 OHLC inválidas.
3. Stack A0–A9 contractual: PASS global.
4. Funnel FVG/OB real 20Y: H1 22478 FVG / 2799 OB; densidades estables.
5. Confluencia no auditada (sin regla formal).
6. Decisión: no re-ejecutar funnel sin cambio de motor.

## Artefactos
- docs/AUDITORIA_A0_A9_FVG_OB_20Y.md
- reports/audits/data/A0_A9_audit_stack.json
- reports/audits/data/A0_real_20Y.json
- reports/audits/experiments/fvg_ob/fvg_ob_funnel.json

## Veredicto
PASS CON RESTRICCIONES. Evidencia local 20Y sólida. CI del Director sigue pendiente.
