# D2/D5 — auditoría de displacement ausente en V2 Q1

Fecha: 2026-09-06. Estado: COMPLETED_DIAGNOSTIC_ONLY.

## Hallazgo reproducible

El detector no estaba vacío. Sobre EURUSD M15 Q1 2022, `build_features` marca
115 displacement alcistas y 123 bajistas. El replay V2 previo pedía solamente
M15/M5/M1. Al no recibir H1/H4, `run_visual_replay` usaba M15 como HTF efectivo.
Ese sesgo cambia de vela a vela: el escenario se invalidaba por cambio de
dirección antes de leer el displacement siguiente.

No se modificó el umbral del detector ni se añadieron señales sintéticas.

## Corrección

`scripts/export_visual_backtest.py` incorpora `--htf-timeframe` (H4 por
defecto) y `--execution-timeframe` (M5). Ambos timeframes se añaden al conjunto
cargado incluso si el usuario limita `--tfs`. Así una ejecución M15/M5/M1 ya no
degrada silenciosamente el contexto HTF a M15.

## Evidencia

- Antes: 123 sweeps, 0 displacement, 0 BOS, 0 entradas; contexto HTF=M15.
- Después, mismo rango y argumentos M15/M5/M1: HTF=H4, 237 sweeps,
  27 displacement, 19 BOS, 18 señales/trades diagnósticos.
- Funnel posterior: 18 episodios, 0 rechazos. Permanece `BLOCKED` solo porque
  no existe prueba FULL/PREFIX independiente; no se promovió ni entrenó.
- Tests: 19 focales de exportador, espera, replay, funnel y visual backtest PASS.

## Artefactos

- `reports/audits/experiments/ai/v2_displacement_fixed_q1_backtest.json`
- `reports/audits/experiments/ai/v2_displacement_fixed_q1_funnel.json`

## Límites

`can_trade=false`, diagnóstico local, sin promoción ni push. Este arreglo
restaura la cadena causal; no prueba edge, rentabilidad ni calidad OOS.
