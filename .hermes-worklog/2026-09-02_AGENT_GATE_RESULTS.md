# Resultados de agentes — gates Edge intradía

## AGENTE / DEPARTAMENTO / TAREA

Codex CEO / CDO Datos + CRO Assurance + Operaciones / verificar los bloqueos
del contrato `PASS_EDGE` sin modificar datos ni ejecutar ciencia.

## STATUS

`BLOCKED — NO-GO` para ejecutar el baseline y para declarar `PASS_EDGE`.

## EVIDENCIA

### Datos intradía

- `241` CSV y `499.864` filas inspeccionadas.
- Manifiestos: `180 + 61` entradas; cobertura `241/241`.
- Faltantes, extras, duplicados, errores de bytes y SHA-256: `0`.
- Las 9 anomalías permanecen en el CSV de octubre de 2024, líneas físicas
  `689, 692, 693, 696, 707, 712, 737, 750 y 765`.
- Cada anomalía incumple `high >= max(open, close)` por `0.00001–0.00002`.
- No se modificaron ni eliminaron filas. La cobertura/hash mecánica pasa, pero
  la corrección OHLC y la procedencia no están demostradas.

### MT5

- Terminal y librería instalados, pero no existe proceso MT5 activo.
- No fue posible observar spread, comisión, fill mode, stops ni ticks.
- No se abrieron órdenes y no se escribieron archivos.

### Corroboración local M15

- `data/raw/EURUSD/EURUSD_M15.parquet` contiene las mismas 9 marcas temporales
  del `2024-10-10` y sus OHLC cumplen las invariantes.
- Las 9 filas difieren de los valores del CSV Dukascopy; esto prueba una
  discrepancia entre fuentes, no que el parquet corrija al CSV.
- El parquet mide `2.552.986` bytes y su SHA-256 actual es
  `49773c106f70a332ad80f2c4bf69b83e1ed0a62a54249f3d6f752570451750b9`.
- Está ignorado por Git, sin historial ni manifiesto de adquisición. Aunque
  documentación operativa lo etiqueta `MT5_LOCAL_PARQUET`, no hay lineage
  reproducible suficiente para usarlo como corrección certificada.
- El gate de datos permanece `BLOCKED`; no se sustituyó ninguna fila.
- Decisión operativa del cliente: las 9 filas se marcan como `DOWNLOAD_SERIALIZATION_ERROR` y como salto aislado, no como trade. Se mantienen intactas en el raw y se excluyen únicamente de la construcción de trades mediante regla documentada; queda pendiente sensibilidad con/sin las 9 filas. Esta decisión permite continuar el sistema sin ocultar la anomalía, pero no convierte el gate de procedencia en `PASS`.

### Búsqueda de lineage adicional

- La búsqueda local de los nueve timestamps en manifests, logs, informes y
  scripts no encontró un tercer registro de origen.
- El conjunto de evidencia local queda limitado al CSV Dukascopy y al parquet
  M15 discrepante; no existe respaldo local que permita resolver cuál de los
  dos valores es correcto.

### Contrato científico

- El contrato `CONTRATO_PASS_EDGE_INTRADIA_V1.md` ya está integrado.
- Define `PASS_EDGE`, `REVIEW`, `NO_EDGE` y `BLOCKED` con veto de datos,
  causalidad, costes, reproducibilidad y provenance.
- Los `PASS` técnicos existentes no se convierten en `PASS_EDGE`.

## ARCHIVOS

- `docs/contratos/CONTRATO_PASS_EDGE_INTRADIA_V1.md`
- `datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json`
- `datasets/eurusd_dukascopy_intraday_2021_2025_manifest.json`
- `datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly/2024/eurusd-m15-bid-2024-10-01-2024-11-01.csv`

## RIESGOS

Las 9 velas pueden afectar rangos, displacement, liquidez y outcomes. Corregir,
excluir o imputar sin evidencia de fuente rompería la reproducibilidad.

## SIGUIENTE ACCIÓN

Obtener evidencia de fuente para las 9 filas y abrir MT5 conectado para la
lectura operativa. Después repetir la auditoría en un worktree limpio. Hasta
entonces no ejecutar backtest, entrenamiento, paper/demo, broker u órdenes.

### Reauditoría coordinada posterior a los commits 564f8a1 y 5d5958f

- Datos/CRO reprodujo `241/241` entradas, `499.864` filas, y cero faltantes,
  extras, duplicados, errores de bytes o SHA-256. El CSV afectado mide
  `124.272` bytes y coincide con su manifiesto.
- La búsqueda adicional solo encontró referencias H1/H4/D1 o reportes derivados;
  no existe un log local que vincule las nueve filas M15 con una adquisición,
  exportación, proveedor o commit generador concreto.
- El script local que declara Dukascopy genera H1/H4/D1 y no constituye evidencia
  primaria para las filas M15. La discrepancia con el parquet MT5 sigue sin
  resolverse y no se usa como corrección.
- Operaciones confirmó `NO_MT5_PROCESS`; no hay evidencia verificable de
  comisión, fill mode, stops ni ticks M15. No se ejecutaron órdenes.
- CRO mantiene `BLOCKED / NO-GO`: no procede `NO_EDGE` porque aún no se midió
  `net_R`, y no procede `PASS_EDGE` porque faltan calidad/procedencia, costes,
  fill, horizonte y reproducibilidad limpia.

### Nueva evidencia local: copias MT5 concordantes

- Se compararon tres parquets locales: el operativo actual y dos copias del
  backup histórico (`data_raw` y `data_mt5`). Los tres contienen las nueve
  marcas temporales con OHLC válido. `data_raw` coincide con el operativo en sus
  `50.296` timestamps comunes; `data_mt5` presenta `432` filas con OHLC
  diferente en su solapamiento. Las copias antiguas además conservan
  `tick_volume` y `spread`.
- Esta evidencia identifica una segunda lectura local coherente, pero no prueba
  que sea la fuente del CSV histórico ni que las copias sean independientes;
  tampoco deben describirse como tres fuentes plenamente concordantes.
Por el contrato de separación de feeds, no se mezclan ni se usa MT5 para
corregir Dukascopy. El gate histórico permanece `BLOCKED`.

### Procedencia parcial del paquete histórico

- La metadata local identifica Dukascopy EURUSD spot bid y registra fecha/comando
  de adquisición para el paquete H1/H4/D1.
- El preregistro T7f documenta el comando mensual M15 y la autorización
  histórica, pero también declara que no existe log de ejecución verificable.
- No existe vínculo máquina-verificable entre esa ejecución declarada y los 241
  CSV actuales. La procedencia M15 queda `PARTIAL/BLOCKED`; no se infiere desde
  el paquete H1/H4/D1 ni se presenta como `PASS`.

### Búsqueda amplia: export MT5 de GRID SCAPL 2

- Se encontró `GRID SCAPL 2/exports/candles_export_full.csv`, generado por un
  script que usa `MetaTrader5.copy_rates_from_pos`.
- Hash SHA-256: `29f0f60ffdb61865d36ea9984ddfea31b0713b86eb1c37ebd13dab2f22a2ad97`;
  tamaño `17.411.179` bytes; 50.000 velas EURUSD M15, rango
  `2024-04-19` a `2026-04-24`.
- Bajo la regla aprobada `low <= open/close <= high`, sus M15 no tienen OHLC
  inválidos. Sus nueve valores de `2024-10-10`, sin embargo, difieren del CSV
  histórico Dukascopy y no cubren 2006–2025; no son sustituto ni corrección.
- El README y el script prueban el mecanismo MT5, pero no aportan un log de
  ejecución fechado que vincule este export con el dataset histórico. El gate
  histórico continúa `BLOCKED`.

### Cierre de búsqueda de cobertura local alternativa

- `GRID SCAPL 2/data/market_ohlc/curated` solo contiene cinco archivos EURUSD
  M15 de 2026; no existe allí una cobertura M15 2006–2025 alternativa.
- Sumado a la búsqueda del repositorio, backups y exports locales, no queda una
  fuente local con cobertura completa, lineage verificable y valores
  reconciliados que permita cerrar Paso 1.
- Se cierra la investigación local como `BLOCKED_EXTERNAL_EVIDENCE`: no se
  descarga, rescata, repara ni sustituye ningún dato.

### Corrección de la auditoría en worktree limpio

- La primera versión del auditor trataba números de línea física como índices
  de datos y desplazaba las nueve observaciones. Se corrigió el productor para
  leer explícitamente líneas físicas incluyendo el encabezado.
- El rerun reproducible en `cert/edge-roadmap-clean-worktree` confirma `241`
  CSV, manifiestos `180 + 61` con `bad_count=0` y las `9/9` anomalías en las
  líneas físicas `689, 692, 693, 696, 707, 712, 737, 750, 765`.
- Commit del arreglo: `19ae150` (`fix: audit intraday anomalies by physical CSV line`).
  El resultado sigue siendo `BLOCKED`; se corrigió la medición, no los datos.

### Corrida técnica PROXY_PILOT

- Se ejecutó una prueba de humo local sobre EURUSD M15, 2022-01-01 a
  2022-01-15 UTC, con contexto D1/H1/H4 y horizonte de 12 velas.
- Resultado: 960 velas, 1.033 eventos estructurales, 3 señales y 3 registros
  técnicos de trade; se observaron `SWEEP`, `DISPLACE`, `BOS` y `ENTRY`.
- Evidencia: `reports/audits/edge_proxy_pilot_smoke_20260902.md`.
- Estado: `REVIEW` técnico de preparación; no es evidencia de edge. El runner
  económico exacto del SDD aún debe implementarse y verificarse; el gate global
  continúa `BLOCKED`, con `can_trade=false` y `can_train=false`.

### Enmienda de geometría resuelta antes de la corrida confirmatoria

- Se adoptó `CAUSAL_AVG_RANGE_50`: `0,3 × rango medio causal high-low de 50
  velas`, preservando el motor sin indicadores.
- La decisión quedó congelada en el preregistro antes de ejecutar DESIGN,
  VALIDATION o HOLDOUT; no se resolverá post-hoc.
- Evidencia: `docs/experimentos/AMENDMENT_STOP_GEOMETRY_PRE_RUN.md`.

### Baseline económico proxy — 2022 Q1

- Corrida completa del trimestre con el runner económico: 6.168 velas M15,
  6.604 eventos, 19 señales/trades técnicos, 7 outcomes resueltos y 12
  abiertos/no resolubles al horizonte.
- Media de los 7 `net_R` resueltos: `-0,618815R`.
- Evidencia: `reports/audits/experiments/pass_edge_proxy_pilot_2022_Q1.json`.
- Es una lectura diagnóstica del proxy, no una prueba confirmatoria de edge;
  faltan los demás periodos, intervalos/robustez y la auditoría completa de
  procedencia.

### Baseline económico proxy — 2022 consolidado

- Q1–Q4: 75 trades técnicos y 19 outcomes resueltos.
- Media ponderada de los 19 `net_R`: `-1,025420R`; las cuatro particiones
  trimestrales fueron negativas.
- Evidencia: `reports/audits/experiments/pass_edge_proxy_pilot_2022_summary.md`
  y los cuatro JSON trimestrales.
- No se declara `NO_EDGE` global: faltan cobertura completa, análisis de
  robustez y cierre de procedencia; el gate de certificación sigue `BLOCKED`.

### Baseline económico proxy — 2023 y consolidado 2022–2023

- 2023 Q1–Q4: 94 trades, 24 outcomes resueltos; todos los trimestres fueron
  negativos.
- Consolidado 2022–2023: 169 trades, 43 outcomes resueltos, media `-1,114712R`.
- Evidencia: `reports/audits/experiments/pass_edge_proxy_pilot_2022_2023_summary.md`
  y los ocho JSON trimestrales.

### Baseline económico proxy — 2024 y consolidado 2022–2024

- 2024: 84 trades, 25 outcomes resueltos; solo Q2 fue positivo.
- Consolidado 2022–2024: 253 trades, 68 outcomes resueltos, media `-1,098611R`.
- Evidencia: `reports/audits/experiments/pass_edge_proxy_pilot_2022_2024_summary.md`
  y los doce JSON trimestrales.

### Baseline económico proxy — 2025 y consolidado 2022–2025

- 2025: 62 trades, 13 outcomes resueltos; solo Q3 fue positivo y tuvo 2
  outcomes resueltos.
- Consolidado: 315 trades, 81 outcomes resueltos, media `-1,077566R`.
- Bootstrap iid exploratorio (10.000, semilla `20260902`): IC aproximado
  `[-1,476154R, -0,696710R]`; no sustituye el análisis clusterizado del SDD.
- Evidencia: `reports/audits/experiments/pass_edge_proxy_pilot_2022_2025_summary.md`
  y los dieciséis JSON trimestrales.

### Robustez por sesión y régimen

- Outcomes por sesión UTC: London 11 (`-0,489994R`), NY 3 (`-1,239506R`) y
  otras horas 67 (`-1,166782R`).
- Outcomes resueltos: 71 SL y 10 TP.
- Los artefactos no contienen una etiqueta de régimen congelada; la dimensión
  de régimen queda `MISSING`, no se reconstruye post-hoc.
- Evidencia: `reports/audits/experiments/pass_edge_robustness_2022_2025.md`.
