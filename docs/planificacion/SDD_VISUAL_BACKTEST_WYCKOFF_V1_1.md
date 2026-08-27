# SDD — Visor causal ICT + Wyckoff v1.1

**Estado:** NORMATIVO PARA IMPLEMENTACIÓN DIAGNÓSTICA
**Fecha:** 2026-08-26
**Departamentos:** D2 Ingeniería, D4 Datos, D5 Assurance, D7 Delivery
**Autoridad:** `engine/` calcula; `backtest/` orquesta y serializa; el frontend solo representa.

## 1. Objetivo y límites

Construir un reproductor local vela cerrada por vela cerrada que consuma los
Parquet EURUSD existentes, llame a las APIs canónicas ICT y
`engine.Wyckoff.build_wyckoff_snapshot`, produzca `visual_backtest.json` v1.1 y
permita inspeccionar exactamente qué estaba disponible en cada
`decision_time`.

El componente es diagnóstico. No implementa reglas de estrategia, no calcula
edge, no entrena IA, no conecta brokers y no puede autorizar trading o
promoción. Son invariantes:

```text
diagnostic_only=true
entry_authorized=false
can_trade=false
can_train=false
promotion_authorized=false
```

`ict_backtest/` no se importa ni se restaura. La muestra visual externa es
referencia de interacción; su `sample.json`, el HTML histórico y el evento
demostrativo no son fuentes productivas.

## 2. Contrato temporal

Los Parquet actuales proceden de MetaTrader 5. El código de adquisición usa
`copy_rates_range` y el contrato operativo en `scripts/daily/brief_lunes.py`
declara que `time` representa la apertura de barra. Para esta misión el CLI
debe recibir explícitamente:

```text
--timestamp-semantics open
timezone=UTC
```

Para una fila de timeframe `tf`:

```text
bar_open_time  = source_time
bar_close_time = source_time + duración(tf)
decision_time  = bar_close_time de la vela principal
available_time = bar_close_time
```

Una fila solo puede participar cuando `bar_close_time <= decision_time`. Antes
de llamar al motor, el replay crea una copia normalizada con
`time=bar_close_time`; conserva `source_time`, `bar_open_time`,
`bar_close_time`, `source_index` y `timestamp_semantics` para trazabilidad. Si
el usuario declara `close`, `time` se conserva como cierre y se deriva la
apertura. Semánticas desconocidas fallan; nunca se infieren silenciosamente.

## 3. Warmup y ventana visible

El loader conserva al menos `warmup_bars` filas anteriores por cada TF. El
warmup alimenta los motores, pero no forma parte de `candles`, del timeline ni
del contador visible. El filtro visible se aplica después de cargar y
normalizar el warmup.

Por TF se registra ruta relativa, filas fuente/usadas/warmup/visibles, límites
temporales, SHA-256 del archivo y del slice, semántica temporal, zona horaria y
fuente de volumen. `tick_volume` se etiqueta `TICK_VOLUME_PROXY`; ausencia de
volumen se etiqueta `UNAVAILABLE`. Solo evidencia explícita permitiría
`REAL_EXCHANGE_VOLUME`.

## 4. Autoridades y flujo

```text
Parquet locales
  -> frontera temporal de backtest/replay.py
  -> engine.market_features.build_features
  -> engine.bos.structure.detect_market_structure
  -> engine.mtf_navigation.MTFNavigator
  -> engine.sequence.run_sequence
  -> engine.sequential_outcome.resolve_outcome
  -> engine.Wyckoff.build_wyckoff_snapshot
  -> visual_backtest.json v1.1
  -> backtest/viewer (solo lectura)
```

`backtest/wyckoff_timeline.py` puede construir prefijos cerrados, invocar APIs,
comparar snapshots y serializar; no clasifica fases, rangos, eventos,
alineación, conflicto, entradas ni outcomes.

## 5. Timeline Wyckoff

Para cada vela visible de la temporalidad principal:

1. calcular `decision_time` en el cierre;
2. obtener `asof_by_tf` de la última barra totalmente cerrada;
3. obtener el `MarketState` canónico con `MTFNavigator`;
4. construir prefijos cerrados por TF;
5. llamar a `build_wyckoff_snapshot` con `authority_tf` y `layers` explícitos;
6. serializar `snapshot.to_dict()` sin reinterpretación;
7. calcular un delta puramente observacional contra el snapshot anterior.

El delta puede describir cambios de `phase`, `phase_state`, `range_ref`,
`ict_alignment`, `conflict`, `volume_mode`, `authority_tf` y nuevos
`event_id`. No traduce cambios en señales.

La FSM vigente es básica. Cada snapshot exportado declara:

```json
{
  "range_id": null,
  "episode_id": null,
  "fsm_contract": "RUNTIME_BASIC_NOT_WYCKOFF_7"
}
```

## 6. Contrato JSON v1.1

El artefacto contiene, como mínimo:

- `schema_version`, `symbol`, `timeframe`, `authority_tf`;
- `visible_window` y `policy`;
- `candles`, `structure_events`, `trades`;
- `timeline` y `wyckoff_events`;
- `data_manifest`, `run_metadata` y `scientific_status`.

Cada vela usa índices visibles contiguos e incluye `source_index`, apertura,
cierre, `available_time` y OHLC. `visible_window` declara explícitamente
`warmup_bars`. Cada punto del timeline comparte el mismo índice y
`decision_time` que el cierre de su vela, y usa los nombres normativos
`ict.context`, `ict.visible_event_ids` y `wyckoff`. `asof_by_tf` nunca puede
ser futuro.

Los eventos estructurales solo son visibles desde `confirmed_index`. Si un
padre o formación está en el warmup, se conserva su ID fuente en un campo
`source_parent_id`/`source_formation_index`, mientras el enlace visible queda
nulo y marcado `outside_visible_window`; no se inventa una ubicación.

Los eventos Wyckoff preservan el `engine_event_id` y registran
`first_seen_decision_time`. Su envolvente se deriva de
`tf + event_type + event_time + source_ref`, sin UUID ni tiempo de ejecución.

Cada entrada del manifiesto usa `relative_source_path`, límites explícitos de
fuente, uso, warmup y ventana visible, `last_asof_available`, conteos y hashes.
`run_metadata` declara commit, branch, limpieza previa del worktree, versiones
de Python/Node, configuración, lineage del motor y comando normalizado.

Una operación existe desde `entry_index`; salida, outcome y métricas solo se
muestran en el visor cuando `result_confirmed_index <= cursor`.

## 7. Identidad y reproducibilidad

`config_sha256` se calcula sobre configuración ordenada. `run_id` se deriva de
commit, configuración y hashes de slices. `artifact_content_sha256` se calcula
sobre el payload canónico excluyendo el propio campo de hash y el lineage
operacional volátil (`git_branch`, limpieza del worktree y versiones de
Python/Node). Esos campos siguen visibles y validados, pero no alteran la
identidad científica. No se incluyen hora de generación, rutas absolutas ni
duración en la identidad.

El mismo commit, configuración y slices debe producir el mismo payload y hash.

## 8. Visor

El frontend React/Vite mantiene el lenguaje visual de la muestra: fondo oscuro,
gráfico dominante, sidebar de capas, barra superior de estado, inspector y
`NO TRADING` persistente. Usa `lightweight-charts` y Phosphor Icons.

La librería gráfica recibe solo `candles[0:cursor+1]`; no se carga el futuro y
no se confía en ocultarlo con viewport. Swing/BOS/CHOCH, eventos Wyckoff y
resultados se filtran por sus tiempos de disponibilidad. El visor ofrece
reinicio, anterior, siguiente, play/pausa, 1x/2x/4x, slider, selector temporal,
capas, carriles MTF, delta y evidencia. Debe ser usable con teclado, focus
visible, ARIA y `prefers-reduced-motion`.

## 9. Servidor local

`scripts/serve_visual_backtest.py` sirve exclusivamente el build estático y un
run seleccionado, enlaza por defecto a `127.0.0.1`, no expone rutas de escritura
y rechaza path traversal. No existe despliegue público.

## 10. Validación y gates

- **G0 Aislamiento:** worktree exclusivo, base `6a653d0`, write set congelado.
- **G1 Contrato:** este SDD cubre apertura/cierre, warmup, schema y autoridad.
- **G2 Timeline:** snapshot real por vela visible.
- **G3 Causalidad:** FULL-vs-PREFIX idéntico y ningún `asof` futuro.
- **G4 Schema:** validación fail-closed, escritura atómica y hash determinista.
- **G5 Visor:** gráfico, controles, capas, carriles y evidencia funcionales.
- **G6 Futuro invisible:** ninguna vela/entidad futura llega a series o DOM.
- **G7 Corrida real:** EURUSD M15, D1/H4/H1/M15/M5/M1, H1 autoridad,
  warmup 200 y cinco días comunes.
- **G8 Seguridad:** no órdenes, IA, promoción, descargas ni mutación de datos.
- **G9 Cierre:** tests, build, QA visual, worklog, Graphify y commit local.

El PASS PIT previo prueba consistencia temporal de su muestra; `515 < 778`
mantiene factibilidad estadística insuficiente. El visor no prueba edge y no
completa WYCKOFF-7.
