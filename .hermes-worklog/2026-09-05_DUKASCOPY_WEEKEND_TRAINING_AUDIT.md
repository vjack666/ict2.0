# Auditoría de primeros pasos con data descargada

## Alcance

Se inspeccionaron únicamente datasets locales Dukascopy, sin descargar ni modificar raw.

- `datasets/eurusd_dukascopy_intraday_2006_2010`: 62 archivos, 7.093.383 bytes.
- `datasets/eurusd_dukascopy_intraday_2011_2020`: 120 archivos, 13.231.273 bytes.
- `datasets/eurusd_dukascopy_intraday_2021_2025`: 61 archivos, 7.088.260 bytes.
- Los archivos disponibles son barras M15 (`eurusd-m15-bid-...csv`); no hay M1/M5 Dukascopy equivalentes en estas carpetas.

## Prueba ejecutada

Se creó un derivado temporal de `data/materialized/v2/v2_real_2006_q4.jsonl` con tiempos ISO y `label_end_6` para probar el runner diagnóstico. El runner se detuvo con:

`TEMPORAL_SEQUENCE_DEPTH_ZERO: rebuild rolling closed-bar sequence`.

La detención es correcta: el corpus antiguo no contiene profundidad de secuencia causal V2. No se rellenó con ceros ni se declaró entrenamiento válido.

## Decisión técnica

La data descargada sirve para el primer paso de inventario y para un experimento M15-only separado. No puede alimentar todavía el modelo V2 canónico que exige Context State, zonas, BOS y confirmación M5/M1, porque faltan las series LTF y la secuencia rolling. La salida conserva `can_trade=false`.

## Siguiente paso del fin de semana

Elegir explícitamente una de estas rutas antes de entrenar:

1. Entrenamiento V2 canónico con las seis temporalidades locales de `data/raw/EURUSD` y Dukascopy solo como auditoría M15.
2. Modelo M15-only diagnóstico, con perfil y contrato separados, sin presentarlo como V2 canónico.

No se ejecuta backtest ni promoción con el corpus descargado hasta resolver esa elección.
