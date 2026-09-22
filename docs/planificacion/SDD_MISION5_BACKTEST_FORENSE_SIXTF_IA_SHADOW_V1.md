# SDD — Misión 5 Backtest forense six-TF + IA shadow

**Estado:** IMPLEMENTACIÓN LOCAL
**Contrato:** `docs/contratos/CONTRATO_BACKTEST_FORENSE_SIXTF_V1.md`

## Diseño

La misión agrega una capa aislada en `backtest/` que consume episodios ya
generados por `MarketObject -> HierarchicalLineage -> SetupBuilder -> Episodes`.
No crea señales. La auditoría revisa tiempos y barras de componentes, clasifica
sesión London/NY y produce un dataset IA shadow sin leakage de labels.

## Salida esperada

El runner `scripts/audit/run_sixtf_episode_backtest.py` emite:

- `forensic_audit`
- `session_summary`
- `weekly_frequency`
- `failure_taxonomy`
- `ai_shadow_dataset`

## Política

`can_trade=false`, `edge_claimed=false`, `mt5_connected=false`,
`orders_sent=false`. La meta de 2–3 trades/semana es criterio de calibración,
no permiso operativo.

## Evidencia Q1 2022

La primera ejecución forense mensual sobre Q1 2022 completó en verde técnico,
pero no habilita entrenamiento operativo:

- Enero 2022: 407 episodios, `mean_net_R=-0.6928`, forense `REVIEW`.
- Febrero 2022: 480 episodios, `mean_net_R=-0.6350`, forense `REVIEW`.
- Marzo 2022: 553 episodios, `mean_net_R=-0.5733`, forense `REVIEW`.
- Consolidado: 1440 episodios, 326 TP, 745 SL, 369 HORIZON, `win_rate=0.3044`,
  `mean_net_R=-0.6212`.

Todos los episodios quedaron en `ABSTENERSE` para IA shadow por
`SYNTHETIC_STAGE_COMPRESSION`. La siguiente corrección debe enfocarse en la
fábrica de episodios/etapas antes de entrenar modelos.
