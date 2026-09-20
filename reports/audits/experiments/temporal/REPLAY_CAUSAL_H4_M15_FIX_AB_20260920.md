# Informe de corrección — Replay causal H4/M15 (2026-09-20)

**Alcance:** piloto histórico EURUSD H4/M15, productor canónico `engine.historical_event_objects`, `MarketState` y lifecycle REALES. No certifica D1/H1/M5/M1, secuencias completas, funnel, episodios, GRU ni MT5.

## Causa raíz y cambio de código

1. **Padre e hijo confirmados en el mismo cierre:** `build_historical_event_objects` aceptaba un OB H4 con `tradable_time <= event_time` como padre de BOS/desplazamiento/FVG M15. A las 04:00 UTC del 2026-09-02 aparecía un vínculo simultáneo no demostrado. El productor ahora exige `tradable_time < event_time` en sus tres caminos de relación. **No se modificó la guarda del replay** ni se inventó un padre. El desplazamiento sin padre anterior elegible ya no se publica como objeto *vinculado*; sigue siendo una ocurrencia del inventario de detectores por separado. A cambia de 29 a **28** MarketObjects H4/M15 vinculados o POI (padres 9→8); B conserva 26/6.

2. **Metadatos futuros en `MarketState.projection_at(T)`:** copiar el objeto vivo y restaurar solo `state` filtraba `invalidated_time`, `touch_count`, `first_touch_time` y metadatos posteriores. Se añadió `_snapshots` disperso: snapshot profundo al nacimiento y cuando cambian atributos observables (incluyendo toque y CE sin cambio de estado). `projection_at(T)` devuelve la última versión íntegra con sello <=T; SAVE/LOAD conserva la serie mediante `object_snapshots`. **Checkpoints antiguos sin esta serie no pueden reconstruir atributos pasados**: falla explícitamente `NO_CAUSAL_METADATA_HISTORY` y se requiere regeneración desde velas; no se fabrican metadatos.

## Pruebas ejecutadas ANTES de publicar

- `python -m pytest -q tests/test_causal_replay.py tests/test_market_state.py tests/test_causal_replay_regressions.py`: **18 passed**, sin fallos. Pruebas nuevas negativas para simultaneidad, checkpoint legado, metadatos de toque/invalidación, SAVE/LOAD y padres anteriores.
- `python -m compileall -q` sobre los cuatro archivos modificados/nuevos: PASS.
- Datos: `EURUSD.zip` suministrado por Rubén; SHA256 de los seis CSV seleccionados coincide **6/6** con el manifiesto del benchmark en GitHub. Solo H4 y M15 se **procesaron** en este piloto. Cada control procesó **515 H4** y **1.439 M15**; CSV `time` de apertura convertido a hora de cierre (H4 +4h; M15 +15min).
- Ejecución A: **28 MarketObjects**, 8 con padre; 20 INVALIDATED, 1 PARTIALLY_MITIGATED, 7 ACTIVE; 1.036 observaciones de lifecycle.
- Ejecución B: **26 MarketObjects**, 6 con padre; 20 INVALIDATED, 1 PARTIALLY_MITIGATED, 5 ACTIVE; 1.318 observaciones de lifecycle.
- FULL/PREFIX: **seis cortes temporales reales por control**; 12/12 comparaciones de productor y 12/12 comparaciones de proyección completa (incluidos metadatos y `meta`) iguales. Sin fechas de invalidación futuras en esas consultas. Comparación SAVE/LOAD y reordenación de entrada: PASS ambos controles.
- Future injection con velas posteriores REALES: **2** velas adicionales en A y **102** en B; ninguna alteró los objetos o las proyecciones al instante de decisión. La prueba de A tiene poco futuro disponible; no extrapolar a seis TF.
- Código probado en carpeta temporal reconstruida exclusivamente desde el repositorio conectado; Git blob SHA de archivos publicados coinciden con los archivos ejecutados: `engine/market_state.py` = `903891f4c90fbbc0f3a2bc32f43e458b600d19d0`, `engine/historical_event_objects.py` = `021fadad36b92df7ed3a9773b2a5e64b8cf1d84b`, test = `cff4182f21db0f5e2fa2b3633daee602f2a2f3ed`, verificador = `b80baa22bc8a82d0168ac334d1bd8ca691319c1e`.

**Limitación del entorno:** la carpeta temporal contenía solo los módulos necesarios; para ejecutar el CLI se usó un sustituto de lectura de datos de `read_source`/`verify_sha256_manifest` equivalente a las funciones del inventario de GitHub. No se sustituyó `MarketState`, lifecycle ni el productor. El verificador `scripts/audit/verify_causal_replay_ab.py` y el original `run_causal_replay.py` fueron probados en ese entorno; Hermes debe repetir en el ORIGINAL completo de Windows. **No se corrió aquí toda la suite del repositorio.**

**Evidencia detallada:** JSON generado `verified_AB.json`, SHA256 `c0bb697fe8a3324ca63f92973f114b423aa5aec4b6a399387578e4551f9c8d91`, 12 cortes con métricas por control (entrega como artefacto de esta conversación, no incluye el ZIP de datos). El verificador está publicado para reproducir las métricas en Windows.

## Dictamen y límites

**PASS únicamente del piloto causal H4/M15 A/B y las regresiones de metadatos; cambios publicados en rama aislada `gpt/ict-causal-replay-20260920`.** No hay merge autorizado a `main` ni a PR #14/#15; pruebas de toda la suite de Windows y revisión Hermes/Vigil siguen pendientes. El inventario 154/582 no equivale a los 28/26 objetos de este productor; no son secuencias, entradas ni episodios. Pendiente: calendario broker H4/D1, contexto seis TF, lineage ICT completo, funnel, episodios y GRU.
