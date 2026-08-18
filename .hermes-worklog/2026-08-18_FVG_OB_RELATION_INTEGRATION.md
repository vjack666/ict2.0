# Worklog — Integración FVG ↔ OB

**Fecha:** 2026-08-18
**Estado:** IMPLEMENTADO — ejecución/gate pendiente

## Objetivo

Conectar los detectores canónicos `engine/detectors/fvg.py` y `engine/detectors/ob.py` mediante una relación explícita, causal y auditable.

## Implementación

- `engine/relations.py`
  - `FVGOBRelation`
  - `relate_fvg_ob()`
  - `relation_links()`
- `tests/test_fvg_ob_relations.py`
- `docs/CONTRATO_FVG_OB_RELACION.md`
- `audits/codigo/fvg_ob_funnel.py` ahora ejecuta la relación y genera `CausalLink`.

## Regla implementada

Una relación `FVG_OB_OVERLAP` requiere:

1. FVG y OB canónicos;
2. misma dirección por defecto;
3. solapamiento de precio positivo;
4. máximo 20 barras de separación;
5. lineage temporal válido.

## Interpretación

La relación representa **confluencia de objetos**. No es todavía un setup, entrada ni evidencia de edge.

## Evidencia

El módulo y sus tests están subidos a `main`. La validación CI del cambio y el Funnel 20Y deben ejecutarse antes de cerrar el Gate de esta extensión.

## Próximo paso

Reejecutar el Funnel FVG/OB sobre 20 años, medir `relation_count`, `lineage_link_count` y distribución por TF/dirección, y evaluar la relación antes de formalizar un setup.
