# DISEÑO — WyckoffRange persistente (WYCKOFF-7) en ICT 2.0

**Tipo:** ESPECIFICACIÓN / DISEÑO (no código)
**Fase destino:** POST FASE 4.2 (el cliente decidió WYCKOFF-7 *después* de FASE 4.2)
**Autoridad que extiende:** `SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md` (v1.2, NORMATIVO)
**Grafo de trazabilidad:** `graphify-out/graph.json` (built_at_commit = `c1328ad`, idéntico a HEAD actual)
**Regla de este documento:** diseña la entidad `WyckoffRange`; **NO modifica** `engine/` ni `backtest/`; no entrena IA ni backtests.

---

## 0. Resumen ejecutivo

`WyckoffRange` es una **entidad persistente de proyección** (hermana de `MarketObject`, no una segunda FSM) que agrega a lo largo del tiempo los `WyckoffSnapshot` canónicos que comparten un `range_id`. Tiene dos ejes ortogonales:

1. **Eje de fase estructural A–E** — avanza por *eventos observados* del motor Wyckoff canónico (`Spring`, `Test`, `SOS`, `LPS`), modelados como **transiciones de estado**, no como reglas de señal.
2. **Eje de lifecycle** — reutiliza `ObjectState` de `engine/market_object.py` (`CREATED→ACTIVE→PARTIALLY_MITIGATED→MITIGATED/INVALIDATED/EXPIRED/CONSUMED`), por lo que es 100 % compatible con el contrato de `MarketObject` y con `Role.POI` restringido a `{D1, H4, H1}`.

Vive en `backtest/` (fuera de `engine/`, respetando el write-set congelado de FASE 4 / §15 del SDD). Su identidad es **determinista** derivada de campos causales, de modo que la evolución `WyckoffSnapshot → WyckoffRange` **no rompe `FULL == PREFIX`** ni introduce fuga futura.

---

## 1. Entidad `WyckoffRange` (definición conceptual)

`WyckoffRange` es el **fold forward puro** de todos los `WyckoffSnapshot` (engine/Wyckoff/types.py:95) cuya `range_ref` apunta al mismo `range_id`, dentro de una ventana `decision_time ≤ T`. Es un objeto congelado por `decision_time` (como `WyckoffSnapshot`), pero con **estado acumulado entre velas**.

### 1.1 Campos

| Campo | Tipo | Origen / invariante |
|---|---|---|
| `range_id` | `str` | **Único y estable** (§3). Identifica la estructura Acumulación/Distribución. |
| `episode_id` | `str` | **Sub-episodio** dentro del rango (§1.2). |
| `authority_tf` | `str` | TF de autoridad del rango; por defecto `H1` (SDD §17: *"H1 ── Wyckoff (authority_tf=H1, Phase C) └── Range actual"*). |
| `structural_phase` | `WyckoffStructuralPhase` | A \| B \| C \| D \| E \| UNCLASSIFIED \| TERMINATED (§4). |
| `lifecycle_state` | `ObjectState` | Importado de `engine/market_object.py:38` (§5). |
| `anchors` | `list[str]` | IDs de `MarketObject` `Role.POI` con `origin_tf ∈ {D1,H4,H1}` (market_object.py:48) que delimitan el rango (soporte/resistencia, Spring, LPS). |
| `phase_events` | `list[WyckoffEvent]` | Eventos canónicos ya emitidos por el motor (types.py:71). |
| `created_at` / `resolved_at` | `decision_time` | Tiempos de los hitos (siempre ≤ T en proyección). |
| `lineage` | `dict` | `range_id` padre y `episode_id` previo (para splits/retests). |
| `fsm_contract` | `str` | `"RUNTIME_BASIC_NOT_WYCKOFF_7"` por defecto; `"WYCKOFF_7_PERSISTENT"` cuando el FSM persistente está activo (§6). |

### 1.2 `episode_id` (sub-episodios)

Un `range_id` puede atravesar **retrocesos no fatales** (p. ej. un *Spring* fallido que devuelve la fase C→B). En vez de invalidar todo el rango, se abre un **nuevo `episode_id`** y el eje de lifecycle permanece `ACTIVE`/`VALIDATED`. `episode_id` se deriva de `(range_id, episode_seed)` donde `episode_seed` cambia sólo ante una transición *hacia atrás* de fase. Así se conserva la trazabilidad de la narrativa completa sin fragmentar la identidad del rango.

---

## 2. Identidad determinista y `FULL == PREFIX` (§6.3 del SDD)

Requisito crítico del diseño: la proyección read-only del replay normaliza la identidad a una derivación estable de campos causales (SDD §6.3), preservando `parent_object`/`related_objects` y evitando UUID de runtime.

- `range_id = sha256(f"{symbol}|{authority_tf}|{sorted(anchor_ids)}|{first_seen_decision_time}")[:20]` precedido de `WR_`.
  - Patrón idéntico al existente `_wrapper_id` de eventos Wyckoff (`WY_<sha256[:20]>`, backtest/wyckoff_timeline.py:54-56).
- `episode_id = sha256(f"{range_id}|{episode_seed}")[:12]`.

**Por qué `FULL == PREFIX` se preserva:**
1. `WyckoffRange(T)` se calcula **sólo** plegando snapshots con `decision_time ≤ T`. Cortar el run en `T'` (PREFIX) produce exactamente el mismo plegado para todo rango hasta `T'`.
2. `range_id`/`episode_id` no dependen de orden de ejecución ni de UUID → el hash del artifact y la comparación `FULL == PREFIX` sobre la intersección (SDD §6.3, gate G3) son idénticos.
3. El `WyckoffSnapshot` canónico **no se muta**: es `@dataclass(frozen=True)` (types.py:95). El rango es un objeto de agregación *aparte*; en el timeline el `range_id`/`episode_id` se **adjuntan en la entrada del timeline** (lectura/atribución), no dentro del snapshot.

---

## 3. Eje de fases A–E: eventos como **transiciones de estado** (no reglas de señal)

El motor Wyckoff canónico **ya emite** estos eventos (engine/Wyckoff/types.py:29-41): `SPRING` (L30), `SOS` (L33), `LPS` (L35), `TEST` (L37), más `UPTHRUST`, `UTAD`, `SOW`, `LPSY`, `FAILED_TEST`, `RANGE_BREAK`. La FSM persistente **sólo observa y registra**; no crea señal. Esto es coherente con la política ya existente `policy = "WYCKOFF_CONTEXT_ONLY_NOT_ENTRY"` (types.py:126) y con `AHF_STATE_NOT_ENTRY` (engine/ahf.py:105).

### 3.1 Estados estructurales

```
WyckoffStructuralPhase = { A, B, C, D, E, UNCLASSIFIED, TERMINATED }
```

### 3.2 Tabla de transición (dirigida por evento observado)

| Desde | Evento (transición) | Hacia | Nota metodológica |
|---|---|---|---|
| UNCLASSIFIED | `SC`/`AR`/`ST` (Secondary Test) | A | Establece límites del rango |
| A | `ST` (Secondary Test superado) | B | Fin de parada de tendencia |
| B | `SPRING` (penetración y recuperación del soporte) | C | El Spring *define* el inicio de C |
| C | `TEST` (test exitoso del Spring / LPS) | C→D (preparación) | Refuerza; no genera entry |
| C | `SOS` (Sign of Strength: rally con spread+volumen) | D | Fuerza hacia arriba confirmada |
| D | `LPS` (Last Point of Support) | E | Soporte final antes del markup |
| E | `RANGE_BREAK` (salida confirmada del rango) | TERMINATED → lifecycle `MITIGATED` | Causa agotada |
| CUALQUIERA | `LPSY`/`UPTHRUST`/`FAILED_TEST` (inval. acumulación) | lifecycle `INVALIDATED` | Era distribución, no acumulación |
| CUALQUIERA | sin resolver en horizonte | lifecycle `EXPIRED` | Rango obsoleto |
| CUALQUIERA | consumido por Setup State downstream | lifecycle `CONSUMED` | Ver §5.3 |

> **Principio:** `Spring`, `Test`, `SOS`, `LPS` son **transiciones de estado** del eje de fase, NO condiciones de entrada. El diseño prohíbe cualquier lógica que emita `can_trade`/`order` a partir de ellos (SDD §16: *NO LIVE TRADING, NO REGLAS EN FRONTEND*).

---

## 4. Eje de lifecycle — compatibilidad con `ObjectState` / `ObjectType` (POI D1/H4/H1)

`WyckoffRange.lifecycle_state` **reutiliza el enum `ObjectState`** de `engine/market_object.py:38` y su tabla `_ALLOWED_TRANSITIONS` (market_object.py:55-75), importado en modo **sólo lectura** (backtest ya lo hace en SDD §6: *"Reutiliza: engine/market_object.py (ObjectState, _ALLOWED_TRANSITIONS, to_dict/from_dict)"*).

### 4.1 Mapeo fase→lifecycle (no inventado, es proyección)

| ObjectState | Significado para el rango | Disparador |
|---|---|---|
| `CREATED` | Rango candidato identificado (fase A, primer snapshot con `range_id`) | asignación de `range_id` |
| `ACTIVE` | Rango confirmado y en despliegue (fases A–D) | `ST` superado |
| `PARTIALLY_MITIGATED` | Rango parcialmente resuelto (precio tocó objetivo parcial / salida parcial) | mitigación observada del rango |
| `MITIGATED` | Rango resuelto (fase E + `RANGE_BREAK`) | `RANGE_BREAK` |
| `INVALIDATED` | Estructura rota (LPSY/UPTHRUST/FAILED_TEST) | evento de inval. canónico |
| `EXPIRED` | No resuelto en horizonte | timeout de observación |
| `CONSUMED` | Un `Setup State` downstream (AHF) lo referenció como contexto de bias | `AHFSnapshot` lo consume |

### 4.2 Compatibilidad con `ObjectType` y restricción POI `{D1,H4,H1}`

- **El `WyckoffRange` NO necesita un nuevo `ObjectType`** para FASE 4.2+. Se compone de referencias a `MarketObject` existentes. Esto evita tocar `engine/market_object.py` (prohibido en FASE 4, SDD §15; y no se requiere para WYCKOFF-7).
- Sus **anclas** son `MarketObject` con `Role.POI` y `origin_tf ∈ {"D1","H4","H1"}` — exactamente el conjunto `_POI_TFS` (market_object.py:48) validado en market_object.py:113-114 (`if self.role == Role.POI and self.origin_tf not in _POI_TFS: raise`). El rango respeta esa restricción por construcción.
- (Opcional, fuera de alcance FASE 4.2) si en el futuro se quisiera serializar el rango *como* `MarketObject`, requeriría añadir `WYCKOFF_RANGE` al enum `ObjectType` (market_object.py:16) — cambio a `engine/` que queda **fuera del write-set** y debe aprobarse como SDD canónico aparte (SDD §10). El diseño actual lo evita vía composición.

---

## 5. Evolución `WyckoffSnapshot` → `WyckoffRange` (sin romper contratos)

### 5.1 Punto de enganche actual

- `build_wyckoff_timeline` (backtest/wyckoff_timeline.py:104) ya hace `snapshot.update({"range_id": None, "episode_id": None, "fsm_contract": FSM_CONTRACT})` en L171. Hoy `range_id` es siempre `None`.
- `FSM_CONTRACT = "RUNTIME_BASIC_NOT_WYCKOFF_7"` (backtest/wyckoff_timeline.py:20) se mantiene como **default**.
- `WyckoffSnapshot` ya trae `range_ref` (types.py:100) y los campos que el `_delta` vigila: `phase, phase_state, range_ref, ict_alignment, conflict, volume_mode, authority_tf` (wyckoff_timeline.py:84-85).

### 5.2 Camino de evolución (no regresión)

1. **Modo legacy (hoy):** `FSM_CONTRACT` queda `RUNTIME_BASIC_NOT_WYCKOFF_7`; `range_id=None`. Comportamiento idéntico a v1.1/v1.2.
2. **Modo persistente (WYCKOFF-7):** cuando el FSM persistente está activo, el paso de atribución de L171 **resuelve** el `range_id`/`episode_id` reales de ese snapshot (look-up en el fold acumulado), sin mutar el `WyckoffSnapshot` congelado. El `fsm_contract` pasa a `"WYCKOFF_7_PERSISTENT"`.
3. El agregador (nuevo módulo `backtest/wyckoff_range.py`, dentro del write-set permitido de FASE 4.2) produce, por cada `range_id`, un `WyckoffRange` serializable con el mismo contrato `to_dict/from_dict` que `MarketObject` (market_object.py:178 / :211) para máxima compatibilidad de artifact.

### 5.3 Por qué **no hay fuga futura**

- `build_wyckoff_timeline` ya construye **prefixes cerrados** (`_closed_prefix`, wyckoff_timeline.py:23; D1/H4/H1 sólo hasta `decision_time`, L132) y `build_wyckoff_snapshot` se alimenta de ellos (L163-169).
- `WyckoffRange(T)` sólo lee snapshots/ejemplos con `decision_time ≤ T` y anclas `MarketObject` con barras ≤ T. Ningún snapshot ni POI futuro alcanza el rango → gate **G6 "Futuro invisible"** y **G3 "FULL==PREFIX"** se preservan.
- El `policy` del rango es de solo contexto; no alimenta órdenes.

---

## 6. Trazabilidad al GRAFO (`graphify-out/graph.json`, built_at_commit `c1328ad`)

Nodos reales consultados (id → archivo:línea del grafo):

| Nodo grafo | Archivo | Línea (grafo) | Concepto |
|---|---|---|---|
| `engine_market_object_objectstate` | engine/market_object.py | L38 | `ObjectState` (lifecycle) |
| `engine_market_object_objecttype` | engine/market_object.py | L16 | `ObjectType` (sin WYCKOFF) |
| `engine_market_object_role` | engine/market_object.py | L31 | `Role` (POI/REFINEMENT/…) |
| `engine_market_object_marketobject` | engine/market_object.py | L79 | `MarketObject` |
| `engine_ahf_ahfstate` | engine/ahf.py | L24 | `AHFState` (FSM canónica) |
| `engine_ahf_ahfevent` | engine/ahf.py | L35 | `AHFEvent` |
| `engine_ahf_ahfsnapshot` | engine/ahf.py | L83 | `AHFSnapshot` |
| `backtest_wyckoff_timeline_build_wyckoff_timeline` | backtest/wyckoff_timeline.py | L104 | orquestador de snapshots |
| `engine_wyckoff_types_wyckoffsnapshot` | engine/Wyckoff/types.py | L96 | `WyckoffSnapshot` |
| `engine_wyckoff_adapter_build_wyckoff_snapshot` | engine/Wyckoff/adapter.py | L57 | constructor canónico |

---

## 7. Trazabilidad al SDD v1.2 (`docs/planificacion/SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md`)

| Sección SDD | Relación con este diseño |
|---|---|
| §3 Arquitectura definitiva | `WyckoffRange` es **proyección**, no segundo motor (principio "NO estamos construyendo un segundo sistema"). |
| §4 Market State(T) | El rango es parte del Market State persistente en T. |
| §6 `market_state.py` | `WyckoffRange` reutiliza `ObjectState`, `_ALLOWED_TRANSITIONS`, `to_dict/from_dict` (SDD §6 cita esos símbolos). |
| §6.1 Semántica HTF/LTF | El rango se observa en `main_tf` pero sus anclas POI nacen en `{D1,H4,H1}`. |
| §6.2 Setup State = AHF | `CONSUMED` se dispara cuando `AHFSnapshot` consume el rango como contexto de bias. |
| §6.3 Identidad / FULL==PREFIX | `range_id`/`episode_id` deterministas (§2 y §3 de este doc). |
| §7 schema 1.2 | Permite `range_id`/`episode_id` "cuando el FSM persistente esté activo, manteniendo `RUNTIME_BASIC_NOT_WYCKOFF_7` como default" — exactamente el diseño de §5.2. |
| §8 `wyckoff_timeline.py` | El enganche es L171 (hoy `None`); se resuelve en modo persistente. |
| §10 WYCKOFF-7 boundary | `FSM_CONTRACT` permanece `RUNTIME_BASIC_NOT_WYCKOFF_7` por defecto; WYCKOFF-7 es descriptivo, no estadístico/trading. |
| §15 Write-set congelado | `WyckoffRange` vive en `backtest/`; **no** toca `engine/`. |
| §16 Reglas absolutas | Cumple NO IA / NO TRAINING / NO TRADING / NO SEGUNDA FSM / NO REGLAS EN FRONTEND. |
| §17 Criterio DONE | El ejemplo del DONE muestra literalmente *"H1 ── Wyckoff (authority_tf=H1, Phase C) └── Range actual"* → valida `authority_tf=H1` y fase C del diseño. |

---

## 8. Riesgos

| # | Riesgo | Impacto | Mitigación en el diseño |
|---|---|---|---|
| R1 | **Confusión de taxonomías de fase.** `WyckoffPhase` (types.py:12) ya existe con `ACCUMULATION/MARKUP/DISTRIBUTION/...`, que es *fase de mercado*, distinta de la *fase estructural A–E* de WYCKOFF-7. | Media | Este diseño introduce `WyckoffStructuralPhase` (A–E) **explícitamente separado** de `WyckoffPhase`; no se reutiliza el enum existente para las A–E. |
| R2 | **Fuga de `ObjectState` fuera de su tabla.** Si la implementación transiciona fases como lifecycle directo, rompe `_ALLOWED_TRANSITIONS` (market_object.py:55). | Alta | Los dos ejes son **ortogonales**: fase A–E = narrativa; `ObjectState` = lifecycle del rango, usando la tabla canónica importada. |
| R3 | **`range_id` no determinista** → rompe `FULL==PREFIX` (gate G3). | Alta | Derivación `sha256` de campos causales (§2), idéntica a `_wrapper_id` existente (wyckoff_timeline.py:54). |
| R4 | **Fuga futura** al plegar snapshots > T. | Alta | Fold estricto `decision_time ≤ T` + prefixes cerrados ya existentes (wyckoff_timeline.py:23,132). |
| R5 | **Tocar `engine/`** (añadir `ObjectType.WYCKOFF_RANGE`) fuera del write-set (SDD §15). | Alta | Diseño por **composición** (referencias a `MarketObject` POI), no herencia; el enum `ObjectType` queda intacto. |
| R6 | **Interpretar eventos como señal.** `Spring/Test/SOS/LPS` son transiciones de estado, no entry signals. | Crítica (rompe SDD §16) | Prohibido por diseño; el rango es `policy` de solo contexto, hereda `WYCKOFF_CONTEXT_ONLY_NOT_ENTRY`. |
| R7 | **Regresión del contrato actual.** Cambiar L171 rompe v1.1/v1.2. | Media | L171 conserva `range_id=None` en modo legacy; el modo persistente *resuelve* el id sin mutar el snapshot congelado. |
| R8 | **Inconsistencia AHF ↔ Wyckoff.** Un rango `CONSUMED` pero AHF sin lock. | Media | `CONSUMED` es pura atribución de linaje; no fuerza transición AHF (SDD §6.2: Setup State no re-deriva FSM). |

---

## 9. Guardas / gates recomendados (para la futura implementación)

- **G-WY1 (identidad):** `range_id` y `episode_id` deben ser reproducibles (`FULL==PREFIX` sobre intersección).
- **G-WY2 (sin fuga):** test de que ningún `WyckoffRange(T)` referencia snapshot/POI con `time > T`.
- **G-WY3 (compatibilidad lifecycle):** toda transición de `lifecycle_state` debe pasar `MarketObject.can_transition_to` (market_object.py:161).
- **G-WY4 (POI restriction):** toda ancla debe cumplir `Role.POI` y `origin_tf ∈ {D1,H4,H1}` (market_object.py:48,113).
- **G-WY5 (no señal):** auditoría estática de que `WyckoffRange` no expone ningún campo `order`/`can_trade`/`entry`.

---

## 10. Conclusión

`WyckoffRange` es una entidad de **proyección persistente**, hermana de `MarketObject`, que:
- tiene `range_id` único y `episode_id` para sub-episodios (§1),
- modela fases A–E con `Spring/Test/SOS/LPS` como **transiciones de estado** observadas, no señales (§3),
- es compatible con `ObjectState` y con la restricción POI `{D1,H4,H1}` por composición (§4),
- evoluciona desde `WyckoffSnapshot` sin romper `FULL==PREFIX` ni filtrar futuro (§5),
- y traza al grafo (`graphify-out/graph.json`, `c1328ad`) y al SDD v1.2 (§6-§17).

**No requiere modificar `engine/` ni `backtest/` para este diseño; la implementación futura (post FASE 4.2) vive en `backtest/` (nuevo `wyckoff_range.py`), respetando el write-set y las reglas absolutas del SDD.**
