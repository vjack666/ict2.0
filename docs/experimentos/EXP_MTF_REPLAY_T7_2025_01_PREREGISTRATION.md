# Preregistro T7 — MTF Replay real, enero de 2025

**Estado:** FROZEN_BEFORE_RUN
**Modo:** LOCAL_ONLY / investigación histórica / sin órdenes
**Perfil:** `INTRADAY_H4_M15`
**Ventana evaluada:** `[2025-01-01T00:00:00Z, 2025-02-01T00:00:00Z)`
**Warmup no evaluado:** diciembre de 2024

## Objetivo

Verificar que el MTF Replay Orchestrator v1 procesa un mes real de EURUSD M15,
deriva H4 de forma cerrada, conserva causalidad y autoridad, produce un
artefacto schema 2.0, chunks para el visor y evidencia reproducible con recursos
acotados. No se mide edge como gate, no se optimiza ningún parámetro y no se
entrena IA.

## Dataset congelado

| Uso | Archivo | SHA-256 | Filas |
| --- | --- | --- | ---: |
| warmup | `datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly/2024/eurusd-m15-bid-2024-12-01-2025-01-01.csv` | `bce883373218e4ca20ac7092422d9893edbe346b96c44cbe5a3d13c172c80c6e` | 1587 |
| evaluación | `datasets/eurusd_dukascopy_intraday_2021_2025/raw_monthly/2025/eurusd-m15-bid-2025-01-01-2025-02-01.csv` | `c62b93557bb0a61b69c63af6618368b51878a1aa7299d99e06abafd815fe0cf6` | 2112 |

El `dataset_hash` del run será SHA-256 del manifiesto ordenado
`ruta|sha256|bytes|filas`. La fuente es Dukascopy EURUSD spot bid M15 y se usa
solo en el plano histórico de investigación. Su licencia/permitted-use y
`acquired_at_utc` no están establecidos: el gate formal de procedencia permanece
`BLOCKED_PROVENANCE`, aunque la integridad mecánica pueda pasar.

## Transformación temporal congelada

- El `timestamp` del CSV representa la apertura del intervalo M15.
- La observación M15 ocurre únicamente en `timestamp + 15 minutos`.
- H4 se deriva de M15 con buckets UTC `[00:00,04:00)`, `[04:00,08:00)`, etc.
- Una barra H4 se observa solo al cierre del bucket; no usa valores posteriores.
- Los huecos de mercado se preservan; no se rellenan ni interpolan.
- Diciembre se procesa como warmup, pero las métricas T7 se cortan a enero.

## Configuración congelada

- `symbol=EURUSD`
- `profile=INTRADAY_H4_M15`
- `checkpoint_every=250`
- `chunk_size=500`
- objetos: ensamblador público `engine.ltf_canonical_feed.build_canonical_objects`
- ejecución: desactivada (`execution_plan_provider` no genera SL/TP)

## Gates preregistrados

1. Hashes físicos, columnas, no nulos, OHLC, duplicados y monotonicidad: PASS.
2. Toda vela emitida es closed-only; H4 nunca aparece antes de su cierre: PASS.
3. FULL/PREFIX literal a 25/50/75/90 % sobre la ventana evaluada: PASS.
4. Dos runs idénticos y chunk sizes 500/257: checksum lógico idéntico: PASS.
5. Artefacto schema 2.0 y manifiestos/chunks válidos: PASS.
6. Pico de memoria y tiempo se reportan; no se cambia el perfil tras observarlos.
7. Cero setups es admisible solo si se declara `NO_COMPLETE_SETUP_POPULATION`:
   el ensamblador público actual produce FVG/OB, no inventa BOS/displacement.
8. Procedencia formal: `BLOCKED_PROVENANCE` hasta que existan licencia y fecha de
   adquisición; este estado no invalida la prueba mecánica local ni se convierte
   silenciosamente en PASS.

## Prohibiciones

No buscar edge, seleccionar reglas, ajustar detectores, SL/TP o parámetros,
entrenar IA, usar MT5, enviar órdenes, descargar/reparar datos ni hacer push.
