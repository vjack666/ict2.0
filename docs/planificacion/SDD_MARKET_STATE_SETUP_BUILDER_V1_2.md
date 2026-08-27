# SDD — Market State persistente + Setup State (v1.2)

**Estado:** NORMATIVO PARA IMPLEMENTACIÓN DIAGNÓSTICA (FASE 4)
**Fecha:** 2026-08-27
**Departamentos:** D2 Ingeniería, D4 Datos, D5 Assurance, D7 Delivery
**Autoridad:** `engine/` calcula; `backtest/` orquesta y serializa; el frontend solo representa.
**Base:** **EXTIENDE** `SDD_VISUAL_BACKTEST_WYCKOFF_V1_1.md` (v1.1, NORMATIVO). **NO LO REEMPLAZA.**

---

## 0. Declaración de extensión (FALTANTE 6)

Este SDD **EXTIENDE** el v1.1, **NO LO REEMPLAZA**. Todo lo normativo del v1.1
(contrato temporal, warmup, identidad, gates, invariantes) permanece vigente.
Este SDD añade la capa de **Market State persistente** y **Setup State** como
proyección del estado canónico existente.

**Autoridades (sin cambio):**
```text
engine/   = autoridad de cálculo
backtest/ = orquestación / serialización
viewer/   = representación (NO calcula reglas)
```

**No se permiten reglas ICT/Wyckoff nuevas dentro del frontend.**

---

## 1. Objetivo y límites

Evolucionar el replay Wyckoff v1.1 hacia un **Market State persistente + Setup
State**, sin reconstruir lo ya construido. El v1.1 produce **snapshots** por vela
(fuerza `range_id=None, episode_id=None`); el v1.2 añade **entidades vivas en T**
(MarketObjects con lifecycle) y **Setup State** (proyección del estado canónico
Context State/AHF).

El componente sigue siendo diagnóstico. No implementa reglas de estrategia, no
calcula edge, no entrena IA, no conecta brokers y no puede autorizar trading o
promoción. Invariantes (heredadas del v1.1):

```text
diagnostic_only=true
entry_authorized=false
can_trade=false
can_train=false
promotion_authorized=false
```

`ict_backtest/` no se importa ni se restaura.

## 2. Contrato temporal (heredado, sin cambios)

```text
bar_open_time  = source_time
bar_close_time = source_time + duración(tf)
decision_time  = bar_close_time de la vela principal
available_time = bar_close_time
```

Una fila solo participa cuando `bar_close_time <= decision_time`. `MqlRates.time`
= inicio del período (confirmado por MQL5). `TICK_VOLUME_PROXY` (EURUSD
no-exchange; `real_volume` = 0).

## 3. Principio arquitectónico definitivo (FALTANTE 1)

**NO estamos construyendo un segundo sistema.** Ya existen:

```text
MarketObject + lifecycle        engine/market_object.py
CausalLink / lineage            engine/lineage.py
Context State                   engine/mtf_navigation.py
AHF navigation                  engine/ahf.py
ICT structure                   engine/bos, engine/plan
Wyckoff runtime                 engine/Wyckoff/
MTFNavigator                    engine/mtf_navigation.py
decision_time / _closed_prefix  backtest/replay.py
Replay causal                   backtest/replay.py
Visor React                     backtest/viewer/
```

La nueva arquitectura es una **proyección** del estado canónico existente:

```text
ENGINE CANÓNICO EXISTENTE
│
├── MarketObject + lifecycle
├── CausalLink / lineage
├── Context State
├── AHF
├── ICT structure
└── Wyckoff runtime
        │
        ▼
REPLAY v1.1 EXISTENTE
        │
        ▼
PROYECCIÓN DEL ESTADO EN T
│
├── entidades vivas
├── lifecycle
├── source/origin TF
├── lineage
├── deltas
└── setup/navigation state
        │
        ▼
VISOR v1.1 EXTENDIDO
```

**NO**:
```text
motor viejo + nuevo motor duplicado
```

### 3.1 Cadena de autoridad (reconciliada con el grafo)

```text
MarketObject
    ↓
CausalLink / lineage
    ↓
Context State (engine/mtf_navigation)
    ↓
AHF (engine/ahf)
    ↓
Replay (backtest/replay)
    ↓
Market State visual (proyección)
```

**NO DUPLICACIÓN ARQUITECTÓNICA = PASS.**

## 4. Market State(T) — unidad real (FALTANTE 3)

Congelamos formalmente:

```text
MARKET STATE(T)
```

como:

> **conjunto causal de entidades y estados que el motor conocía y que seguían
> vigentes en `decision_time=T`.**

Debe incluir, cuando corresponda:

```text
MarketObjects vivos
Context State
AHF navigation state
ICT structure
Wyckoff snapshot
authority_tf
lineage
evidence refs
delta de entidades T-1→T
```

**No debe incluir información futura.**

### 4.1 Objetos terminales

Los objetos terminales (`MITIGATED`, `INVALIDATED`, `EXPIRED`, `CONSUMED`)
siguen disponibles como **historia** pero **ya no se dibujan como activos**.
Se conservan en el artifact para trazabilidad, pero el visor no los pinta como
entidades vigentes.

### 4.2 Regla fundamental

```text
MarketState(T) == resultado de información disponible hasta T
```

FULL vs PREFIX debe producir el mismo estado para T.

## 5. Setup State — NO segunda FSM (FALTANTE 2)

**El proyecto YA tiene la máquina de Setup**: Context State / AHF.

```text
WAIT_D1 → D1_LOCKED → WAIT_H4 → H4_LOCKED → WAIT_H1 → WAIT_LTF → SETUP_READY
```

**NO construimos una segunda máquina de Setup paralela.**

El futuro `setup_builder.py` (si sigue siendo necesario) es un:

```text
ADAPTER / PROJECTION / EXPLANATION
```

sobre el estado canónico existente (Context State/AHF). **NO** es una segunda
lógica de decisión. No recalcula las reglas de AHF; las **expone y explica**.

Debe poder responder:

```text
estado:        WAIT_LTF
active_tf:     M15
presentes:     D1 context, H4 POI, H1 process confirmation
faltantes:     LTF confirmation
invalidación:  ...
evidence_refs: ...
```

sin recalcular las reglas de AHF.

### 5.1 `backtest/setup_builder.py` (nuevo — ADAPTADOR, no FSM)

Responsabilidad:
- **Proyectar** el estado canónico de Context State/AHF al artifact.
- **Explicar** condiciones presentes/faltantes a partir del estado canónico.
- **NO** recalcular reglas de AHF ni crear una segunda FSM.

## 6. `backtest/market_state.py` (nuevo — EXTIENDE timeline/replay)

Responsabilidad:
- **Proyectar MarketObjects por vela**, reutilizando los que `engine/sequence.py`
  ya crea internamente (`_make_event_object`, `_build_expediente`) y exponiéndolos
  al artifact.
- Mantener un **Persistent Market State**: entidades vivas en T con lifecycle
  (`CREATED → ACTIVE → PARTIALLY_MITIGATED → MITIGATED/INVALIDATED/EXPIRED/CONSUMED`).
- Calcular **delta de entidades** (no solo de campos) entre T-1 y T.

Reutiliza: `engine/market_object.py` (ObjectState, _ALLOWED_TRANSITIONS,
to_dict/from_dict), `engine/sequence.py` (MarketObjects ya creados).

### 6.1 Semántica de lifecycle HTF/LTF (decisión contractual — FASE 4.1)

El replay v1.1 navega por la vela del `main_tf` (timeframe de ejecución). Una
zona FVG/OB con `origin_tf` D1/H4/H1/M15/M5/M1 puede cambiar su lifecycle
(ACTIVE → PARTIALLY_MITIGATED) por **contacto observado en la vela del `main_tf`**,
no requiere una vela de su propio `origin_tf`. Esta es la semántica intencional:
el `main_tf` es la lente de observación puntual; el `origin_tf` es el sello de
capa (dónde nació la zona), no una restricción de dónde se observa su mitigación.

Las transiciones terminales `MITIGATED / INVALIDATED / EXPIRED / CONSUMED` las
emite el **motor canónico** (`engine.detectors` / `engine.sequence`) dentro de
`ObjectState`; `market_state.py` las respeta y mueve el objeto a `terminal_entities`
(history). `market_state.py` NO inventa esas transiciones: es proyección pura. Por
tanto el lifecycle COMPLETO se observa en el artifact cuando los datos canónicos
lo producen; en muestras donde el motor solo alcanza PARTIALLY_MITIGATED, el
artifact refleja exactamente eso (dos estados), sin fabricar terminales.

### 6.2 Setup State = traducción de AHFSnapshot (decisión contractual — FASE 4.1)

`setup_builder.build_setup_state` es un **adaptador puro** del estado AHF canónico.
El replay instancia `engine.ahf.AdaptiveHierarchicalFunnel` una vez por run y
serializa cada `AHFSnapshot` en `timeline[i]["ict"]["context"]["ahf_snapshot"]`.
`setup_builder` traduce `AHFSnapshot.state / active_tf / confirmed_context /
history[-1].invalidation_reason` a Setup State. **No re-deriva la FSM**: elimina
cualquier lógica propia de transición (el `_derive_setup` previo se removió). El
test `test_setup_state_does_not_recompute_ahf` compara `SetupState(T)` contra
`AHFSnapshot(T)` punto a punto y falla si difieren.

### 6.3 Identidad determinista y FULL/PREFIX (decisión contractual — FASE 4.1)

El motor secuencial puede crear UUID de runtime para sus `MarketObject`. La
proyección read-only del replay los normaliza a una identidad estable derivada
de los campos causales del objeto, preservando `parent_object` y
`related_objects`. No se modifica la identidad interna del motor. Esto es
obligatorio para que el hash del artifact y la comparación FULL/PREFIX no
dependan de aleatoriedad de ejecución.

El gate `FULL == PREFIX` requiere dos artifacts generados con el mismo inicio,
configuración, datos y código, pero con un final PREFIX más corto. Se comparan
literalmente los snapshots `market_state` y `setups` en toda la intersección,
incluyendo `decision_time`, entidades vivas, historia terminal, delta y estado
AHF. Un único artifact o una prueba de ausencia de timestamps futuros no es
suficiente.

Si falla la ejecución del AHF canónico o falta un `AHFSnapshot`, el replay falla
cerrado y no fabrica un `Setup State` de fallback.

## 7. `backtest/schema.py` (cambios)

- `SCHEMA_VERSION` → **"1.2"**.
- Añadir campo **`market_state`** (entidades vivas en T) y **`setups`** (Setup
  State proyectado).
- Permitir `range_id`/`episode_id` en el snapshot Wyckoff (cuando el FSM
  persistente esté activo), manteniendo `RUNTIME_BASIC_NOT_WYCKOFF_7` como default.

## 8. `backtest/wyckoff_timeline.py` / `backtest/replay.py` (cambios)

- Proyectar MarketObjects por vela (delta de entidades, no solo de campos).
- Mantener `FSM_CONTRACT = "RUNTIME_BASIC_NOT_WYCKOFF_7"` (ver §10).

## 9. Visor `App.jsx` (cambios)

- Visualizar **regiones persistentes** (FVG/OB/rangos con lifecycle), no solo
  markers puntuales.
- Mostrar el **Setup State** (condiciones presentes/faltantes) como proyección
  del estado canónico.
- Cada entidad indica `origin_tf`, `authority_tf`, `role`, `parent/refinement`.
- El visor **NO calcula reglas**; solo representa el artifact.

## 10. WYCKOFF-7 boundary (FALTANTE 4)

Congelamos esta separación:

```text
WYCKOFF RUNTIME BASIC
→ disponible ahora (FSM_CONTRACT = RUNTIME_BASIC_NOT_WYCKOFF_7)

FSM DESCRIPTIVA WYCKOFF-7
→ puede construirse posteriormente (no bloqueada por datos)

PIT / causalidad
→ puede validarse independientemente

SUFICIENCIA ESTADÍSTICA / EDGE
→ bloqueada/insuficiente

TRAINING / TRADING
→ prohibido
```

**NO declaramos** "sin CME 6E/OI = imposible construir FSM descriptiva".

CME 6E/OI afecta la **calidad/evidencia de volumen** y futuras validaciones,
pero distingue claramente **implementación descriptiva** de **certificación
estadística**. La FSM descriptiva WYCKOFF-7 puede construirse sin CME 6E/OI;
lo que queda bloqueado es la validación estadística/edge que depende de volumen
centralizado + OI.

Para FASE 4 mantener:

```text
FSM_CONTRACT = RUNTIME_BASIC_NOT_WYCKOFF_7
```

salvo que un SDD canónico aprobado indique lo contrario.

## 11. Estado de fuentes externas (FALTANTE 5)

**ICT PRIMARY = PARTIAL** (episodios 6 y 16 del Mentorship 2022 no accedidos
directamente; cubiertos por fuente terciaria theinnercircletraders.com).

**Decisión**: este pendiente **DOES NOT BLOCK IMPLEMENTATION**. La arquitectura
necesaria ya está determinada por tesis + código canónico (Context State/AHF,
MarketObject, Wyckoff runtime). Un pendiente bibliográfico no debe frenar
artificialmente FASE 4. Se documenta como PARTIAL y se re-evalúa si se requiere
la fuente primaria exacta.

## 12. Contrato JSON v1.2

El artefacto contiene, como mínimo (heredado del v1.1 + nuevos):

- `schema_version`, `symbol`, `timeframe`, `authority_tf`;
- `visible_window` y `policy`;
- `candles`, `structure_events`, `trades`;
- `timeline` y `wyckoff_events`;
- **`market_state`** (nuevo): entidades vivas en T con lifecycle;
- **`setups`** (nuevo): Setup State proyectado con condiciones presentes/faltantes;
- `data_manifest`, `run_metadata` y `scientific_status`.

Cada entidad de `market_state` usa el contrato de `engine/market_object.py`
(id, type, origin_tf, role, direction, zone_high, zone_low, state, parent_object,
related_objects, candidate/confirmation/tradable, first_touch, invalidated,
mitigation_level, age_bars).

Cada setup de `setups` declara: id, dirección, cadena HTF→LTF, condiciones
presentes/faltantes, estado (READY/PENDING/INVALID), y refs a las entidades del
Market State que lo componen. **No recalcula reglas de AHF; las expone.**

## 13. Identidad y reproducibilidad (heredado)

`config_sha256`, `run_id`, `artifact_content_sha256` se calculan igual que v1.1.
El mismo commit, configuración y slices produce el mismo payload y hash.

## 14. Validación y gates

- **G0 Aislamiento:** worktree exclusivo, base `d562ac4`, write set congelado.
- **G1 Contrato:** este SDD cubre Market State, Setup State, schema 1.2.
- **G2 Timeline:** snapshot real por vela visible + entidades vivas en T.
- **G3 Causalidad:** FULL-vs-PREFIX idéntico y ningún `asof` futuro.
- **G4 Schema:** validación fail-closed, escritura atómica y hash determinista.
- **G5 Visor:** regiones persistentes + Setup State funcionales.
- **G6 Futuro invisible:** ninguna vela/entidad futura llega a series o DOM.
- **G7 Corrida real:** EURUSD M15, D1/H4/H1/M15/M5/M1, H1 autoridad, warmup 200.
- **G8 Seguridad:** no órdenes, IA, promoción, descargas ni mutación de datos.
- **G9 Cierre:** tests, build, QA visual, worklog, Graphify y commit local.

## 15. Write-set congelado para FASE 4 (FALTANTE 7)

Los únicos archivos que FASE 4 puede modificar/crear:

```text
backtest/market_state.py          (nuevo)
backtest/setup_builder.py         (nuevo, adaptador)
backtest/schema.py                (extender a 1.2)
backtest/wyckoff_timeline.py      (proyectar entidades)
backtest/replay.py                (orquestar proyección)
backtest/viewer/src/App.jsx       (regiones persistentes + Setup State)
backtest/viewer/src/*.jsx|*.css   (componentes del visor, solo representación)
tests/                            (tests nuevos de FASE 4)
docs/planificacion/SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md  (este SDD)
```

**NO se tocan**: `engine/` (solo lectura), `data/`, `datasets/`, `ict_backtest/`,
`runtime/ai_learning/`, `scripts/` (salvo tests), `governance/`.

## 16. Reglas absolutas (FASE 4)

```text
NO IA
NO TRAINING
NO PROMOTION
NO EDGE CLAIM
NO PERFORMANCE OPTIMIZATION
NO LIVE TRADING
NO CAMBIOS DE DATASET
NO LOOK-AHEAD
NO REGLAS EN FRONTEND
NO SEGUNDO MOTOR
NO SEGUNDA FSM DE SETUP
```

## 17. Criterio de DONE — FASE 4

FASE 4 termina cuando se puede detener el replay en cualquier instante T y
obtener:

```text
EURUSD — INSTANTE T

D1   └── POI #12 ACTIVE
H4   └── Liquidity #7 ACTIVE
H1   ├── Wyckoff (authority_tf=H1, Phase C) └── Range actual
M15  ├── CHOCH bullish └── FVG #31 PARTIALLY_MITIGATED
M5   └── OB #18 ACTIVE

AHF / SETUP STATE
D1_LOCKED, H4_LOCKED, H1_PASS, WAIT_LTF
Active TF: M15
Presentes: ... Faltantes: ... Conflictos: ...

CAMBIÓ DESDE T-1
FVG #31 ACTIVE → PARTIALLY_MITIGATED

FUTURO UTILIZADO: NO
```

Y el gráfico muestra únicamente lo que un trader podía tener legítimamente
dibujado en ese instante.
