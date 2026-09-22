# Contrato — Backtest forense six-TF v1

**Estado:** NORMATIVO PARA MISIÓN 5
**Fecha:** 2026-09-22
**Autoridad:** `engine/episodes.py` produce episodios; `backtest/` solo consume y audita.

## Propósito

Auditar episodios six-TF antes de usarlos para calibración económica o IA
shadow. El objetivo es detectar trampas de motor/proceso: etapas comprimidas en
una vela, tiempos futuros, padres HTF no cerrados y pérdida de secuencia.

## Límites

- No autoriza trading, señales, MT5 ni órdenes.
- No modifica datos crudos ni fabrica cobertura M1.
- `engine/` no importa `backtest/`.
- IA solo clasifica evidencia para análisis: `ACEPTAR_ANALISIS`,
  `RECHAZAR_ANALISIS` o `ABSTENERSE`.

## Gates mínimos

- `sequence_audit_status=BLOCKED` si existe `SAME_BAR_CORE_STAGE`,
  `SAME_TIMESTAMP_STAGE`, `TEMPORAL_ORDER`, `FUTURE_CONTEXT` o `HTF_NOT_CLOSED`.
- `sequence_audit_status=REVIEW` si falta evidencia o hay
  `SYNTHETIC_STAGE_COMPRESSION`.
- Dataset IA shadow separa features causales y labels post-hoc.
- Reporte debe incluir sesiones London/NY, frecuencia semanal, taxonomía de
  fallos y `can_trade=false`.

## Decisión posterior

Si el fallo es de motor/proceso, se corrige el motor antes de calibrar. Si el
fallo es económico, se calibra backtest/filtros. Si el fallo es contexto de
mercado, se documenta sin fabricar edge.

## Resultado inicial Misión 5

La ejecución Q1 2022 por chunks mensuales produjo `PASS_DIAGNOSTIC` técnico,
pero `sequence_audit_status=REVIEW` para todos los episodios por
`SYNTHETIC_STAGE_COMPRESSION`. Este estado bloquea usar la IA como selector de
trades; solo puede usarse para análisis forense hasta que la fábrica preserve
etapas operativas multi-bar reales.
