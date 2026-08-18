# Worklog — Sincronización SDD FVG/OB

**Fecha:** 2026-08-18  
**Tipo:** corrección documental / gobernanza  
**Estado:** COMPLETADO

## Hallazgo

`docs/SDD_FVG_OB_ARCHITECTURE_MAP.md` había quedado desactualizado respecto del estado real después de los Gates B, C y D. La implementación avanzó, pero el SDD no fue sincronizado en cada cierre de fase.

## Corrección

Se actualizó el SDD para reflejar:

- Fase A PASS.
- Fase B PASS y contrato `MarketObject` vigente.
- Fase C PASS y detectores canónicos en `engine/detectors/fvg.py` y `engine/detectors/ob.py`.
- Fase D PASS y `engine/lineage.py` con `CausalLink`, `link`, `validate_links` y `trace_setup_lineage`.
- Estado de Fase E como `READY`.
- Diferencia explícita entre OB canónico implementado y taxonomía completa de OB todavía pendiente.
- Breaker/BPR presentes en el contrato de dominio, pero no declarados como detectores terminados.
- M5 diferido.
- Archivos reales actualmente normativos y archivos legacy en transición.
- Regla de que el SDD debe actualizarse al cerrar cada fase, experimento arquitectónico o cambio de contrato relevante.

## Evidencia

- Gate B: 13 tests PASS.
- Gate C: 20 tests PASS.
- Gate D: 27 tests PASS.
- Integración de D en `main`: `19986c2684155ffa82d455863909dbbf4a6fb00a`.
- SDD sincronizado en `main`: `63930b13474b0d285332094ca6fe6742ee968658`.

## Decisión

A partir de este punto, el SDD es un **documento vivo y normativo**. Ningún cierre de fase será considerado documentalmente completo si no actualiza:

1. código/tests;
2. SDD aplicable;
3. `.hermes-index.md`;
4. `.hermes-worklog/`;
5. evidencia del Gate.

## Resultado

Corrección documental completada. El estado de arquitectura ya coincide con el estado real de `main`.
