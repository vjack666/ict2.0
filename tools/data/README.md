# EURUSD M5 Data Acquisition

Pipeline reproducible para adquirir EUR/USD M5 desde Dukascopy sin almacenar el dataset pesado en Git.

## Objetivo

Producir localmente:

```text
data/raw/EURUSD/EURUSD_M5.parquet
data/metadata/EURUSD_M5.json
data/metadata/EURUSD_M5.sha256
```

El dataset es un artefacto de datos, no código fuente. No debe commitearse al repositorio.

## Fuente

Dukascopy Historical Data. La adquisición debe registrar en metadata la URL/endpoint exacto utilizado, rango solicitado, fecha de adquisición, versión de la herramienta y SHA-256 del archivo resultante.

## Requisitos

- Python 3.11+
- `pandas`
- `pyarrow`
- `requests`

Instalación:

```bash
pip install pandas pyarrow requests
```

## Uso

```bash
python tools/data/acquire_eurusd_m5.py --start 2020-01-01 --end 2020-12-31
```

Para CI/Hermes, el rango debe ser explícito mediante variables:

```text
EURUSD_START=2020-01-01
EURUSD_END=2020-12-31
```

Nunca usar una fecha final implícita para un experimento de backtest.

## Validación

El pipeline rechaza el dataset si:

- faltan columnas OHLC;
- hay timestamps duplicados;
- timestamps no están ordenados;
- existen valores NaN/inf en OHLC;
- `high < max(open, close)`;
- `low > min(open, close)`;
- `high < low`;
- existen intervalos M5 imposibles dentro de una sesión continua sin quedar registrados como gap;
- el archivo no puede leerse como Parquet;
- el SHA-256 calculado no coincide con el metadata cuando se valida un artefacto existente.

Los gaps reales de mercado no se rellenan automáticamente: se reportan en metadata.

## Reproducibilidad

Cada adquisición genera:

- fuente;
- instrumento;
- timeframe;
- timezone normalizada a UTC;
- rango solicitado y rango efectivo;
- número de filas;
- número de gaps;
- primera/última vela;
- columnas y tipos;
- SHA-256;
- timestamp de adquisición;
- versión del pipeline.

Un experimento de Hermes debe guardar el SHA-256 del dataset utilizado.
