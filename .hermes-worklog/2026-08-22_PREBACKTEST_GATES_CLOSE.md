# Worklog — Cierre de gates pre-backtest

**Fecha:** 2026-08-22  
**AGENTE:** Codex / Hermes  
**DEPARTAMENTO:** D5 CRO/Assurance + D7 Delivery/Interfaces  
**TAREA:** Cerrar la evidencia A0-A9 full-stack y congelar el contrato de ejecución, manteniendo el backtest sin ejecutar.  
**STATUS:** PASS local reproducible + CI confirmado; backtest requiere decisión explícita del cliente.

## Hechos verificados

- `C:\Python314\python.exe -m audits.codigo.run_full_stack --scope real` terminó con `status=PASS` y A0, A1, A2, A3, A4, A5, A6, A7, A8 y A9 en `PASS`.
- El stack validó el snapshot versionado Dukascopy: H1 124377 filas, H4 32133 y D1 6258; los tres SHA256 coinciden con sus blobs Git.
- TNA: 124377 decisiones, cero divergencias reportadas y verificaciones de eventos completas en `reports/audits/tna_streaming_prefix_2026-08-22.json`.
- Funnel: H1 702, H4 206 y D1 58 relaciones causales; el artefacto MTF/Sequence permanece `COMPLETE`, `sequence=PASS` y `mtf_ok_rate=1.0`.
- `C:\Python314\python.exe -m audits.codigo.run_execution_freeze` terminó con `status=PASS`; la prueba de invariancia de vela cerrada conserva `entry`, `sl`, `tp` y `rr=3.0` frente a una vela futura añadida.
- `C:\Python314\python.exe -m audits.codigo.close_pre_backtest_gates` terminó con `status=PASS` en las cuatro condiciones agregadas.
- No se ejecutaron experimentos, backtests, PnL, descargas de mercado ni jobs de laboratorio. No se modificaron datasets.
- El primer CI del cierre (`Hermes A0-A9 Audit Stack #46`) alcanzó el Funnel, pero falló al iniciar el full-stack porque el contrato `requirements.txt` no declaraba `numpy`/`pandas`; la suite CI general tenía la misma causa de entorno. Se añadió esa dependencia mínima antes de repetir CI.
- La repetición CI del commit `49702fd` pasó en A0-A9, Tests y Funnel; el run final de reconciliación `#48` sobre `27565ae` también pasó en los tres jobs.

## Inferencias y límites

- El PASS demuestra integridad, causalidad y reproducibilidad del stack; no demuestra edge, win rate ni rentabilidad.
- El freeze es válido únicamente para `EXECUTION_INTRADAY_M15_V1`: HTF H1/H4, ITF/ejecución M15, UTC y velas cerradas. M5/M1/scalping y un dataset M15 separado requieren nuevo freeze/gate de datos.
- La evidencia local quedó confirmada por `.github/workflows/20-hermes-audit-stack.yml` en la rama publicada; el workflow no ejecuta PnL ni órdenes.

## Evidencia y archivos

- `reports/audits/A0_A9_audit_stack.json`
- `reports/audits/execution_freeze_2026-08-22.json`
- `reports/audits/pre_backtest_gate_close_2026-08-22.json`
- `audits/codigo/full_stack.py`
- `audits/codigo/run_full_stack.py`
- `audits/codigo/execution_freeze.py`
- `audits/codigo/run_execution_freeze.py`
- `audits/codigo/close_pre_backtest_gates.py`
- `docs/planificacion/EXECUTION_FREEZE_2026-08-22.json`
- `.github/workflows/20-hermes-audit-stack.yml`

## Riesgos

- El workflow CI puede revelar diferencias de entorno o de resolución del snapshot que no aparecen en la ejecución local.
- El contrato M15 no cubre la capa M5/M1 ni autoriza envío de órdenes.
- `Sequence×Context` continúa en `INSUFFICIENT_N`; no es evidencia de edge.

## Siguiente acción

1. Commit y push de esta evidencia y del workflow actualizado.
2. Mantener los gates cerrados y solicitar al cliente una decisión explícita sobre un backtest limitado al perfil congelado; no ejecutar automáticamente.
