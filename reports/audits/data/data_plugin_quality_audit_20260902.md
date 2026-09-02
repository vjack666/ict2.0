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
- Se detectaron 9 filas OHLC inválidas, todas en `datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly/2024/eurusd-m15-bid-2024-10-01-2024-11-01.csv`, filas 689, 692, 693, 696, 707, 712, 737, 750 y 765.
- Tres copias locales del feed MT5 contienen OHLC válido en las nueve marcas: `data/raw`, `legacy_smc_backup/data_raw` y `legacy_smc_backup/data_mt5`. La copia `data_raw` coincide con el parquet operativo en sus `50.296` timestamps comunes; `data_mt5` difiere en OHLC en `432` filas de su solapamiento. No son tres fuentes independientes plenamente concordantes y no constituyen una corrección certificada del CSV histórico Dukascopy.

## Riesgos

Las anomalías pueden cambiar rangos, displacement, liquidez y etiquetas o setups posteriores. La concordancia MT5 demuestra una segunda lectura local, pero no resuelve el conflicto de fuente ni autoriza mezclar feeds. Además, los hashes técnicos no prueban por sí solos la identidad de la fuente ni el lineage completo de adquisición.

## Aplicación realizada

Se creó el dictamen machine-readable y su resumen Markdown. No se modificaron datasets, reportes históricos ni lógica del motor; tampoco se ejecutaron backtests, descargas, entrenamientos ni promoción.

## Siguiente acción

1. Resolver las nueve filas desde evidencia de fuente, sin corrección silenciosa.
2. Documentar evidencia de fuente para el parquet M15 discrepante o mantenerlo fuera del conjunto canónico.
3. Repetir la auditoría completa en un worktree limpio y explícitamente scoped.
