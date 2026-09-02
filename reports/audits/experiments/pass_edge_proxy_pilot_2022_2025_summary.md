# Baseline económico PROXY_PILOT — 2022–2025

| Año | Trades | Resueltos | Media net_R |
|---|---:|---:|---:|
| 2022 | 75 | 19 | -1,025420 |
| 2023 | 94 | 24 | -1,185401 |
| 2024 | 84 | 25 | -1,070918 |
| 2025 | 62 | 13 | -0,967482 |
| **Total** | **315** | **81** | **-1,077566** |

En 2025 Q1/Q2/Q3/Q4 las medias fueron `-1,441031R`, `-1,133951R`,
`+0,688480R` y `-1,278386R`; solo Q3 fue positivo y se basa en 2 outcomes
resueltos. El consolidado se calcula sobre los 81 outcomes, no sobre medias
trimestrales.

Como diagnóstico descriptivo, un bootstrap iid de 10.000 remuestras con semilla
`20260902` produjo IC aproximado del 95% para la media de `[-1,476154R,
-0,696710R]`. No sustituye el IC por clusters temporales exigido por el SDD.

**Estado:** diagnóstico `REVIEW`; certificación global `BLOCKED`. Baseline sin
IA, `can_trade=false`, `can_train=false`.
