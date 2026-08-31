# SDD — Episodes / Funnel causal v1

**Estado:** NORMATIVO; implementación local revisada, pendiente únicamente de auditoría independiente y GO de publicación
**Fecha:** 2026-08-30
**Contrato:** `docs/contratos/CONTRATO_EPISODES_FUNNEL_V1.md`
**Padre:** `docs/planificacion/SDD_ENGINE_LIFECYCLE_MARKET_STATE_SETUP_BUILDER_V1.md`

## 1. Objetivo

Construir una capa de agrupación y auditoría sobre setups históricos ya
compuestos. La capa debe responder:

```text
qué setup existía en T,
por qué fue aceptado o rechazado,
qué episode representa,
qué linaje y temporalidad lo justifican,
y qué información futura queda separada como label.
```

## 2. Arquitectura autorizada

```text
engine/market_state.py
        │ projection_at(T)
        ▼
engine/setup_builder.py
        │ Setup(T), elegibilidad
        ▼
engine/episodes.py          ← única capa nueva de composición v1
        │ Episode + FunnelRecord
        ▼
audits/codigo/episodes.py   ← auditoría, no autoridad de cálculo
        ▼
reports/audits/episodes/    ← evidencia reproducible
```

`engine/episodes.py` no puede importar `backtest/`, no puede llamar a
`lifecycle.evaluate`, no puede avanzar `MarketState` y no puede recalcular AHF,
FVG/OB, relaciones ni Setup Builder.

La única fuente de candidatos es `build_setups_at(ms, T, ctx)`, que devuelve
`Setup` compuestos por `setup_builder`. El funnel no reimplementa la
composición ni la elegibilidad: deriva el estado del Episode directamente de
`Setup.eligibility` (`SetupEligibility` → `ACCEPTED`/`REJECTED`/`SUPERSEDED`).

## 3. Componentes

### 3.1 `Episode`

Debe contener `episode_id`, `canonical_setup_key`, `symbol`, `decision_time`,
`direction`, referencias a los cinco componentes del setup (sus `.id`),
temporalidades, estado (derivado de `SetupEligibility`), razones, lineage,
`contract_version` y metadatos de procedencia.

### 3.2 `FunnelRecord`

Debe conservar cada candidato y su etapa (`SNAPSHOT`, `SETUP`, `TEMPORAL`,
`LINEAGE`, `IDENTITY`, `DEDUPLICATION`, `EPISODE`) con `accepted`, `reason`,
`decision_time` y referencias de objetos.

### 3.3 Runner de auditoría

El runner debe producir un reporte JSON determinista con conteos por etapa,
dirección y TF; razones de rechazo; lineage; duplicados; provenance; checksum;
`aggregated_status`; y resultado FULL/PREFIX.

## 4. Pipeline causal

1. Leer configuración y manifiesto; validar identidad.
2. Obtener snapshots en una lista de decisiones T declarada.
3. Construir setups únicamente desde cada snapshot.
4. Validar tiempos, autoridad y lineage.
5. Formar la clave canónica y deduplicar de forma idempotente.
6. Crear el Episode aceptado o registrar el rechazo.
7. Separar cualquier outcome/label futuro del registro causal.
8. Agregar resultados sin borrar poblaciones ni ceros.
9. Repetir con FULL/PREFIX y comparar literalmente.

## 5. FULL/PREFIX

Para cada decisión T:

```text
FULL(snapshot_at(T)) == PREFIX(snapshot_at(T))
```

La comparación cubre `episode_id`, componentes, estados, tiempos, lineage,
razones, deduplicación, agregados y orden de registros. No se acepta comparar
solo conteos o checksum final. Una divergencia debe identificar campo, TF,
objeto, T y causa raíz.

## 6. Multiagentes y write sets

Los trabajos independientes se pueden paralelizar únicamente así:

| Dueño | Write set | Dependencia |
|---|---|---|
| D1 | contrato, SDD, índice, worklog | primero/último |
| D2 | `engine/episodes.py` y tests de dominio | después de E0 |
| D5 | `audits/codigo/episodes.py`, tests negativos y runner | junto a D2 si no comparte archivos |
| D7 | reportes, verificación y commit selectivo | después de D2/D5 |

Ningún agente crea otra versión de `Episode`, otro Funnel o una copia de
`MarketState`. La integración debe localizar la autoridad antes de fusionar.

## 7. Definition of Done

- contrato y SDD enlazados desde el índice y el arranque de Hermes;
- `engine/episodes.py` implementado sin mutaciones ni futuro;
- todos los candidatos y rechazos explicables;
- identidad y deduplicación deterministas;
- FULL/PREFIX literal PASS en la configuración declarada;
- tests focales, negativos y suite completa PASS;
- reporte con provenance, commit, configuración y checksum;
- bitácora, Graphify e índice actualizados;
- commit local selectivo, sin push automático;
- estado entregado como `COMPLETED` solo con todos los gates PASS.

## 8. Fuera de alcance

Resultado de trading, rentabilidad, optimización, entrenamiento, broker,
producción, CME/OI, descarga externa, cambio de dataset, Wyckoff-7 estadístico,
OTE y cualquier promoción.
