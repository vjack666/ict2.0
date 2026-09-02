# Auditoría Data — calidad y procedencia intradía

**AGENTE:** Codex / Data Analytics  
**DEPARTAMENTO:** CDO / Datos + CRO / Assurance  
**TAREA:** Auditar calidad, cobertura de manifiesto y procedencia de los datasets EURUSD M15 existentes.  
**STATUS:** BLOCKED  
**VEREDICTO:** NO-GO para certificación científica, promoción o autorización operativa.

## Evidencia

- 241 archivos CSV y 499.864 velas inspeccionadas.
- Esquema uniforme: `timestamp, open, high, low, close, volume`.
- 0 duplicados de timestamp dentro de archivo.
- El manifiesto de 180 archivos tiene 0 faltantes, 0 errores de tamaño y 0 hashes SHA-256 incorrectos.
- El manifiesto original cubría 180 archivos y `datasets/eurusd_dukascopy_intraday_2021_2025_manifest.json` cubre los 61 restantes; la cobertura actual es 241/241, con 0 faltantes, 0 errores de tamaño y 0 hashes incorrectos. La repetición en worktree limpio sigue siendo un requisito de certificación, no un faltante de cobertura.
- Se detectaron 9 filas OHLC inválidas, todas en `datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly/2024/eurusd-m15-bid-2024-10-01-2024-11-01.csv`, filas 689, 692, 693, 696, 707, 712, 737, 750, 765. Por decisión operativa del cliente se clasifican como `DOWNLOAD_SERIALIZATION_ERROR`: quedan visibles e intactas, pero no se consideran un trade ni una señal; se tratan como un salto aislado de datos.
- Tres copias locales del feed MT5 contienen OHLC válido en las nueve marcas: `data/raw`, `legacy_smc_backup/data_raw` y `legacy_smc_backup/data_mt5`. La copia `data_raw` coincide con el parquet operativo en sus `50.296` timestamps comunes; `data_mt5` difiere en OHLC en `432` filas de su solapamiento. No son tres fuentes independientes plenamente concordantes y no constituyen una corrección certificada del CSV histórico Dukascopy.

## Procedencia parcial demostrada

- `datasets/eurusd_dukascopy_20y/metadata.json` identifica proveedor e instrumento y registra fecha/comando de adquisición para H1/H4/D1.
- `docs/experimentos/EXP_MTF_REPLAY_T7F_2006_2020_PREREGISTRATION.md` documenta la fuente M15, el comando mensual y la autorización histórica, pero declara que no existe log de ejecución verificable.
- Ningún artefacto local vincula de forma máquina-verificable ese comando M15 con los 241 CSV actuales. Por tanto, la procedencia M15 es **PARCIAL**, no `PASS`.
- Se inspeccionó además `C:\Users\v_jac\Desktop\GRID SCAPL 2\exports\candles_export_full.csv`: hash SHA-256 `29f0f60ffdb61865d36ea9984ddfea31b0713b86eb1c37ebd13dab2f22a2ad97`, 17.411.179 bytes, 50.000 velas EURUSD M15 desde 2024-04-19 hasta 2026-04-24. Bajo la regla no estricta aprobada no tiene OHLC inválidos, pero no cubre 2006-2025 completo, difiere del CSV histórico y su exportación MT5 no aporta un log de adquisición reproducible para el conjunto histórico.

## Riesgos

Las anomalías quedan fuera de la construcción de trades por la regla anterior, sin borrar ni corregir filas. Debe ejecutarse una sensibilidad incluyendo/excluyendo las 9 filas y registrar si cambia cualquier resultado. La concordancia MT5 demuestra una segunda lectura local, pero no resuelve el conflicto de fuente ni autoriza mezclar feeds. Además, los hashes técnicos no prueban por sí solos la identidad de la fuente ni el lineage completo de adquisición. El estado de procedencia permanece `BLOCKED` hasta cerrar esa evidencia.

## Aplicación realizada

Se creó el dictamen machine-readable y su resumen Markdown. No se modificaron datasets, reportes históricos ni lógica del motor; tampoco se ejecutaron backtests, descargas, entrenamientos ni promoción.

## Siguiente acción

1. Resolver las nueve filas desde evidencia de fuente, sin corrección silenciosa.
2. Documentar evidencia de fuente para el parquet M15 discrepante o mantenerlo fuera del conjunto canónico.
3. Repetir la auditoría completa en un worktree limpio y explícitamente scoped.
