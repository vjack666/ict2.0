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
- `entry_protocol_summary` clasifica PO3, Silver Bullet y Turtle Soup usando
  módulos existentes del motor.
- `timeframe_worker_evidence` registra la muestra diagnóstica D1/H4/H1/M15/M5
  vía `MTFNavigator` y M1 vía `sequential_events`.

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

## Extensión Misión 7 — protocolos de tesis y trabajadores

Se conectaron los protocolos de entrada ya existentes al backtest forense:

- PO3: `engine.po3.build_po3_state`.
- Silver Bullet: `engine.silver_bullet.is_silver_bullet` + killzones
  canónicas.
- Turtle Soup: `engine.turtle_soup.is_turtle_soup`.

La caja negra por episodio incluye `entry_protocols`. La IA shadow ahora exige
secuencia causal PASS, sesión válida y al menos una familia de entrada completa
antes de `ACEPTAR_ANALISIS`.

Resultado de aceptación sobre 2022-03-07..2022-03-13:

- Backtest: `PASS_DIAGNOSTIC`.
- Episodios: 121.
- Forense: PASS 121/121.
- Protocolos completos: PO3 121; Silver Bullet 0; Turtle Soup 0.
- IA shadow: `ACEPTAR_ANALISIS=40`, `ABSTENERSE=81`.
- Subconjunto aceptado: 40 trades, 16 TP, 24 SL, `mean_net_R=-0.4300`.
- Worker evidence: D1/H4/H1/M15/M5 disponibles y respondidos en 48/48
  decisiones muestreadas; M1 `sequence_status=PASS` en 121/121.

El resultado sigue siendo diagnóstico y negativo. La próxima fase debe mejorar
semántica de filtros/calibración, no activar trading.
