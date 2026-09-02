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

### Corrección de la auditoría en worktree limpio

- La primera versión del auditor trataba números de línea física como índices
  de datos y desplazaba las nueve observaciones. Se corrigió el productor para
  leer explícitamente líneas físicas incluyendo el encabezado.
- El rerun reproducible en `cert/edge-roadmap-clean-worktree` confirma `241`
  CSV, manifiestos `180 + 61` con `bad_count=0` y las `9/9` anomalías en las
  líneas físicas `689, 692, 693, 696, 707, 712, 737, 750, 765`.
- Commit del arreglo: `19ae150` (`fix: audit intraday anomalies by physical CSV line`).
  El resultado sigue siendo `BLOCKED`; se corrigió la medición, no los datos.
