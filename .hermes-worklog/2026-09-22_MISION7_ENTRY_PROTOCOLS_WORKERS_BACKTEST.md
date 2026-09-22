# Bitácora — Misión 7 Protocolos de entrada + trabajadores en backtest

**Fecha:** 2026-09-22
**Estado:** COMPLETED_LOCAL_IMPLEMENTATION
**Política:** `can_trade=false`, sin MT5, sin órdenes, sin entrenamiento IA.

## Objetivo

Conectar al backtest forense los protocolos de entrada de la tesis — PO3,
Silver Bullet y Turtle Soup — reutilizando módulos existentes. Además, dejar
evidencia inicial del modelo de “trabajadores” por temporalidad sin crear seis
motores nuevos.

## Cambios

- `backtest/sixtf_forensic.py`
  - Clasificación `entry_protocols` por episodio.
  - IA shadow se abstiene si no hay familia de entrada completa.
  - Caja negra JSONL incluye protocolos.
  - Evidencia de trabajadores: D1/H4/H1/M15/M5 vía `MTFNavigator`; M1 vía
    `sequential_events`.
- `scripts/audit/run_sixtf_episode_backtest.py`
  - Exporta `entry_protocol_summary`.
  - Exporta `timeframe_worker_evidence`.
- `tests/test_sixtf_forensic.py`
  - Pruebas de protocolos, abstención sin protocolo y evidencia de workers.
- Documentación de gobierno
  - SDD propio: `docs/planificacion/SDD_MISION7_ENTRY_PROTOCOLS_WORKERS_BACKTEST_V1.md`.
  - Autoridad: `docs/INDICE_AUTORIDAD.md`.
  - Biblioteca ICT: `docs/ict/00_INDICE.md`.
  - Contratos multimodelo/frecuencia: `docs/contratos/ICT_MULTIMODEL_CANDIDATE_V1.md`
    y `docs/contratos/FREQ_GATE_2_3_WEEKLY_V1.md`.
  - Plan multimodelo: `docs/planificacion/PLAN_ICT_MULTIMODELO_INTRADIA_V1.md`.

## Evidencia

Pruebas:

```text
python -m pytest -q tests/test_sixtf_forensic.py tests/test_sixtf_episode_backtest.py
14 passed

python -m pytest -q tests/test_sixtf_forensic.py tests/test_sixtf_episode_backtest.py tests/test_backtest_economics.py tests/test_sixtf_marketobject_connector.py tests/test_lineage_hierarchy.py tests/test_setup_builder_integration.py tests/test_episodes.py tests/test_sequential_events.py
70 passed
```

Backtest diagnóstico:

```text
python scripts/audit/run_sixtf_episode_backtest.py --data-dir data/raw/EURUSD --start-time 2022-03-07T00:00:00Z --end-time 2022-03-13T23:00:00Z --decisions 168 --step-minutes 60 --horizon-m1-bars 240 --risk-pips 10 --reward-r 2 --spread-pips 1.0 --slippage-pips 0.3 --commission-per-lot-side 5.0 --sequence-tf M1 --output reports/audits/experiments/mission7/sixtf_episode_backtest_entry_protocols_2022_03_w2.json --blackbox-output reports/audits/experiments/mission7/sixtf_entry_protocols_blackbox_2022_03_w2.jsonl
```

Resultado:

- `status=PASS_DIAGNOSTIC`.
- Episodios/trades: 121.
- Resultado económico: 34 TP, 76 SL, 11 HORIZON.
- `win_rate=0.3091`.
- `mean_net_R=-0.6118`.
- Forense: PASS 121/121.
- Protocolos completos: PO3 121; Silver Bullet 0; Turtle Soup 0.
- IA shadow: `ACEPTAR_ANALISIS=40`, `ABSTENERSE=81`.
- Subconjunto aceptado por IA: 16 TP, 24 SL, `mean_net_R=-0.4300`.
- Caja negra: 121 líneas.
- Worker evidence: D1/H4/H1/M15/M5 disponibles en 48/48 decisiones
  muestreadas; M1 PASS 121/121.

## Dictamen

La entrada por tesis ya está conectada al backtest, pero todavía no demuestra
edge. En esta ventana, PO3 actúa como filtro semántico principal y no aparecen
Silver Bullet/Turtle Soup completos con la evidencia real disponible. La IA
shadow reduce la población analítica de 121 a 40, pero el subconjunto sigue
negativo.

## Riesgos y siguiente acción

- PO3 puede estar demasiado permisivo porque se alimenta con la secuencia real
  y dirección del episodio; debe calibrarse con reglas de calidad más estrictas.
- Silver Bullet/Turtle Soup pueden requerir mejor mapeo de sweep/reversal y
  horarios para no quedar invisibles cuando existan.
- El mes completo fue interrumpido por coste de ejecución; la ventana semanal
  queda como aceptación funcional. Siguiente paso: optimizar runner por chunks
  y ampliar muestra sin perder causalidad.

## Cierre documental reforzado

Se agregó SDD específico de Misión 7 porque dejar la misión solo como extensión
de Misión 6 podía inducir a confundir “secuencia real M1” con “protocolos de
entrada calibrados”. El nuevo SDD declara explícitamente que PO3/Silver/Turtle
están conectados en modo diagnóstico, pero la calibración de calidad y el gate
2–3 semanal siguen pendientes.
