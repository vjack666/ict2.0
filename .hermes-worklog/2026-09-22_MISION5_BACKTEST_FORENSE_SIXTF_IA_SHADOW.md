# Bitácora — Misión 5 Backtest forense six-TF + IA shadow

## Objetivo

Endurecer el backtest six-TF para detectar episodios fabricados de forma
instantánea o comprimida, separar sesiones Londres/NY, medir frecuencia semanal
y preparar un dataset IA shadow sin autorizar trading.

## Implementación

- Consumidor forense aislado en `backtest/sixtf_forensic.py`.
- Metadata causal mínima en Episodes para auditar tiempos de componentes.
- Runner six-TF extendido con:
  - `forensic_audit`
  - `session_summary`
  - `weekly_frequency`
  - `failure_taxonomy`
  - `ai_shadow_dataset`
- Pruebas focales para compresión en una vela, futuro, HTF no cerrado, sesión y
  separación features/labels.

## Política

IA solo como analista: `ACEPTAR_ANALISIS`, `RECHAZAR_ANALISIS`, `ABSTENERSE`.
Sin MT5, sin órdenes, sin edge declarado y `can_trade=false`.

## Evidencia ejecutada

Suite focal/regresión:

```text
python -m pytest -q tests/test_sixtf_forensic.py tests/test_sixtf_episode_backtest.py tests/test_backtest_economics.py tests/test_sixtf_marketobject_connector.py tests/test_lineage_hierarchy.py tests/test_setup_builder_integration.py tests/test_episodes.py
51 passed
```

Backtest forense por chunks mensuales Q1 2022:

| Mes | Decisiones | Episodios | TP | SL | HORIZON | win_rate | mean_net_R | Forense | IA shadow |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2022-01 | 506 | 407 | 65 | 177 | 165 | 0.2686 | -0.6928 | REVIEW: SYNTHETIC_STAGE_COMPRESSION | ABSTENERSE 407 |
| 2022-02 | 480 | 480 | 108 | 255 | 117 | 0.2975 | -0.6350 | REVIEW: SYNTHETIC_STAGE_COMPRESSION | ABSTENERSE 480 |
| 2022-03 | 553 | 553 | 153 | 313 | 87 | 0.3283 | -0.5733 | REVIEW: SYNTHETIC_STAGE_COMPRESSION | ABSTENERSE 553 |
| Q1 práctico | 1539 | 1440 | 326 | 745 | 369 | 0.3044 | -0.6212 | REVIEW 1440/1440 | ABSTENERSE 1440 |

Artefactos:

- `reports/audits/experiments/mission5/sixtf_episode_backtest_forensic_2022_01.json`
- `reports/audits/experiments/mission5/sixtf_episode_backtest_forensic_2022_02.json`
- `reports/audits/experiments/mission5/sixtf_episode_backtest_forensic_2022_03.json`

## Veredicto

No se detectó `BLOCKED` por futuro o HTF no cerrado en esta ventana, pero el
100% de episodios queda en `REVIEW` por compresión sintética de etapas dentro
del componente (`candidate_time == confirmation_time == tradable_time`). Esto
confirma que no conviene entrenar IA para tomar decisiones todavía: primero hay
que corregir o enriquecer la fábrica de episodios para preservar una secuencia
operativa real multi-bar antes de calibrar frecuencia 2-3 trades/semana.
