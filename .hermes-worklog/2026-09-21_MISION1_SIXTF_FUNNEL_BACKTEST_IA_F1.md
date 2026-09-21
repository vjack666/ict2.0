# Bitacora — Mision 1 seis-TF -> Funnel -> Backtest -> IA F1

**Fecha:** 2026-09-21  
**Agente:** Codex / CEO operativo  
**Departamento:** D1 documentacion, D2 ingenieria, D5 assurance  
**Estado:** `COMPLETED_DOCUMENTAL`

## Pregunta

Ruben solicito verificar si existia plan o SDD para la Mision 1 y, si no,
crearlo y completar al 100% esa fase.

## Hallazgo

Si existia base reutilizable:

- `docs/planificacion/SDD_EPISODES_FUNNEL_V1.md`
- `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`
- `docs/contratos/CONTRATO_LINEAGE_HIERARCHY_V1.md`
- PR #16 mergeado en remoto con commit `d4fdf68def1915ce29f0e3abe31e33f19eeb92ea`
- trazado HTML `reports/audits/experiments/temporal/PR16_SIXTF_LINEAGE_TRACE_20260921.html`

Faltaba el documento puente post-PR16 que declarara Mision 1 como ruta unica
hacia funnel/backtest/IA usando seis temporalidades y no H4/M15 como atajo.

## Accion realizada

Se creo:

- `docs/planificacion/SDD_MISION1_SIXTF_FUNNEL_BACKTEST_IA_V1.md`
- `.hermes/plans/2026-09-21_MISION1_SIXTF_FUNNEL_BACKTEST_IA.md`

Y se actualizo:

- `.hermes-index.md`

## Dictamen

`MISION1_PHASE1 = COMPLETED_DOCUMENTAL`.

La fase cerrada al 100% es documental/preflight: autoridad, plan, gates y
limites. No se declara implementado el backtest funnel ni entrenamiento IA.

## Riesgos

- El checkout principal sigue con cambios locales sucios ajenos.
- La rama local actual es de preservacion; no se debe hacer reset/clean.
- F2 requiere una base local segura que contenga PR16 antes de tocar codigo.

## Siguiente accion

F2: implementar o certificar el productor seis-TF hacia `engine/episodes.py`
con FULL/PREFIX literal, rechazos explicitos y suite focal.

