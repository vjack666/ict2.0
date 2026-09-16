# M15 AI Shadow Funnel + Diagnostic Backtest

**Fecha:** 2026-09-15  
**Estado:** ejecutado como diagnostico sombra  
**Trading:** `can_trade=false`

## Objetivo

Construir funnel y backtest diagnostico con neuronas en sombra para comparar
motor solo contra motor + IA, sin activar ejecucion ni produccion.

## Implementacion

- Script:
  `scripts/lab/experiments/build_m15_ai_shadow_funnel_backtest_v1.py`
- Contrato:
  `docs/contratos/M15_AI_SHADOW_FUNNEL_BACKTEST_V1.md`
- Reporte:
  `reports/audits/experiments/ai/m15_ai_shadow_funnel_backtest_v1.md`
- JSON:
  `reports/audits/experiments/ai/m15_ai_shadow_funnel_backtest_v1.json`
- Imagenes:
  - `reports/audits/experiments/ai/m15_ai_shadow_funnel_v1.png`
  - `reports/audits/experiments/ai/m15_ai_shadow_backtest_v1.png`
  - `reports/audits/experiments/ai/m15_ai_shadow_confusion_v1.png`

## Regla

`prediccion != failure` deja pasar un candidato diagnostico. `prediccion ==
failure` lo evita. La IA no modifica el motor ni publica snapshot operable.

## Limites

Es backtest diagnostico, no economico. No contiene spread, slippage, comision,
fill, SL/TP, PnL ni certificacion de sesion broker.

## Siguiente accion

Si el diagnostico pasa, abrir backtest economico controlado con contrato de
costes/fill/sesion congelado. Si falla, redisenar solo con TRAIN/VALIDATION.
