# Auditoria — fabrica seis-TF vs conexion al motor real

**Fecha:** 2026-09-21  
**Modo:** `LOCAL_ONLY`  
**Rama:** `preservation/before-lineage-hierarchical-integration-20260921`  
**Dictamen:** `FACTORY_SIXTF_CONTEXT_EXISTS / CONNECTION_TO_REAL_EPISODES_PENDING`

## Pregunta auditada

Ruben observa que la "fabrica" probablemente ya esta creada y que puede faltar
solo la conexion. La auditoria verifica si eso es correcto.

## Resultado ejecutivo

Si: la observacion es correcta en lo esencial.

No falta construir desde cero una fabrica seis-TF. Ya existe una capa/fabrica de
contexto y features que carga y navega:

```text
D1 -> H4 -> H1 -> M15 -> M5 -> M1
```

Lo que falta no es el contexto seis-TF, sino conectarlo al motor canonico de:

```text
MarketObject -> HierarchicalLineage -> SetupBuilder -> Episodes/Funnel
```

## Evidencia de fabrica seis-TF existente

- `scripts/lab/experiments/v2_extractor_engine.py`
  - Declara `TIMEFRAMES = ("D1", "H4", "H1", "M15", "M5", "M1")`.
  - Carga los seis marcos con `load_frames("EURUSD", TIMEFRAMES, ...)`.
  - Usa `MTFNavigator` con `exec_tf="M15"`.
  - Genera filas con `features_at_t`, `engine_snapshot`, `M5`, `M1`,
    `can_trade=false`, `shadow_mode=true` y `diagnostic_only=true`.
  - Limite observado: su payload marca `lineage: {"available": False, ...}`.

- `engine/multitf_context.py`
  - Define contexto por barra `D1 -> H4 -> H1 -> M15 -> M5 -> M1`.

- `engine/mtf_navigation.py`
  - Implementa `MTFNavigator` y `TimeframeLayer` con D1/H4/H1/M15/M5/M1.
  - Navega el contexto point-in-time y produce `MarketState`/constraints de
    contexto, no episodios finales.

- `engine/ahf.py`
  - Contiene maquina AHF con estados D1/H4/H1/LTF y usa M15/M5 como LTF
    disponible.

## Evidencia del hueco de conexion

- `engine/historical_event_objects.py`
  - Es el productor historico real de `MarketObject`.
  - Requiere explicitamente `H4` y `M15`; si faltan lanza
    `MISSING_LAYER: H4 and M15 are required`.
  - Produce OB H4 y FVG/BOS/displacement M15 con `parent_object`.
  - No produce aun el grafo completo D1/H4/H1/M15/M5/M1.

- `engine/detector_event_bridge.py`
  - Acepta seis temporalidades (`D1`, `H4`, `H1`, `M15`, `M5`, `M1`).
  - Convierte ocurrencias confirmadas en `MarketObject`.
  - Declara explicitamente que no infiere ICT lineage, lifecycle ni trade
    eligibility.
  - Publica objetos con `lineage_status=UNRESOLVED` y
    `lifecycle_status=NOT_REPLAYED`.

- `engine/setup_builder.py`
  - Ya espera `MarketObject` relacionados por `parent_object` o
    `related_objects`.
  - Puede componer setups si recibe POI/refinement/confirmation/trigger y
    contexto HTF.

- `engine/episodes.py`
  - Ya consume setups y valida temporalidad/lineage; no debe fabricar padres.

## Correccion del dictamen anterior

Dictamen anterior demasiado general:

```text
PRODUCER_SIXTF_PENDING
```

Dictamen corregido:

```text
FACTORY_SIXTF_CONTEXT_EXISTS
PRODUCER_MARKETOBJECT_REAL_SCOPE=H4_M15
CONNECTION_TO_REAL_EPISODES=PENDING
```

## Trabajo siguiente correcto

No crear otra fabrica paralela. Conectar y promover la fabrica seis-TF existente:

```text
v2_extractor_engine / multitf_context / MTFNavigator
  -> productor MarketObject seis-TF
  -> parent_object / related_objects causal
  -> HierarchicalLineage(require_all_six_tfs=True)
  -> build_setups_at()
  -> build_episodes()
  -> backtest/dataset/IA shadow sobre episodios reales
```

## No-go preservados

- No MT5.
- No trading.
- No fabricacion de M1 posterior al dato real.
- No nueva rama.
- No declarar edge.
- No entrenar modelo productivo.
