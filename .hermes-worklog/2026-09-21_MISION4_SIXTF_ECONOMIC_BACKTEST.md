# Mision 4 — Backtest economico aislado sobre episodios seis-TF

**Fecha:** 2026-09-21  
**Rama:** `preservation/before-lineage-hierarchical-integration-20260921`  
**Estado tecnico:** `PASS_DIAGNOSTIC`  
**Estado economico:** `REVIEW_NEGATIVE_EXPECTANCY`  
**No autoriza:** trading, MT5, edge, entrenamiento productivo ni promocion.

## Objetivo

Actualizar el backtest para que consuma los episodios seis-TF reales del motor
actual:

```text
seis TF -> MarketObject -> HierarchicalLineage -> Episodes -> backtest economico aislado
```

## Implementacion

Nuevos artefactos:

- `backtest/sixtf_episode_backtest.py`
- `scripts/audit/run_sixtf_episode_backtest.py`
- `tests/test_sixtf_episode_backtest.py`
- `reports/audits/experiments/mission4/sixtf_episode_backtest_2022_03.json`

El backtest:

- usa episodios reales seis-TF;
- entra en el cierre M1 disponible en `decision_time`;
- resuelve SL/TP solo con barras M1 futuras;
- aplica spread, slippage y comision con `backtest.economics`;
- conserva `can_trade=false`, `edge_claimed=false`, `diagnostic_only=true`;
- no conecta MT5 ni emite ordenes.

## Calibracion de Mision 2 para rendimiento

El intento de Q1 completo horario y de marzo horario con snapshot completo
resulto demasiado lento porque `MTFNavigator` se recalculaba por cada
decision. Se calibro el conector agregando:

```text
SixTFConnectorConfig(build_context_snapshot=False)
```

Uso exclusivo del backtest economico masivo:

- No salta las seis temporalidades.
- No salta `MarketObject`.
- No salta `HierarchicalLineage(require_all_six_tfs=True)`.
- No salta `build_setups_at()` ni `build_episodes()`.
- No salta FULL/PREFIX.
- Solo omite el snapshot detallado de `MTFNavigator` por decision, ya cubierto
  por Mision 2/Mision 3.

## Evidencia ejecutada

Comando final:

```text
python scripts/audit/run_sixtf_episode_backtest.py ^
  --data-dir data/raw/EURUSD ^
  --start-time 2022-03-01T00:00:00Z ^
  --end-time 2022-03-31T23:00:00Z ^
  --decisions 744 ^
  --step-minutes 60 ^
  --horizon-m1-bars 240 ^
  --risk-pips 10 ^
  --reward-r 2 ^
  --spread-pips 1.0 ^
  --slippage-pips 0.3 ^
  --commission-per-lot-side 5.0 ^
  --output reports/audits/experiments/mission4/sixtf_episode_backtest_2022_03.json
```

Resultado:

```text
status=PASS_DIAGNOSTIC
period=2022-03-01T00:00:00Z -> 2022-03-31T23:00:00Z
decision_count=553
episode_count=553
rejection_count=553
resolved_count=466
unresolved_count=87
TP=153
SL=313
HORIZON=87
win_rate=0.3283261802575107
mean_gross_R=-0.34334763948497854
mean_net_R=-0.5733476394850038
sum_net_R=-267.1800000000118
window_checksum=16a96044ed1ab6f87d491fec5f10e395742dda1596c9943a4a9f32d21fdc8528
can_trade=false
edge_claimed=false
```

## Intentos de maxima data

- Q1 2022 horario completo fue intentado, pero excedio la ventana practica de
  esta iteracion. No se declara fallido economicamente; queda como
  `PERFORMANCE_SCALING_PENDING`.
- La mayor ventana completada en verde fue marzo 2022 horario, con 553
  decisiones efectivas.

## Pruebas

```text
python -m pytest -q tests/test_sixtf_episode_backtest.py tests/test_backtest_economics.py tests/test_sixtf_marketobject_connector.py tests/test_lineage_hierarchy.py tests/test_setup_builder_integration.py tests/test_episodes.py
45 passed
```

## Dictamen

El backtest esta actualizado a las ultimas capas del motor seis-TF y pasa los
gates tecnicos. El resultado economico de la ventana auditada es negativo; por
tanto:

```text
economic_edge_claimed=false
can_trade=false
next_status=REVIEW_NEGATIVE_EXPECTANCY
```

Siguiente paso recomendado: calibrar reglas de entrada/salida y/o filtros de
episodio antes de ampliar el backtest o crear dataset IA economico.
