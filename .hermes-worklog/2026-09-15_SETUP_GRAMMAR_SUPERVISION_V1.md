# Setup Grammar Supervision v1

**Fecha:** 2026-09-15  
**Estado:** `READY_FOR_MATERIALIZATION_DESIGN`  
**Politica:** `can_trade=false`

## Objetivo

Responder a la observacion del usuario: las neuronas no estan construyendo
setups adecuadamente. Se abre una linea para entrenarlas con la tesis local.

## Fuentes leidas

- `docs/ict/20_TESIS_ICT.md`
- `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`
- `docs/ict/21_POI.md`
- `docs/reglas/ICT_RULEBOOK.md`
- `docs/tesis/SDD_SEQUENCE_EVENT_WAIT.md`
- `docs/tesis/SDD_LTF_ENTRY_LAYER.md`
- `reports/b1/OBJETIVO2_DISENIO_ENSAMBLADOR.json`

## Entrega

- Contrato: `docs/contratos/SETUP_GRAMMAR_SUPERVISION_V1.md`
- Plan: `docs/planificacion/PLAN_SETUP_GRAMMAR_SUPERVISION_V1.md`
- Reporte: `reports/audits/experiments/ai/setup_grammar_supervision_v1.md`
- JSON: `reports/audits/experiments/ai/setup_grammar_supervision_v1.json`

## Decision

La siguiente mejora no es hacer la red mas grande, sino ensenarle la gramatica
del setup: HTF, PO3, sweep, displacement, BOS/CHOCH, zona, retest, POI,
exec TF y decision PASS/WAIT/ABSTAIN/REJECT.

## Investigacion pendiente

- Killzones London/NY con timezone exacta.
- M3 como exec TF.
- Breaker/Mitigation/BPR como PD Arrays entrenables.

No se usaron fuentes externas en esta fase; los huecos quedaron marcados como
`RESEARCH_REQUIRED`.

## Siguiente accion

Materializar `SETUP_GRAMMAR_DATASET_V1` y entrenar `setup_quality_v1` en modo
sombra.
