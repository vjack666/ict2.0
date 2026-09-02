# PROXY_PILOT — corrida de humo técnica

**Fecha:** 2026-09-02  
**Alcance:** LOCAL_ONLY; preparación técnica, no certificación de edge.

## Resultado

El motor causal ejecutó correctamente un tramo corto del protocolo sobre los
datos locales disponibles: **960 velas M15**, **1.033 eventos estructurales**,
**3 señales** y **3 registros técnicos de trade**. Las fases observadas fueron
`SWEEP`, `DISPLACE`, `BOS` y `ENTRY`.

## Configuración usada

- Símbolo: EURUSD.
- Ventana de humo: 2022-01-01 a 2022-01-15 UTC.
- Contexto: D1/H1/H4; ejecución principal M15.
- Horizonte técnico: 12 velas M15.
- Tie policy: `pessimistic`.
- Fuente local: `data/raw/EURUSD/*.parquet`.
- Terminal documentado: MetaQuotes-Demo en `C:\Program Files\FundedNext MT5 Terminal\terminal64.exe`.

## Interpretación y límites

Esta corrida demuestra que el adaptador causal puede producir señales y
registros técnicos con el dataset local. No demuestra rentabilidad ni edge:
todavía no incorpora en este artefacto el cálculo económico completo del
escenario `PROXY_PILOT` (spread 1 pip, slippage 0.3 pip, comisión US$5 por lote
por lado), ni prueba de robustez por periodos, ni validación de procedencia.
El terminal MetaQuotes-Demo es un proxy y no una cuenta FundedNext.

**Gate:** `REVIEW` técnico de preparación; el SDD global de edge permanece
`BLOCKED` hasta cerrar el runner económico reproducible, sus manifiestos y la
auditoría de datos/procedencia. `can_trade=false` y `can_train=false`.
