# Setup Grammar NO_ZONE Audit v1

**Fecha:** 2026-09-16
**Estado:** `REVIEW`
**Politica:** `can_trade=false`

## Objetivo

Auditar si las filas `NO_ZONE` del dataset de gramatica son una lectura valida
o si el sistema esta tratando como "no hay zona" casos donde podria existir
una zona ICT real. No se inventan zonas ni se relabela el dataset.

## Tesis usada

- `docs/ict/21_POI.md`: POI valido = PD Array (OB/FVG/BPR/etc.) en contexto
  correcto, con sesgo, zona premium/discount y respaldo institucional.
- `docs/ict/18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`: HTF da sesgo, ITF marca
  zona y exec TF dispara.
- `docs/contratos/SETUP_GRAMMAR_SUPERVISION_V1.md`: la red debe aprender si
  FVG/OB es zona usable y si el precio retorna a esa zona.

## Resultado

- Total filas del dataset: `292`.
- `NO_ZONE`: `73` (`25.00%`).
- Distribucion: TRAIN `30`, VALIDATION `24`, TEST_OOS `19`.
- Contradicciones contra secuencia fuente: `0`.
- Todas las filas `NO_ZONE` tienen secuencia fuente:
  `LIQUIDITY_POOL -> SWEEP -> DISPLACEMENT -> STRUCTURE`.
- Todas las filas `NO_ZONE` tienen geometria M15 direccional reciente segun
  auditoria local.
- Todas las filas `NO_ZONE` desarrollan zona mas tarde en la misma cadena, pero
  eso es futuro respecto a la decision y no puede usarse para relabel causal.

## Dictamen

`NO_ZONE` no parece error directo contra la fuente H1, pero si es una zona de
riesgo metodologico: la tesis exige mirar ITF/M15 para zona, y el auditor
encuentra geometria M15 direccional en las 73 filas. No se debe convertir eso
automaticamente en zona valida, porque la tesis exige contexto, sesgo,
premium/discount y respaldo institucional. Estado: `REVIEW`.

## Archivos

- `scripts/lab/experiments/audit_no_zone_setup_grammar_v1.py`
- `reports/audits/experiments/ai/setup_grammar_no_zone_audit_v1.md`
- `reports/audits/experiments/ai/setup_grammar_no_zone_audit_v1.json`

## Siguiente accion

Crear `SETUP_GRAMMAR_PD_ARRAY_SEMANTIC_V1`: materializar PD Arrays M15/ITF
semanticos, con zona premium/discount, direccion, tier, ancla narrativa,
estado lifecycle y retest causal. Solo despues comparar contra `NO_ZONE`.
