# WYCKOFF-7 — Semántica de ALIGNMENT / CONFLICT entre AHF (ICT canónico) y la capa Wyckoff

**Tipo:** Especificación de diseño (NO código). Documento de contrato.
**Alcance:** Definir el significado de `alignment` y `conflict` como diagnósticos
cruzados AHF ↔ Wyckoff, y fijar el contrato de promoción a `WYCKOFF-7`.
**Autoridad:** `.hermes-index.md`, `AGENTS.md`, `docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md`.
**Estado:** BORRADOR DE DISEÑO. No modifica `engine/`, `backtest/` ni `runtime/`.
**FSM vigente (no promovida):** `RUNTIME_BASIC_NOT_WYCKOFF_7`
(`backtest/wyckoff_timeline.py:20`, `FSM_CONTRACT`).

---

## 0. Regla de oro de este documento

> `alignment` y `conflict` son **diagnósticos observacionales** de coherencia
> direccional entre dos máquinas de estado. **Ninguno de los dos es una señal
> de entrada.** Un diagnóstico no es promoción, y la ausencia de conflicto no es
> una autorización de trade (`AGENTS.md`: "GEN-000 y los gates científicos
> conservan su autoridad; un diagnóstico no es promoción").

---

## 1. Contexto y autoridad (archivos reales citados)

| Rol | Archivo real | Símbolo / línea | Nota graphify |
|---|---|---|---|
| Máquina ICT canónica (autoridad de estado/dirección) | `engine/ahf.py` | `AdaptiveHierarchicalFunnel` L132; `AHFState` L24–32; `AHFSnapshot` L82–106; `_ctx_blob` L109–121 | nodo `engine/ahf.py#L132` (community 17) |
| Contexto por capa (dirección por TF) | `engine/ahf.py` | `confirmed_context[<tf>]["structure_bias"]` (BULLISH/BEARISH/UNKNOWN) vía `_ctx_blob` L113–121 | — |
| Snapshot Wyckoff (capa especializada) | `engine/Wyckoff/types.py` | `WyckoffSnapshot` L95–127; `phase` L97; `phase_state` L98; `ict_alignment` L105; `conflict` L106 | nodo `engine/Wyckoff/types.py#L96` (community 7, degree 5) |
| Clasificador ICT↔Wyckoff (interno) | `engine/Wyckoff/classifier.py` | `classify_alignment` L17–46; `phase_direction` L9–14 | nodo `engine/Wyckoff/classifier.py#L17` (community 7, degree 10) |
| Adaptador read-only de Wyckoff | `engine/Wyckoff/adapter.py` | `build_wyckoff_snapshot` L57–105; `_context_direction` L25–33 (lee `constraints.direction_hint`) | llama `classify_alignment` en L84 |
| Timeline causal consumidor (FSM vigente) | `backtest/wyckoff_timeline.py` | `FSM_CONTRACT = "RUNTIME_BASIC_NOT_WYCKOFF_7"` L20; `build_wyckoff_timeline` L104–210; `_delta` L82–101 | política `CLOSED_PREFIX_DIAGNOSTIC_ONLY` L201 |
| Proyección del Context State (policy de no-entrada) | `backtest/setup_builder.py` | `build_setup_state` L95–131; `policy = "CONTEXT_STATE_NOT_ENTRY_SIGNAL"` L91 | — |
| Pre-registro del experimento de evidencia | `docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md` | §5 (n calculado), §8 (PIT), §9 (veredicto) | — |
| Certificación independiente de la evidencia | `reports/audits/experiments/wyckoff_ict_01/certification/CERTIFICATION_VERDICT.md` | dictamen `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N` | — |
| Índice maestro (estado EXP-WYCKOFF-ICT-01) | `.hermes-index.md` | L158 (bloqueador EXP-WYCKOFF-ICT-01); L18 (FSM `RUNTIME_BASIC_NOT_WYCKOFF_7`) | — |

**Verificación graphify (grafo `graphify-out/graph.json`, `built_at_commit = c1328ad`,
igual a HEAD actual `c1328ad` → fresco):** la travesía confirma que
`AdaptiveHierarchicalFunnel` (community 17) y `WyckoffSnapshot`/`classify_alignment`
(community 7) son islas funcionales distintas conectadas sólo a través de
`backtest/wyckoff_timeline.build_wyckoff_timeline` (que importa
`build_wyckoff_snapshot` de `engine.Wyckoff`) y de `MTFNavigator`
(`engine/mtf_navigation.py#L394`). No hay hoy un borde directo AHF → Wyckoff:
esa unión es precisamente lo que este contrato define para WYCKOFF-7.

---

## 2. Definiciones de dominio

### 2.1 Dirección canónica ICT — fuente de autoridad: AHF

El AHF es la máquina de estados ejecutable que **bloquea** el sesgo direccional
HTF por capas (`WA1_D1 → D1_LOCKED → H4_LOCKED → H1_LOCKED → SETUP_READY`,
`engine/ahf.py:280–302`). Su dirección canónica se deriva del **lock de mayor
jerarquía confirmado** en `confirmed_context`, no del último bar.

Definición (especificación; a implementar post-promoción, sin tocar código hoy):

```
ahf_ict_direction(ahf_snapshot) -> {-1, 0, +1}
    leer confirmed_context en orden de autoridad D1 > H4 > H1
    tomar el primer tf presente con structure_bias en {BULLISH, BEARISH}
    devolver +1 si BULLISH, -1 si BEARISH, 0 si ninguno está locked
```

- `AHF.state` aporta la **madurez** del lock (p. ej. `SETUP_READY` implica
  D1/H4/H1 locked; `WAIT_D1` implica dirección 0).
- `confirmed_context[<tf>]["structure_bias"]` aporta el **signo** (vía `_ctx_blob`,
  `engine/ahf.py:113–121`).

> Distinción crítica: hoy `build_wyckoff_snapshot` deriva la dirección ICT de
> `context_state.constraints.direction_hint` (`engine/Wyckoff/adapter.py:25–33`),
> que es el `MTFNavigator`, **no** el lock AHF. Para WYCKOFF-7 la fuente
> canónica de dirección ICT debe ser `ahf_ict_direction` (el lock AHF), porque
> `AGENTS.md` declara a `engine/` como autoridad y a `backtest/` como consumidor
> aislado; el AHF es la única máquina con invalidación y lock jerárquico.

### 2.2 Dirección Wyckoff — fase / tendencia

`WyckoffSnapshot.phase` (`engine/Wyckoff/types.py:97`) clasifica el proceso; su
dirección se obtiene con `phase_direction` (`engine/Wyckoff/classifier.py:9–14`):

| Fase | `phase_direction` |
|---|---|
| `ACCUMULATION`, `MARKUP` | +1 |
| `DISTRIBUTION`, `MARKDOWN` | −1 |
| `RANGE_UNCLASSIFIED`, `TRANSITION`, `UNKNOWN` | 0 |

`phase_state` (`engine/Wyckoff/types.py:98`) ya expresa la relación interna
Wyckoff-vs-ICT-context como `PRO_TREND / COUNTERTREND / TRANSITION / NEUTRAL`.
Para WYCKOFF-7 ese "ICT-context" interno **debe resolverse contra el lock AHF**
(§2.1), no contra `direction_hint` del MTFNavigator.

---

## 3. Semántica de ALIGNMENT (requisito 1)

**Definición formal.** `alignment` = coincidencia direccional entre la dirección
canónica AHF (`ahf_ict_direction`) y la dirección Wyckoff (`phase_direction`):

```
alignment(AHF, Wyckoff) == True
    iff  sign(ahf_ict_direction) == sign(phase_direction(Wyckoff.phase))
    and  ahf_ict_direction != 0
    and  phase_direction(Wyckoff.phase) != 0
```

Es decir: el lock AHF y la fase Wyckoff apuntan al **mismo signo** y ambos están
resueltos (no neutrales/transición).

**Tabla de mapeo (ALIGNMENT):**

| AHF lock (`confirmed_context`) | Fase Wyckoff (`phase`) | Wyckoff dir | ALIGNMENT |
|---|---|---|---|
| D1 BULLISH (locked) | `MARKUP` / `ACCUMULATION` | +1 | ✅ TRUE |
| D1 BEARISH (locked) | `MARKDOWN` / `DISTRIBUTION` | −1 | ✅ TRUE |
| D1 BULLISH (locked) | `RANGE_UNCLASSIFIED`/`TRANSITION`/`UNKNOWN` | 0 | ❌ indeciso (no ALIGNMENT) |
| `WAIT_D1` / sin lock | cualquiera | — | ❌ dirección 0 → no ALIGNMENT |
| lock BULLISH | fase BEARISH | −1 | ❌ (ver CONFLICT, §4) |

**Correlato en el motor existente:** cuando `alignment == True`, el
`WyckoffSnapshot` resultante debe quedar en `phase_state = PRO_TREND` y
`ict_alignment = "ALIGNED"` (`engine/Wyckoff/classifier.py:43`), conservando su
política `WYCKOFF_CONTEXT_ONLY_NOT_ENTRY` (`types.py:126`).

---

## 4. Semántica de CONFLICT (requisito 2)

**Definición formal.** `conflict` = la dirección canónica AHF es **opuesta** a la
dirección de la fase Wyckoff, con ambas resueltas:

```
conflict(AHF, Wyckoff) == True
    iff  ahf_ict_direction != 0
    and  phase_direction(Wyckoff.phase) != 0
    and  sign(ahf_ict_direction) == - sign(phase_direction(Wyckoff.phase))
```

Es decir: el lock AHF dice +1 y la fase Wyckoff dice −1 (o viceversa).

**Tabla de mapeo (CONFLICT):**

| AHF lock (`confirmed_context`) | Fase Wyckoff | Wyckoff dir | CONFLICT |
|---|---|---|---|
| D1 BULLISH (locked) | `DISTRIBUTION`/`MARKDOWN` | −1 | ✅ TRUE |
| D1 BEARISH (locked) | `ACCUMULATION`/`MARKUP` | +1 | ✅ TRUE |
| lock BULLISH | fase BULLISH | +1 | ❌ (es ALIGNMENT, §3) |
| lock BULLISH | `TRANSITION`/`UNKNOWN` | 0 | ❌ indeciso (no CONFLICT) |

**Relación con `WyckoffSnapshot.conflict` ya existente.** El motor hoy marca
`conflict = True` (`types.py:106`) cuando la fase Wyckoff es opuesta al
`direction_hint` del MTFNavigator y hay evidencia de transición
(`engine/Wyckoff/classifier.py:44–46`). En WYCKOFF-7 ese flag interno se
**reesuelve contra el lock AHF** (§2.1): el CONFLICT de este contrato es el
mismo concepto, pero con fuente ICT canónica = AHF. El `_delta` del timeline ya
incluye las claves `ict_alignment` y `conflict` (`backtest/wyckoff_timeline.py:84–85`)
y su `interpretation` es `OBSERVATIONAL_DELTA_NOT_SIGNAL` (L100): eso confirma
que el motor ya trata esta relación como observacional, no señal.

---

## 5. Naturaleza diagnóstica — ni ALIGNMENT ni CONFLICT son señal de entrada (requisito 3)

Este contrato **mantiene y extiende** las políticas de no-entrada ya presentes:

| Política (código existente, NO modificar) | Archivo / línea | Significado |
|---|---|---|
| `AHF_STATE_NOT_ENTRY` | `engine/ahf.py:105` (`AHFSnapshot.to_dict`) | el AHF nunca emite entradas |
| `CONTEXT_STATE_NOT_ENTRY_SIGNAL` | `backtest/setup_builder.py:91` | la proyección Setup State es solo adaptación |
| `WYCKOFF_CONTEXT_ONLY_NOT_ENTRY` | `engine/Wyckoff/types.py:126` | el snapshot Wyckoff no es orden |
| `RUNTIME_BASIC_NOT_WYCKOFF_7` | `backtest/wyckoff_timeline.py:20` (`FSM_CONTRACT`) | la FSM vigente no es WYCKOFF-7 |
| `CLOSED_PREFIX_DIAGNOSTIC_ONLY` | `backtest/wyckoff_timeline.py:201` | el timeline es diagnóstico closed-prefix |
| `OBSERVATIONAL_DELTA_NOT_SIGNAL` | `backtest/wyckoff_timeline.py:100` | el delta no es señal |

**Reglas de este contrato:**

1. `alignment` y `conflict` son campos de **diagnóstico de coherencia** en el
   timeline (`backtest/wyckoff_timeline.py`), bajo la misma envoltura
   `CLOSED_PREFIX_DIAGNOSTIC_ONLY` / `OBSERVATIONAL_DELTA_NOT_SIGNAL`.
2. `conflict == True` **no** aborta, **no** invierte y **no** genera entrada;
   es un marcador de que el lock AHF y la fase Wyckoff discrepan (contexto para
   el observador humano / laboratorio, no input de un motor de ejecución).
3. `alignment == True` **no** autoriza trade; sólo indica acuerdo direccional.
   La autorización sigue sujeta a los gates científicos (GEN-000) y a
   `can_trade=false` vigente.
4. En WYCKOFF-7, `RUNTIME_BASIC_NOT_WYCKOFF_7` permanece como `FSM_CONTRACT` hasta
   que se cumpla el contrato de promoción (§6). Mientras tanto, cualquier
   `alignment`/`conflict` se registra pero no pivota la FSM hacia un estado de
   "setup Wyckoff completo".

---

## 6. Contrato de promoción a WYCKOFF-7 (requisito 4)

**Principio.** La FSM Wyckoff "completa" (capacidad de declarar un setup Wyckoff
con alignment/conflict como insumo de gate) **no puede promoverse** sin que
exista,_versionada y certificada, la evidencia de `EXP-WYCKOFF-ICT-01` que
demuestre que el contexto Wyckoff aporta información incremental por encima del
Context State ICT. Hoy esa evidencia **no existe con potencia suficiente**.

### 6.1 Estado actual de la evidencia (hecho, no opinión)

- Pre-registro: `docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md`
  (pre-registrado 2026-08-25; `can_train=false`, `can_trade=false`).
- Ejecución de preflight (v2, commit `e9c9be9` → `cdf45f1`): certificada
  independientemente el **2026-08-26** como
  **`CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N`**
  (`reports/audits/experiments/wyckoff_ict_01/certification/CERTIFICATION_VERDICT.md`).
- Conteos: H1 TOTAL = 515 observaciones; **máxima celda primaria = 361 ≪
  n_required = 389** (§5 del pre-registro, MDE 10 pp, potencia 0.80).
- Gates PIT: `GATE CAUSAL 0/120 PASS`, `GATE WYCKOFF PIT 0/80 PASS` (limpios de
  leakage), pero insuficientes en n.
- Consecuencia pre-registrada: cierre honesto `INSUFFICIENT_N`; prohibido ampliar
  el universo (EURUSD 20Y fijado) para llegar a n.

### 6.2 Evidencia que DEBE existir ANTES de la FSM Wyckoff completa

Para promover `RUNTIME_BASIC_NOT_WYCKOFF_7` → WYCKOFF-7, el repositorio debe
contener **todos** los siguientes artefactos con sus condiciones de paso:

| # | Artefacto requerido | Condición de paso (de `EXP_WYCKOFF_ICT_01_PREREGISTRATION.md`) | Estado hoy |
|---|---|---|---|
| E1 | Experimento `EXP-WYCKOFF-ICT-01` ejecutado (no solo preflight) con ancla `structure_bar`, dedup `(bar_k, direction)`, `context_bucket` relativo a `sequence_direction`, flag `CONFLICT` del `WyckoffSnapshot` | reproduce exactamente el contrato v2 corregido | ❌ solo preflight |
| E2 | `n` por celda primaria ≥ `n_required = 389` (MDE 10 pp, potencia 0.80, Bonferroni α≈0.0167) | todas las celdas de interés ≥ 389 | ❌ máx 361 |
| E3 | `GATE CAUSAL` (PIT `navigate(full,t)==navigate(prefix,t)`) 0 violaciones sobre la muestra | `PASS 0/N` | ✅ 0/120 (preflight) |
| E4 | `GATE WYCKOFF PIT` (ventana solo-pasado ≤ t) 0 violaciones | `PASS 0/N` | ✅ 0/80 (preflight) |
| E5 | Veredicto mecánico **`SUPPORTED`**: Δ(outcome \| Wyckoff dentro de ICT fijo) con IC95 bootstrap (cluster `chain_id`) que **excluye 0**, tras corrección por comparaciones múltiples, en ≥1 celda primaria (`ICT_ALIGNED × WYCKOFF_CONFLICT` vs `ICT_ALIGNED × NON_CONFLICT`, y análogo en `AGAINST`) | `SUPPORTED` (no `FALSIFIED`/`INSUFFICIENT_N`/`INVALID`) | ❌ `INSUFFICIENT_N` |
| E6 | Certificación independiente (3 revisores: reproducción + metodología + estadística) del artefacto E1–E5 | 3/3 PASS como en `certification/CERTIFICATION_VERDICT.md` | ❌ solo preflight fallido |
| E7 | Manifiesto con hashes de `engine/mtf_navigation.py`, `engine/sequential_events.py`, `engine/Wyckoff/*`, `generator_commit`, `generator_worktree` | presentes e inmutables | ❌ no ejecutado |
| E8 | Decisión explícita del cliente (Ruben) + autorización de promoción, con `can_trade` aún en `false` (Shadow Mode) | firma en `.hermes-index.md` / worklog | ❌ pendiente |

### 6.3 Gate de promoción (mecánico)

```
PROMOVER_A_WYCKOFF_7 == (E1 ∧ E2 ∧ E3 ∧ E4 ∧ E5 ∧ E6 ∧ E7 ∧ E8)
```

Hasta que `PROMOVER_A_WYCKOFF_7` sea `True`, el `FSM_CONTRACT` se mantiene en
`RUNTIME_BASIC_NOT_WYCKOFF_7` y el diagnóstico `alignment`/`conflict` se sigue
registrando bajo `CLOSED_PREFIX_DIAGNOSTIC_ONLY` / `OBSERVATIONAL_DELTA_NOT_SIGNAL`
(§5), sin pivotar la FSM.

### 6.4 Consecuencia honesta (no se fuerza PASS)

Dado que el universo está fijado (EURUSD 20Y, prohibido ampliar) y la población
observable es ~13–80× inferior al n requerido (`EXP-SEQ-CTX-01` documenta lo
mismo para ICT), **la promoción a WYCKOFF-7 está bloqueada estructuralmente**
bajo el diseño actual. Las únicas vías legítimas son: (a) un nuevo pre-registro
con ancla/universo/MDE distinto que alcance potencia, o (b) una decisión
explícita del cliente de ampliar universo (prohibido por el pre-registro vigente).
Ninguna de las dos existe hoy; por tanto el contrato de promoción **no se cumple**
y WYCKOFF-7 permanece en estado `RUNTIME_BASIC_NOT_WYCKOFF_7`.

---

## 7. Citas graphify (requisito 5 — archivos reales verificados en el grafo)

Grafo: `graphify-out/graph.json`, `built_at_commit = c1328ad` (HEAD actual
`c1328ad` → fresco, sin stale). Consultas ejecutadas:

- `graphify query "AHF AdaptiveHierarchicalFunnel state confirmed_context relation to WyckoffSnapshot ict_alignment conflict classify_alignment"` →
  BFS depth=2, 375 nodos; confirma `AdaptiveHierarchicalFunnel` (community 17),
  `WyckoffSnapshot`/`classify_alignment` (community 7), `MTFNavigator`
  (`engine/mtf_navigation.py#L394`) y `backtest/wyckoff_timeline.py` como único
  puente AHF→Wyckoff (sin borde directo hoy).
- `graphify explain "WyckoffSnapshot"` → `engine/Wyckoff/types.py#L96`, community 7,
  degree 5 (referenciado por `build_wyckoff_snapshot`, `adapter.py`, `types.py`,
  `__init__.py`, `.to_dict`).
- `graphify explain "classify_alignment"` → `engine/Wyckoff/classifier.py#L17`,
  community 7, degree 10 (llamado por `build_wyckoff_snapshot`; llama
  `phase_direction`; referencia `WyckoffPhase`/`WyckoffEvent`/`WyckoffPhaseState`).

Archivos reales citados (rutas canónicas del repo):

```
engine/ahf.py
engine/Wyckoff/types.py
engine/Wyckoff/classifier.py
engine/Wyckoff/adapter.py
engine/mtf_navigation.py
backtest/wyckoff_timeline.py
backtest/setup_builder.py
docs/experimentos/EXP_WYCKOFF_ICT_01_PREREGISTRATION.md
reports/audits/experiments/wyckoff_ict_01/certification/CERTIFICATION_VERDICT.md
.hermes-index.md
```

---

## 8. Contrato de promoción a WYCKOFF-7 (resumen ejecutivo — entregable)

> **WYCKOFF-7 no se promueve mientras `RUNTIME_BASIC_NOT_WYCKOFF_7` siga siendo
> el `FSM_CONTRACT`.**
>
> **Condición necesaria y suficiente:** que exista, versionada y certificada
> independientemente, la evidencia `EXP-WYCKOFF-ICT-01` con (E1) ejecución completa
> fiel al contrato v2, (E2) `n`≥389 por celda primaria, (E3) `GATE CAUSAL` 0/120
> PASS, (E4) `GATE WYCKOFF PIT` 0/80 PASS, (E5) veredicto mecánico `SUPPORTED`
> (Δ excluye 0 tras corrección múltiple en celda primaria), (E6) certificación 3/3,
> (E7) manifiesto con hashes inmutables, y (E8) autorización explícita del cliente
> con `can_trade=false`.
>
> **Estado actual:** `CERTIFIED_FEASIBILITY_FAIL_INSUFFICIENT_N` (2026-08-26) —
> máxima celda 361 ≪ 389; universo fijado sin ampliación permitida. **El contrato
> NO se cumple.** `alignment`/`conflict` siguen siendo diagnósticos bajo
> `CLOSED_PREFIX_DIAGNOSTIC_ONLY` / `OBSERVATIONAL_DELTA_NOT_SIGNAL`, nunca señal
> de entrada.
