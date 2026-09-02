# Preregistro T7f — MTF Replay real, expansión 2006-2020

**Estado:** FROZEN_BEFORE_RUN
**Modo:** LOCAL_ONLY / investigación histórica / sin órdenes
**Perfil:** `INTRADAY_H4_M15`
**Ventana evaluada:** `[2006-01-01T00:00:00Z, 2021-01-01T00:00:00Z)` — 15 años, por año calendario
**Warmup no evaluado:** diciembre del año anterior (excepto 2006, sin warmup: no existe 2005-12)

## Objetivo

Extender el MTF Replay Orchestrator v1 (semilla T7d reproducida técnicamente,
con revisión documental pendiente) a la ventana completa 2006-2020, conservando
causalidad, autoridad y determinismo. Se evalúa la población de setups causales
por año; NO se mide edge como gate, no se optimiza ningún parámetro y no se
entrena IA. El resultado es un corpus de población causal reproducible, no una
promoción.

## Antecedentes

- T7d (enero 2025) es `PASS_TECHNICAL_REPRODUCED / REVIEW`; determinismo y
  gates se reprodujeron desde la punta, pero la certificación formal requiere
  un dictamen versionado con el commit exacto del generador.
- El veredicto OE7 declara explícitamente: NO suficiencia estadística (muestra
  mínima: 2 setups únicos × 2 decision_time = 4 episodios, 0 trades). T7f
  amplía la población para habilitar análisis posteriores, sin cambiar reglas.
- El usuario autorizó T7f explícitamente y ordenó descargar los datos M15
  faltantes (2011-2020) desde Dukascopy.

## Dataset congelado

Fuente: Dukascopy EURUSD spot bid M15, descargado con
`npx dukascopy-node -i eurusd -t m15 -p bid -f csv -v` (mensual).

| Dataset | Años | Archivos | Ubicación |
| --- | --- | ---: | --- |
| 2006-2010 | 2006-2010 | 60 | `datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/` |
| 2011-2020 | 2011-2020 | 120 | `datasets/eurusd_dukascopy_intraday_2011_2020/raw_monthly/` |

El manifiesto congelado de los 180 archivos (ruta, sha256, bytes) está en
`datasets/eurusd_dukascopy_intraday_2006_2020_manifest.json`:

- **SHA-256 del manifiesto:** `70328ea0976e2cf2ae2c960284c6033d2e8067f416bd439b2754332282ff18d1`
- **Total:** 180 archivos, ~19.3 MB, 373,794 filas M15 (2006-2010: 125,169 +
  2011-2020: 248,625).

El `dataset_hash` de cada run por año será SHA-256 del manifiesto ordenado
`ruta|sha256|bytes` de los archivos de ese año (12 archivos) + warmup (1
archivo del diciembre anterior, cuando exista). La fuente es Dukascopy EURUSD
spot bid M15 y se usa solo en el plano histórico de investigación. Su
licencia/permitted-use y `acquired_at_utc` no están establecidos: el gate
formal de procedencia permanece `BLOCKED_PROVENANCE`, aunque la integridad
mecánica pase.

## Transformación temporal congelada

- El `timestamp` del CSV representa la apertura del intervalo M15.
- La observación M15 ocurre únicamente en `timestamp + 15 minutos`.
- H4 se deriva de M15 con buckets UTC `[00:00,04:00)`, `[04:00,08:00)`, etc.
- Una barra H4 se observa solo al cierre del bucket; no usa valores posteriores.
- Los huecos de mercado se preservan; no se rellenan ni interpolan.
- Diciembre del año anterior se procesa como warmup; las métricas del año se
  cortan a `[YYYY-01-01, YYYY+1-01-01)`.
- 2006 no tiene warmup (no existe 2005-12); se declara y no se fabrica.

## Configuración congelada

- `symbol=EURUSD`
- `profile=INTRADAY_H4_M15`
- `checkpoint_every=250`
- `chunk_size=500`
- objetos: `engine.historical_event_objects.build_historical_event_objects`
  (DAG causal OB H4 → {FVG, BOS, displacement} M15) y `SetupBuilder` público;
  no se sustituye el productor por el feed H4 incompleto de T7 original
- ejecución: desactivada (`execution_plan_provider` no genera SL/TP)
- PIT estricto: `bar_time > tradable_time` (enmienda T7d, commit `dfa12b3`)
- lineage: POI sin `parent_object` (fix B5, commit `c99d00b`); BOS/displacement
  evidencias hermanas (enmienda H6, commit `de24d68`)

## Gates preregistrados (por año)

1. Hashes físicos contra manifiesto congelado, columnas, no nulos, OHLC,
   duplicados y monotonicidad: PASS.
2. Toda vela emitida es closed-only; H4 nunca aparece antes de su cierre: PASS.
3. FULL/PREFIX literal a 25/50/75/90 % sobre la ventana del año: PASS.
4. Dos runs idénticos por año: checksum lógico idéntico: PASS.
5. Artefacto schema 2.0 y manifiestos/chunks válidos: PASS.
6. Pico de memoria y tiempo se reportan; no se cambia el perfil tras observarlos.
7. Cero setups en un año es admisible solo si se declara
   `NO_COMPLETE_SETUP_POPULATION_H4_AUTHORITY_REPLAY` para ese año; no se
   relajan reglas para fabricar población.
8. Procedencia formal: `BLOCKED_PROVENANCE` hasta que existan licencia y fecha
   de adquisición; este estado no invalida la prueba mecánica local ni se
   convierte silenciosamente en PASS.
9. El corpus 2006-2020 se entrega como población causal reproducible; NO se
   interpreta como edge ni como autorización de trading.

## Prohibiciones

No buscar edge, seleccionar reglas, ajustar detectores, SL/TP o parámetros,
entrenar IA, usar MT5, enviar órdenes, descargar/reparar datos ni hacer push.
No ampliar la ventana ni seleccionar años por resultados.
