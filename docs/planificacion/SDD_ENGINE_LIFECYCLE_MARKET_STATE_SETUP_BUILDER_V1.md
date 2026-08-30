# SDD — Engine Lifecycle → Market State → Setup Builder v1

**Estado:** NORMATIVO para el motor canónico de `ICT SYSTEM`
**Fecha de consolidación:** 2026-08-30
**Departamentos:** D1 Documentación, D2 Ingeniería, D5 Assurance, D7 Delivery
**Autoridad:** `engine/` calcula; `audits/` verifica; `backtest/` (si se usa) consume y proyecta; el visor solo representa.
**Antecedentes:** consolida Lifecycle v1, MarketState v1 y Setup Builder revisado después del cierre técnico A7.

---

## 0. Propósito y regla de precedencia

Este documento une en una sola referencia operativa la misión posterior a A7:

```text
MarketObject + detector
        ↓
Lifecycle causal por objeto
        ↓
MarketState histórico por instante T
        ↓
Setup Builder de solo lectura
        ↓
Episodes / Funnel (siguiente fase)
```

La tesis ICT, sus contratos y `AGENTS.md` tienen precedencia sobre este SDD si
aparece un conflicto. Este SDD no crea una nueva teoría ICT ni autoriza trading.

El archivo histórico `SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md`, creado en la rama
del visor `codex/visual-replay-wyckoff-v1-1`, describe una proyección diagnóstica
de `backtest/`. No es autoridad para cambiar `engine/` en la rama operativa.
No se debe copiar su semántica de observación si contradice este contrato.

## 1. Alcance y no-objetivos

### Incluido

- identidad, temporalidad, autoridad y linaje de `MarketObject`;
- transición causal y auditable del lifecycle;
- historial append-only y snapshots `MarketState` as-of-T;
- persistencia `to_dict`/`from_dict` y continuación determinista;
- composición de `Setup` desde una proyección histórica;
- separación entre estado físico del objeto y elegibilidad del setup;
- pruebas de causalidad, idempotencia, temporalidad y FULL/PREFIX;
- preparación documental de la fase Episodes/Funnel.

### Prohibido en esta misión

- órdenes, broker, `can_trade`, promoción o producción;
- afirmar edge, rentabilidad o suficiencia estadística;
- entrenar IA o ejecutar backtests de rendimiento;
- crear un segundo motor de detección o una segunda FSM de setup;
- introducir OTE, Fibonacci 62–79% o reglas no presentes en la tesis;
- modificar datasets para obtener un resultado favorable;
- usar `backtest/` como autoridad del motor diario.

## 2. Autoridad documental y de código

| Capa | Fuente | Responsabilidad |
|---|---|---|
| Tesis | `docs/ict/` y `docs/reglas/` | Significado ICT y límites metodológicos |
| Contratos | `docs/contratos/` | Interfaces, invariantes y gates |
| Diseño | Este SDD + `SDD_CONTEXT_STATE_MTF_NAVIGATION.md` + §13 de `SDD_FVG_OB_ENGINE.md` | Arquitectura vigente |
| Motor | `engine/market_object.py`, `engine/lifecycle.py`, `engine/market_state.py`, `engine/setup_builder.py` | Cálculo canónico |
| Assurance | `audits/`, `tests/` | Evidencia y verificación independiente |
| Operación | `.hermes-index.md`, `.hermes-worklog/`, `.hermes/plans/` | Estado ocurrido y siguiente misión |

`Graphify` sirve para navegación y relaciones. No certifica, no decide
autoridad y no reemplaza Git, contratos, tests ni la bitácora.

## 3. Contrato temporal multi-timeframe

Cada objeto conserva al menos:

```text
origin_tf       = temporalidad donde nace
authority_tf    = temporalidad que puede cambiar su estado oficial
lifecycle_tf    = temporalidad usada para evaluar lifecycle
observation_tf  = temporalidad que puede aportar observación subordinada
candidate_time  = candidato detectable
confirmation_time = confirmación causal
tradable_time   = momento desde el que puede ser usado por un consumidor
```

En Lifecycle v1, el contrato congelado es:

```text
authority_tf == lifecycle_tf == origin_tf
```

Un objeto H4 puede ser usado como contexto para una decisión M15, pero una vela
M15 no puede invalidarlo ni cambiar su `first_touch`, `touch_count` o estado
oficial. M15 puede registrarse en `meta["observations"]["M15"]` mediante la API
de observación, sin contaminar la historia oficial de H4.

Reglas obligatorias:

1. Solo velas cerradas y con tiempo disponible `<= decision_time` participan.
2. La autoridad debe coincidir con la autoridad firmada en el objeto; si no,
   la operación falla cerrada.
3. Una barra de otra TF no puede disfrazarse de la TF autorizada.
4. Un evento fuera de orden se rechaza; el motor no reescribe el pasado.
5. El snapshot de T solo puede contener datos observables hasta T.

## 4. Lifecycle de `MarketObject`

La única autoridad para transicionar FVG/OB es `engine/lifecycle.py`. Los
detectores crean objetos; `relations.py` relaciona; `MarketState` registra y
proyecta; `setup_builder.py` lee. Ninguno de los consumidores debe mutar
`object.state` directamente.

Estados:

```text
CREATED → ACTIVE → PARTIALLY_MITIGATED → MITIGATED
    └──────────────→ INVALIDATED
```

- `PARTIALLY_MITIGATED`: penetración real en la zona.
- `MITIGATED`: el precio recorre la zona hasta el `far_side`; en v1 no es
  terminal porque puede existir invalidación posterior.
- `INVALIDATED`: cierre de una vela de `authority_tf` más allá del `far_side`.
- `EXPIRED` y `CONSUMED` existen en el vocabulario, pero están deshabilitados
  como decisiones automáticas de v1 salvo contrato posterior explícito.
- Precedencia: si se cumplen fill completo y cierre invalidante, gana
  `INVALIDATED`.

La misma barra reprocesada debe ser idempotente. La deduplicación se hace por
identidad de objeto, TF, tiempo/índice de vela y tipo de evento. Una observación
LTF repetida tampoco puede duplicarse.

## 5. `MarketState(T)` event-sourced

`engine/market_state.py` mantiene el universo de objetos y una historia
append-only de transiciones. La API conceptual es:

```text
ingest(obj)                 → registra nacimiento una sola vez
advance_bar(obj_id, bar)    → evalúa autoridad o registra observación
history_of(obj_id)          → devuelve copia de la historia
state_at(obj_id, T)         → estado conocido hasta T
projection_at(T)            → copias profundas congeladas en T
snapshot_at(T)              → universo + historial relevante + reloj
to_dict/from_dict           → SAVE → LOAD → CONTINUE
```

Invariantes:

- `projection_at(T)` no devuelve referencias vivas del presente;
- avanzar el motor después de T no modifica el snapshot histórico de T;
- objetos nacidos después de T no aparecen en T;
- terminales permanecen como historia, pero no como activos;
- el orden de procesamiento por TF se conserva y los eventos atrasados fallan
  cerrado;
- el round-trip serializado conserva objetos, autoridad, observaciones,
  transiciones y relojes.

## 6. Setup Builder

`engine/setup_builder.py` es una capa de composición de solo lectura. No es una
FSM paralela y no ejecuta Lifecycle. Su cadena canónica es:

```text
context_htf → poi(OB) → refinement(FVG) → confirmation(BOS) → trigger(DISPLACEMENT)
```

`build_setups_at(ms, T, ctx)` debe consumir exclusivamente
`ms.projection_at(T)`, nunca `ms.active()` del presente. La elegibilidad del
setup es distinta de `MarketObject.state`:

```text
ELIGIBLE | BLOCKED | OUT_OF_CONTEXT | SUPERSEDED
```

Condiciones mínimas:

- POI y refinement activos dentro del snapshot T;
- relación FVG↔OB causal, estricta y de misma dirección;
- contexto HTF disponible y alineado;
- confirmation y trigger presentes cuando se exige setup completo;
- POI invalidado produce `SUPERSEDED`, no un setup elegible;
- ningún objeto referenciado cambia de estado por construir el setup.

## 7. FULL/PREFIX y determinismo

Para cada instante de decisión T, la comparación correcta es literal:

```text
FULL(data hasta el final).snapshot_at(T)
==
PREFIX(data truncado después de T).snapshot_at(T)
```

La igualdad debe cubrir objetos, estados, historia, observaciones permitidas,
linaje, autoridad, ids, setups, elegibilidad, decisiones y deltas. No basta con
comprobar que no existen timestamps futuros ni con comparar un solo resumen.

El resultado debe ser reproducible con el mismo código, configuración, bytes de
entrada y ventana. UUID de runtime no puede ser la identidad de una evidencia
comparada; cualquier proyección que necesite ids estables debe derivarlos de
campos causales sin alterar la identidad interna del motor.

## 8. Estado auditado de la implementación actual

| Componente | Evidencia actual | Clasificación |
|---|---|---|
| MarketObject + autoridad TF | `engine/market_object.py` + `tests/test_market_object_pd_contract.py` | Implementado |
| Lifecycle único | `engine/lifecycle.py` + `tests/test_lifecycle.py` | Implementado/revisado |
| MarketState causal | `engine/market_state.py` + `tests/test_market_state.py` | Implementado |
| Setup Builder | `engine/setup_builder.py` + 4 suites focales | Implementado/promovido con revisión |
| Funnel A7 | `audits/codigo/mtf_seq_funnel_a7.py` + SDD A7 | Técnico completado; no demuestra edge |
| Episodes/Funnel de setups | no existe módulo canónico en `engine/` | Siguiente fase, no iniciado |

El estado de implementación no equivale todavía a certificación científica ni
a autorización operativa.

## 9. Gates de cierre de esta capa

| Gate | Pregunta | Evidencia mínima |
|---|---|---|
| G1 Autoridad | ¿Cada transición usa la TF correcta? | tests de rechazo cruzado |
| G2 Lifecycle | ¿Las transiciones son válidas, terminales e idempotentes? | `test_lifecycle.py` + negativos |
| G3 Observación | ¿LTF no altera estado oficial HTF? | observaciones separadas en `meta` |
| G4 Persistencia | ¿SAVE→LOAD→CONTINUE conserva el mundo? | `test_market_state.py` |
| G5 As-of-T | ¿El pasado queda congelado? | `projection_at/snapshot_at` |
| G6 Setup | ¿Composición y elegibilidad son solo lectura? | 4 suites de Setup Builder |
| G7 FULL/PREFIX | ¿La igualdad es literal y completa? | runner con múltiples T y corpus |
| G8 Documentación | ¿Índice, SDD, plan y worklog coinciden? | revisión D1/D5 + Git |

Un gate no demostrado queda `REVIEW` o `BLOCKED`; no se convierte en PASS por
inferencia ni cambiando el criterio después de ver el resultado.

## 10. Siguiente misión: Episodes / Funnel

La siguiente fase no debe rehacer Lifecycle, MarketState ni Setup Builder.
Debe agrupar setups ya compuestos en episodios causales para análisis posterior.

Objetivo de entrada:

```text
MarketState(T) + Setup(T)
        ↓
Episode causal con identidad, ventana, estado, lineage y resultado descriptivo
        ↓
Funnel auditable por etapa y motivo de rechazo
```

Antes de programar esa fase, Hermes/Codex deben producir o actualizar su
contrato específico. El nuevo módulo no puede mutar `MarketObject`, recalcular
Lifecycle, usar futuro, convertir un setup en orden ni reclamar edge.

Write set inicial propuesto, pendiente de aprobación del plan Episodes:

```text
engine/episodes.py
audits/codigo/episodes.py
tests/test_episodes.py
docs/contratos/CONTRATO_EPISODES_FUNNEL.md
docs/planificacion/SDD_EPISODES_FUNNEL_V1.md
reports/audits/episodes/   (artefactos generados, no código)
```

No se debe crear `engine/episodes.py` hasta que el contrato, el SDD y los gates
de la fase estén congelados.

## 11. Cierre de la reconciliación

Esta consolidación corrige la divergencia documental entre la rama del visor y
la rama operativa. La implementación actual se audita contra `engine/`; el SDD
v1.2 histórico de `backtest/` queda como antecedente técnico, no como permiso
para duplicar el motor. El próximo cambio de código autorizado es Episodes /
Funnel, después de su SDD y contrato propios.
