# Bitácora — Orden causal estricto FVG/OB

**Fecha:** 2026-08-18 16:50 UTC-5

## Cambio
- `relate_fvg_ob(..., causal_mode="strict"|"symmetric")`
- Default strict: OB antes de FVG; relation=`FVG_OB_CAUSAL`; parent=OB en CausalLink
- Tests actualizados (5 PASS)
- Contrato `docs/CONTRATO_FVG_OB_RELACION.md` actualizado
- Funnel 20Y re-ejecutado

## Evidencia empírica
H1: 2318 → 702 (−70 %); la mayoría del drop es OB-after-FVG.
