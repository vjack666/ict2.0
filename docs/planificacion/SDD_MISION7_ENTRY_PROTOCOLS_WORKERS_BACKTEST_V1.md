# SDD — Misión 7 Protocolos de entrada + workers en backtest v1

**Estado:** IMPLEMENTADO LOCALMENTE / DIAGNÓSTICO
**Fecha:** 2026-09-22
**Autoridad:** `can_trade=false`, `entry_authorized=false`, sin MT5, sin órdenes.

## Objetivo

Conectar al backtest six-TF los protocolos de entrada de la tesis ICT sin crear
un motor paralelo:

- PO3 / AMD.
- Silver Bullet.
- Turtle Soup.

Además, publicar una primera caja negra de “trabajadores por temporalidad” para
ver si el backtest está reconstruyendo contexto como un trader humano:

- D1: contexto.
- H4: ubicación.
- H1: estructura y profundidad.
- M15: refinamiento.
- M5: confirmación.
- M1: ejecución/evidencia secuencial.

## Límites

- Esta misión no autoriza trading.
- Esta misión no declara edge.
- Esta misión no conecta MT5.
- Esta misión no entrena IA productiva.
- La IA queda en modo shadow: análisis, abstención y diagnóstico.
- `engine/` no importa `backtest/`.

## Diseño implementado

### Protocolos de entrada

El runner forense reutiliza módulos existentes:

| Familia | Módulo | Uso en backtest |
| --- | --- | --- |
| PO3 | `engine.po3.build_po3_state` | Clasifica ciclo A/M/D desde evidencia secuencial cerrada. |
| Silver Bullet | `engine.silver_bullet.is_silver_bullet` + `engine.killzone.killzone_en` | Verifica sweep→retest dentro de killzone compatible. |
| Turtle Soup | `engine.turtle_soup.is_turtle_soup` | Verifica sweep/reversal sobre marco LTF disponible. |

El resultado por episodio queda en `entry_protocols` y se resume en
`entry_protocol_summary`.

### Workers por temporalidad

La evidencia se publica como diagnóstico:

| Worker | Fuente reutilizada | Salida |
| --- | --- | --- |
| D1/H4/H1/M15/M5 | `engine.mtf_navigation.MTFNavigator` | capas disponibles, respuestas y path de navegación. |
| M1 | `engine.sequential_events.run_sequential` | cadena causal multi-bar y `sequence_status`. |
| Coordinador | `scripts/audit/run_sixtf_episode_backtest.py` | reporte, caja negra y política. |

Para no convertir el backtest económico en una navegación pesada por cada vela,
la evidencia D1–M5 se muestrea como caja negra (`FIRST_48_DECISIONS`). La
evidencia M1 de secuencia se mantiene para todos los episodios.

## Reglas IA shadow

La decisión `ACEPTAR_ANALISIS` solo puede emitirse si:

1. `sequence_audit_status == PASS`.
2. La sesión no es `OFF_SESSION`.
3. Existe al menos una familia de entrada completa.

Si no hay protocolo completo, la IA debe abstenerse aunque la secuencia M1 sea
causalmente válida.

## Evidencia de aceptación

Comandos ejecutados:

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
- 121 episodios.
- Forense: PASS 121/121.
- Resultado económico: 34 TP, 76 SL, 11 HORIZON.
- `win_rate=0.3091`.
- `mean_net_R=-0.6118`.
- Protocolos completos: PO3 121; Silver Bullet 0; Turtle Soup 0.
- IA shadow: `ACEPTAR_ANALISIS=40`, `ABSTENERSE=81`.
- Subconjunto aceptado: 40 trades, 16 TP, 24 SL, `mean_net_R=-0.4300`.
- Worker evidence: D1/H4/H1/M15/M5 disponibles y respondidos en 48/48
  decisiones muestreadas; M1 PASS 121/121.

## Dictamen

La conexión funciona, pero no hay edge. PO3 aparece demasiado amplio en esta
ventana; Silver Bullet y Turtle Soup no aparecen completos con la evidencia
real disponible. La siguiente fase debe calibrar calidad, mapeo de familias,
deduplicación y frecuencia antes de cualquier entrenamiento o promoción.

## Próximos pasos

1. Optimizar runner por chunks para ampliar marzo completo sin bloquear.
2. Endurecer PO3 para no aceptar cualquier secuencia válida como ciclo completo.
3. Revisar mapeo sweep/reversal de Turtle Soup y sweep/FVG/KZ de Silver Bullet.
4. Medir frecuencia deduplicada contra `FREQ_GATE_2_3_WEEKLY_V1`.
5. Mantener IA en shadow hasta que exista población causal, estable y menos
   frecuente.
