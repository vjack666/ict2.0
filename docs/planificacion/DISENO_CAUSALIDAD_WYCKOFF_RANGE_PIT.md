# Diseño de causalidad punto‑en‑tiempo (PIT) para la evolución `WyckoffSnapshot` → `WyckoffRange` persistente (ICT 2.0)

> **Tipo de entrega:** Especificación de diseño (markdown). **No contiene código ejecutable ni modifica ningún archivo del repositorio.**
> **Autoridad:** Delegación de diseño de causalidad únicamente. FASE 4.1 ya cerró *Setup State* proyectando `AHFSnapshot` sin re‑derivar la FSM (`5623a7b`). La FSM descriptiva `WYCKOFF‑7` es posterior (ver límite `SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md` §10). El runtime vigente sigue siendo `RUNTIME_BASIC_NOT_WYCKOFF_7`.
> **Grafo de soporte:** `graphify-out/graph.json` (`built_at_commit = c1328ad4d2f546cf9a3adc841d9040b904c475c0` == `HEAD`). Las citas de archivos reales abajo están respaldadas por ese conocimiento grafificado.

---

## 0. Resumen de entregables

- **Ruta de este documento:** `docs/planificacion/DISENO_CAUSALIDAD_WYCKOFF_RANGE_PIT.md`
- **Campo PIT propuesto (entregable obligatorio):** `scientific_status["wyckoff_range_pit"]` — bloque hermano de `pit_temporal_consistency`, que extiende la prueba PIT al rango persistente incluyendo su `history` de transiciones.

---

## 1. Contexto y alcance

El motor actual expone un `WyckoffSnapshot` **puntual y de solo‑lectura** (`engine/Wyckoff/types.py::WyckoffSnapshot`, L96‑127), construido por `build_wyckoff_snapshot` (`engine/Wyckoff/adapter.py::build_wyckoff_snapshot`, L57) a partir de **prefijos cerrados** por temporalidad (`engine/Wyckoff/adapter.py::_prefix`, L15; `backtest/wyckoff_timeline.py::_closed_prefix`, L23). El runtime declara `range_id=None, episode_id=None, fsm_contract="RUNTIME_BASIC_NOT_WYCKOFF_7"` (`backtest/wyckoff_timeline.py`, L171) y el esquema lo exige (`backtest/schema.py`, L284‑290).

La evolución propuesta introduce un **`WyckoffRange` persistente**: un objeto con identidad estable (`range_id`), ciclo de vida y una `history` de transiciones, que sustituye/extiende el snapshot puntual cuando el FSM descriptivo esté activo. La pregunta de este diseño es **solo una**: *¿se puede construir ese rango persistente sin violar `FULL == PREFIX` ni introducir fuga futura?* La respuesta es **sí**, y se demuestra abajo a partir de los invariantes ya certificados del snapshot.

---

## 2. Estado actual (evidencia real, grafo + código)

| Concepto | Archivo real | Ubicación | Rol en la causalidad |
|---|---|---|---|
| `WyckoffSnapshot` (frozen, prefix‑only) | `engine/Wyckoff/types.py` | L96‑127 | Estado puntual; `to_dict()` serializa `decision_time` |
| `build_wyckoff_snapshot` | `engine/Wyckoff/adapter.py` | L57 | Construye solo con `frames` ya prefijados por `decision_time` |
| `_prefix` / `_closed_prefix` | `engine/Wyckoff/adapter.py` / `backtest/wyckoff_timeline.py` | L15 / L23 | `times <= decision_time` → corte causal por construcción |
| `AHFTransition` (modelo de `history`) | `engine/ahf.py` | L60‑79 | Plantilla de transición causal a imitar |
| `AHFSnapshot.history` | `engine/ahf.py` | L91 | Lista de `AHFTransition` por `decision_time` |
| `build_wyckoff_timeline` | `backtest/wyckoff_timeline.py` | L104 | Un snapshot por vela cerrada; `range_id=None` hoy |
| Gate `pit_temporal_consistency` | `backtest/replay.py` | L797‑803 | `status=PASS, points_checked=80, divergences=0` |
| Evidencia del gate | `reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json` | — | `wyckoff_state(full,t)==wyckoff_state(prefix_through_t,t)`, 80/80, 0 divergencias |
| Verificador `full_eq_prefix` | `scripts/verify_fase42_wyckoff_integration.py` | L66‑79 | Usa `pit_temporal_consistency.status==PASS` y `divergences==0` |
| Verificador `FULL == PREFIX` (2 artifacts) | `scripts/verify_6tf_acceptance.py::compare_full_prefix` | L23 | Comparación literal de `market_state`/`setups` en la intersección |
| Permiso de `range_id`/`episode_id` | `docs/planificacion/SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md` | L281‑282 | "Permitir `range_id`/`episode_id` cuando el FSM persistente esté activo" |
| Contrato JSON v1.1 (`range_id=null`) | `docs/planificacion/SDD_VISUAL_BACKTEST_WYCKOFF_V1_1.md` | L108‑116 | FSM básica declara `range_id=null, episode_id=null` |

**Hecho ya certificado (gate_wyckoff_pit.json):** el estado Wyckoff puntual satisface `wyckoff_state(full, t) == wyckoff_state(prefix_through_t, t)` en 80 puntos de una muestra H1 de 20 años, con **0 divergencias**. Ese es el suelo sobre el que se construye el rango persistente.

---

## 3. Definición de `WyckoffRange` (forma de diseño, no código)

`WyckoffRange` es la proyección persistente de un rango Wyckoff. Mantiene la disciplina *closed‑prefix* del snapshot: **en `decision_time = T` solo puede usar barras con `time <= T`.**

```
WyckoffRange (forma de diseño)
  range_id            : str            # identidad estable derivada de campos causales (no UUID de ejecución)
  authority_tf        : str            # ej. "D1"/"H1"
  open_time           : Timestamp      # <= decision_time siempre (corte)
  open_phase          : WyckoffPhase
  zone_high / zone_low: float          # derivados SOLO de prefix_{<=T}
  state               : RangeState     # OPEN | ACTIVE | EXTENDED | TERMINAL_CLOSED | TERMINAL_INVALIDATED
  decision_time       : Timestamp      # momento de la proyección
  history             : list[WyckoffRangeTransition]   # estilo AHFTransition (§6)
  policy              : "WYCKOFF_CONTEXT_ONLY_NOT_ENTRY"
  fsm_contract        : str            # RUNTIME_BASIC_NOT_WYCKOFF_7 hoy; WYCKOFF-7 cuando aplique
```

Invariante fundacional (heredado de `WyckoffSnapshot`): `open_time <= decision_time` y **todos** los campos `zone_*`, `open_phase` y cada `history[i].transition_time` son función de `prefix_{<=T}`.

---

## 4. Requisito (1): Regla de corte — `WyckoffRange(T)` solo de datos `time <= decision_time(T)`

**Regla (PIT‑CUT):**

> Para todo `T`, el objeto `WyckoffRange(T)` se construye exclusivamente con el prefijo cerrado `frames[tf].loc[time <= T]`. Ningún `range_id`, `zone_*`, `phase` o transición de `history` puede depender de una barra con `time > T`.

**Por qué no se viola `FULL == PREFIX`:**
- El motor ya impone el corte en la capa inferior: `build_wyckoff_snapshot` recibe `frames` que son prefijos (`adapter.py::_prefix`, L15) y `build_wyckoff_timeline` los genera con `_closed_prefix` (`wyckoff_timeline.py`, L23). El rango no introduce ninguna nueva fuente de datos: hereda exactamente el mismo prefijo que el snapshot.
- Sea `FULL` el run sobre datos `[t0, t_end]` y `PREFIX` el run sobre `[t0, T]` con `T <= t_end`, misma configuración, mismo commit, mismos slices (el contrato de `compare_full_prefix`, `verify_6tf_acceptance.py` L23). Por PIT‑CUT, para cada `t <= T` el `WyckoffRange(t)` de FULL y de PREFIX se calculan con **el mismo prefijo** `frames[·].loc[time <= t]`. Luego `WyckoffRange_FULL(t) == WyckoffRange_PREFIX(t)` para toda la intersección.
- Esto es la traducción directa del gate ya aprobado: `gate_wyckoff_pit.json` probó la igualdad a nivel de `WyckoffSnapshot`; el rango la hereda porque su constructor no mira más allá del prefijo que ya recibe el snapshot.

> Conclusión (1): `WyckoffRange(T)` cumple PIT‑CUT y, por tanto, la intersección FULL/PREFIX es idéntica. No hay divergencia por construcción.

---

## 5. Requisito (2): Un rango que cierre en `T+K` no revela información en `T`

El cierre (spring confirmado, upthrust, breakdown) o la invalidación (por ICT: `D1_INVALIDATED`/`H4_INVALIDATED`/`H1_INVALIDATED`, ver `engine/ahf.py` L41‑44, L218‑250) ocurren en su **propio momento** `T+K`. Este diseño los trata como **transiciones terminales** que se registran **en el instante en que se vuelven observables**, no antes.

**Regla (PIT‑TERMINAL):**
> Toda transición con `transition_time = T+K` entra a `history` **solo** cuando el run alcanza `decision_time = T+K`. En `T` (`T < T+K`), `WyckoffRange(T).state` es **no terminal** (`OPEN`/`ACTIVE`/`EXTENDED`) y `history` contiene **exclusivamente** transiciones con `transition_time <= T`.

**Demostración de no‑revelación:**
- En `T`, `history` no contiene ningún evento con `time > T`. Por la regla de visibilidad de eventos del esquema (`backtest/schema.py` L372‑380: `wyckoff_event` solo es visible desde `first_seen_decision_time`, y `event_time` no puede exceder el cierre de su `first_seen`), la transición terminal de `T+K` **no existe** en la proyección de `T`.
- Por tanto `WyckoffRange(T)` no expone predicción de cierre: su `state` terminal se materializa recién en `T+K`. Esto es análogo al `delta` observacional de `wyckoff_timeline.py::_delta` (L82) — describe lo que *ya* ocurrió, no lo que ocurrirá.
- Efecto sobre `FULL == PREFIX`: truncar el run en `T` simplemente **omite** la transición de `T+K` (que está más allá del corte). En la intersección `[t0, T]` ambos runs (FULL y PREFIX) ven exactamente las mismas transiciones `<= T`. No hay fuga futura y no hay divergencia.

> Conclusión (2): el cierre/invalidación es una transición terminal ligada a su `transition_time`; en `T` el rango es no‑terminal y no revela `T+K`. `FULL == PREFIX` se preserva.

---

## 6. Requisito (3): Estructura `history` estilo `AHFTransition` para `WyckoffRange`

`engine/ahf.py::AHFTransition` (L60‑79) es la plantilla causal canónica del repo: cada transición lleva `state`, `active_tf`, `transition_event`, `transition_time`, `parent_state`, `invalidation_reason`, `confirmed_context`. `AHFSnapshot.history` (L91) es la lista ordenada por `decision_time`. El rango adopta la misma forma:

```
WyckoffRangeTransition (espejo de AHFTransition)
  state            : str   # RangeState en el momento de la transición
  active_tf        : str   # authority_tf vigente
  transition_event : str   # RANGE_OPENED | RANGE_EXTENDED | RANGE_CONFIRMED | RANGE_CLOSED | RANGE_INVALIDATED
  transition_time   : Timestamp  # == decision_time en que se observó; siempre <= decision_time de proyección
  parent_range_id  : str | None  # para anidación (rango hijo de un range)
  reason           : str | None  # motivo de cierre/invalidación (p. ej. "D1 bias flip")
  confirmed_context: dict  # snapshot de phase, range_ref, ict_alignment en el instante
```

Mapeo 1:1 con `AHFTransition`:

| `AHFTransition` | `WyckoffRangeTransition` | Comentario |
|---|---|---|
| `state` | `state` (RangeState) | estado de ciclo de vida |
| `active_tf` | `active_tf` | autoridad en el momento |
| `transition_event` | `transition_event` (RANGE_*) | evento de borde |
| `transition_time` | `transition_time` | **siempre `<= decision_time`** (PIT‑TERMINAL) |
| `parent_state` | `parent_range_id` | linaje, no estado previo |
| `invalidation_reason` | `reason` | texto de cierre/invalidación |
| `confirmed_context` | `confirmed_context` | contexto sellado en el instante |

`history` se construye de forma **apend‑only y causal**: `build_wyckoff_range` emite una `WyckoffRangeTransition` solo cuando detecta el borde en el prefijo de `T`, idéntico al patrón `_emit` de `AdaptiveHierarchicalFunnel` (`engine/ahf.py` L157‑175). La validación de esquema ya exige listas para `history`/`delta` (`backtest/schema.py` L535‑539), de modo que la serialización es directa.

---

## 7. Requisito (4): Verificación contra `pit_temporal_consistency` y campo propuesto

El `scientific_status` actual ya contiene (`backtest/replay.py` L792‑814; `backtest/schema.py` L567‑574 exige su presencia):

```json
"pit_temporal_consistency": {
  "status": "PASS",
  "points_checked": 80,
  "divergences": 0,
  "meaning": "TEMPORAL_CONSISTENCY_IN_AUDITED_SAMPLE_ONLY",
  "source": "reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json"
}
```

Ese bloque opera a **nivel de `WyckoffSnapshot`**. Para el rango persistente se propone el campo hermano:

### Campo PIT propuesto (entregable)

```json
"wyckoff_range_pit": {
  "status": "PASS",
  "points_checked": 80,
  "divergences": 0,
  "meaning": "RANGE_STATE_PREFIX_EQUALS_FULL_ON_TRANSITION_HISTORY",
  "source": "reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_range_pit.json",
  "check": "WyckoffRange(full,t).history == WyckoffRange(prefix_through_t,t).history  AND  no transition_time > t in prefix run"
}
```

**Definición operativa del gate (análogo a `gate_wyckoff_pit.json`):**
- Para cada punto `t` de la muestra: `WyckoffRange(full, t).history == WyckoffRange(prefix_through_t, t).history` (misma secuencia de `WyckoffRangeTransition`, mismos `transition_time`).
- Y se exige `no transition_time > t` en el run PREFIX (garantía de PIT‑TERMINAL).
- `divergences = 0` ⇒ `FULL == PREFIX` se mantiene **incluyendo** la `history` del rango.

**Integración con los verificadores existentes:**
- `scripts/verify_fase42_wyckoff_integration.py::full_eq_prefix` (L66‑79) ya valida `pit_temporal_consistency.status == "PASS"` y `divergences == 0`; el nuevo campo se consulta con la **misma** lógica, ampliando la cobertura de `market_state`/`setups` a `WyckoffRange.history`.
- `scripts/verify_6tf_acceptance.py::compare_full_prefix` (L23) sigue siendo la fuente de verdad artifact‑to‑artifact: el rango se añade a la comparación literal de la intersección, sin cambiar el contrato (mismo inicio/config/slices, fin PREFIX más corto).

**Relación con `pit_temporal_consistency`:** el snapshot‑gate queda subsumido por el range‑gate (el rango en `T` expone al menos el mismo estado que el snapshot en `T`, más su `history`). Ambos pueden coexistir; el range‑gate es el más fuerte.

> Entregable PIT: `scientific_status["wyckoff_range_pit"]` (bloque hermano de `pit_temporal_consistency`), con `status`, `points_checked`, `divergences`, `meaning`, `source` y `check`.

---

## 8. Matriz de invarianzas de causalidad (checklist de diseño)

| ID | Invariante | Regla | Soporte en código actual | Estado |
|---|---|---|---|---|
| PIT‑CUT | `WyckoffRange(T)` usa solo `time <= T` | §4 | `_prefix`/`_closed_prefix` ya cortan | ✅ heredado |
| PIT‑TERMINAL | transición terminal solo en su `transition_time` | §5 | visibilidad `first_seen` (`schema.py` L372‑380) | ✅ heredado |
| FULL==PREFIX | intersección FULL/PREFIX idéntica | §4,§5 | `gate_wyckoff_pit.json` (0 div) + `compare_full_prefix` | ✅ extensible |
| NO‑LEAK | 0 eventos con `time > last_close` | §5 | `verify_6tf_acceptance.py` L141‑145 | ✅ extensible |
| HISTORY‑CAUSAL | `history` append‑only por `decision_time` | §6 | `AHFTransition`/`_emit` (`ahf.py` L157) | ✅ modelo |
| RUNTIME | `RUNTIME_BASIC_NOT_WYCKOFF_7` por defecto | §1 | `wyckoff_timeline.py` L20, L171 | ✅ vigente |

---

## 9. Límites y next‑steps (no acción ahora)

1. **No tocar código.** Este documento es diseño; la implementación corresponde a la fase `WYCKOFF‑7` bajo autorización de CEO/auditoría (`SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md` §10). El runtime básico permanece.
2. **Permiso ya previsto:** `SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md` L281‑282 autoriza `range_id`/`episode_id` cuando el FSM persistente esté activo, manteniendo `RUNTIME_BASIC_NOT_WYCKOFF_7` como default. Este diseño encaja en esa ranura.
3. **Esquema:** `backtest/schema.py` L284‑290 hoy exige `range_id is None` bajo runtime básico; al activar el rango persistente, esa guarda debe relajarse solo bajo el contrato `WYCKOFF‑7` (fuera de alcance de este diseño).
4. **Evidencia del gate:** generar `reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_range_pit.json` con la misma metodología que `gate_wyckoff_pit.json` (80 puntos H1, 20Y), produciendo el `source` del campo propuesto.

---

## 10. Citas Graphify (archivos reales verificados)

Nodos y archivos confirmados en `graphify-out/graph.json` (`built_at_commit == HEAD c1328ad`):

- `engine/ahf.py` — `AHFTransition` (L60), `AHFSnapshot.history` (L91), `_emit` (L157), `step` (L252), invalidación (L218‑250).
- `engine/Wyckoff/types.py` — `WyckoffSnapshot` frozen (L96‑127).
- `engine/Wyckoff/adapter.py` — `build_wyckoff_snapshot` (L57), `_prefix` (L15).
- `backtest/wyckoff_timeline.py` — `_closed_prefix` (L23), `build_wyckoff_timeline` (L104), `FSM_CONTRACT` (L20), `range_id=None` (L171).
- `backtest/schema.py` — `validate_visual_backtest` (L186), guarda `range_id`/`episode_id` (L284‑290), `pit_temporal_consistency` requerido (L567‑574).
- `backtest/replay.py` — `pit_temporal_consistency` emitido (L797‑803).
- `scripts/verify_fase42_wyckoff_integration.py` — `full_eq_prefix` (L66‑79).
- `scripts/verify_6tf_acceptance.py` — `compare_full_prefix` (L23), `7_zero_future_leak` (L141‑145).
- `reports/audits/experiments/wyckoff_ict_01/gate_wyckoff_pit.json` — evidencia PIT (80/80, 0 divergencias).
- `docs/planificacion/SDD_VISUAL_BACKTEST_WYCKOFF_V1_1.md` — contrato `range_id=null` (L108‑116), build del timeline (L95‑102).
- `docs/planificacion/SDD_MARKET_STATE_SETUP_BUILDER_V1_2.md` — permiso `range_id`/`episode_id` (L281‑282), `FULL==PREFIX` (L266‑271), límite `WYCKOFF‑7` (L298‑319).

---

## 11. Conclusión

La evolución `WyckoffSnapshot` → `WyckoffRange` **puede** construirse como objeto persistente **sin** violar `FULL == PREFIX` ni introducir fuga futura, porque:

1. hereda el corte `time <= decision_time` ya certificado en el snapshot (PIT‑CUT);
2. trata cierre/invalidación como transición terminal visible solo en su `transition_time`, de modo que en `T` el rango es no‑terminal y no revela `T+K` (PIT‑TERMINAL);
3. adopta la `history` estilo `AHFTransition`, append‑only y causal;
4. se verifica con el campo propuesto `scientific_status["wyckoff_range_pit"]`, análogo y más fuerte que `pit_temporal_consistency`, reutilizando `gate_wyckoff_pit.json` y los verificadores `verify_fase42_*` / `verify_6tf_acceptance.py`.

**Entregables:** ruta del doc = `docs/planificacion/DISENO_CAUSALIDAD_WYCKOFF_RANGE_PIT.md`; campo PIT = `scientific_status["wyckoff_range_pit"]`.
