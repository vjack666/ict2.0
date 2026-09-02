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
- El árbol completo contiene 241 archivos: 61 archivos no están cubiertos por ese manifiesto.
- Se detectaron 9 filas OHLC inválidas, todas en `datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly/2024/eurusd-m15-bid-2024-10-01-2024-11-01.csv`, filas 689, 692, 693, 696, 707, 712, 737, 750 y 765.

## Riesgos

Las anomalías pueden cambiar rangos, displacement, liquidez y etiquetas o setups posteriores. La cobertura incompleta del manifiesto impide reconstruir la identidad exacta del conjunto completo. Además, los hashes técnicos no prueban licencia, uso permitido ni lineage completo de adquisición.

## Aplicación realizada

Se creó el dictamen machine-readable y su resumen Markdown. No se modificaron datasets, reportes históricos ni lógica del motor; tampoco se ejecutaron backtests, descargas, entrenamientos ni promoción.

## Siguiente acción

1. Resolver las nueve filas desde evidencia de fuente, sin corrección silenciosa.
2. Completar y verificar el manifiesto de los 241 archivos.
3. Completar licencia, uso permitido, adquisición y commit generador.
4. Repetir la auditoría en un worktree limpio.
