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
