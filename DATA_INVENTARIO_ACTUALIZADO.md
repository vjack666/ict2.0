# Inventario de datos — estado actual

**Actualizado:** 2026-08-17

## Decisión de trabajo

M5 queda **DEFERRED** por ahora. Los intentos contra el endpoint directo de Dukascopy desde GitHub Actions presentaron 503 y timeouts, por lo que no se debe bloquear el desarrollo del motor esperando M5.

La implementación continuará con los datos EURUSD disponibles en H1, H4 y D1. El código de detección de FVG/Order Block debe diseñarse de forma agnóstica al timeframe, pero toda afirmación específicamente M5 queda pendiente de validación posterior.

## Datos disponibles

| TF | Estado | Fuente | Rango observado | Uso |
|---|---|---|---|---|
| D1 | DISPONIBLE | ejtraderLabs/historical-data | 2012-12-04 → 2022-03-04 | contexto macro, estructura, OB/FVG HTF |
| H4 | DISPONIBLE | ejtraderLabs/historical-data | 2012-11-26 20:00 → 2022-03-04 20:00 | estructura HTF, FVG/OB |
| H1 | DISPONIBLE | ejtraderLabs/historical-data | 2012-11-16 00:00 → 2022-03-04 23:00 | desarrollo principal de FVG/OB |
| M5 | DEFERRED | Dukascopy / otras fuentes | no confirmado | pendiente de fuente estable |

## Canonicalización verificada

Los datos H1/H4/D1 entregados por el trabajo externo fueron convertidos de precios escalados (~×100000) a unidades de precio EURUSD. Se verificaron orden temporal y relaciones OHLC básicas. El Parquet requiere `pyarrow` para generarse.

## Archivos esperados localmente

```text
data/raw/EURUSD/EURUSD_H1.csv
data/raw/EURUSD/EURUSD_H4.csv
data/raw/EURUSD/EURUSD_D1.csv
data/raw/EURUSD/EURUSD_H1.parquet
data/raw/EURUSD/EURUSD_H4.parquet
data/raw/EURUSD/EURUSD_D1.parquet
data/metadata/EURUSD_H1_H4_D1.json
```

Los Parquet anteriores **no se consideran versionados en GitHub hasta que aparezcan en el árbol de `main`**. El pipeline reproducible para regenerarlos está en `tools/data/acquire_eurusd_higher_tf.py`.

## Restricciones

1. No usar H1/H4/D1 para afirmar que un algoritmo está validado específicamente en M5.
2. No mezclar fuentes/timeframes sin registrar fuente, escala, timezone y hash.
3. No introducir datos futuros en pruebas históricas.
4. No bloquear FVG/OB por ausencia de M5.
5. Cuando aparezca una fuente M5 estable, incorporarla como fase de datos separada y repetir validación de integridad.

## Objetivo inmediato

Completar el motor FVG/OB con H1/H4/D1:

`OHLC → estructura → FVG → Order Block → mitigación/invalidación → features → tests → backtest`.

M5 queda como **validación posterior**, no como dependencia del desarrollo actual.
