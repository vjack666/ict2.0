# SDD — Misión 6 Secuencia real en backtest + caja negra

**Estado:** IMPLEMENTACIÓN LOCAL
**Contrato:** `docs/contratos/CONTRATO_BACKTEST_SECUENCIA_REAL_SIXTF_V1.md`

## Diseño

El runner six-TF precomputa `engine.sequential_events.run_sequential` sobre la
temporalidad de ejecución (`M1` por defecto). Para cada episodio busca la última
cadena completa con dirección compatible y cierre anterior a `decision_time`.
Esa evidencia se pasa al auditor forense para resolver la compresión sintética.

## Salidas

- Reporte JSON de backtest con `sequence_evidence`.
- Caja negra JSONL por episodio.
- `forensic_audit` debe diferenciar compresión sintética resuelta por cadena
  real de fallos duros como futuro o HTF abierto.

## Resultado marzo 2022

- `forensic_audit`: PASS 553/553.
- Cadenas M1 completas disponibles: 122.
- IA shadow: `ACEPTAR_ANALISIS=184`, `ABSTENERSE=369`.
- Subconjunto aceptado: 184 trades, 69 TP, 111 SL, 4 HORIZON,
  `win_rate=0.3833`, `mean_net_R=-0.4633`.
- Frecuencia aceptada: 32–40 por semana, todavía muy por encima de la meta
  2–3/semana.

## Próximo cuello

La compresión temporal quedó resuelta para el auditor, pero falta filtro de
calidad/calibración para bajar frecuencia y mejorar expectativa.
