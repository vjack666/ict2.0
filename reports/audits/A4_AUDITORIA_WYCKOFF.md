# AUDITORÍA WYCKOFF — TRAMO A4

**Plan vigente:** `.hermes/plans/2026-08-16_1510_PIPELINE_APRENDIZAJE_CIENTIFICO.md` (líneas 115‑134)
**Fecha de auditoría:** 2026‑08‑20
**Rama de auditoría:** `feature/a4-audit-wyckoff` (creada con `git checkout -b`)
**Modo:** DOCUMENTAL — lectura + documentación, cero modificaciones de código, cero nuevos módulos.
**Regla de Oro:** toda afirmación cita `archivo:línea` real del repositorio.

---

## 0. Hallazgos de contexto (discrepancias del plan)

| # | Discrepancia | Evidencia | Severidad |
|---|---|---|---|
| C‑1 | El plan declara `HEAD e6fceb7` en `origin/main`; `origin/main` real es `f453bf2` y el árbol de trabajo estaba en `feature/a3-audit-ict` (ahora `feature/a4-audit-wyckoff`). | `git rev-parse origin/main` → `f453bf2` | BAJA (contexto del plan obsoleto) |
| C‑2 | `PLAN_LTF_ENTRY_LAYER.md` define la fase **WYCKOFF‑6** (Documentación y cierre, línea 287) pero la tabla de gates (líneas 14‑19) sólo lista WYCKOFF‑0..5. | `docs/tesis/PLAN_LTF_ENTRY_LAYER.md:287` vs `:14‑19` | BAJA |
| C‑3 | `docs/wyckoff/00_indice.md:10` sigue citando `agents/wyckoff_agent.py` como el código Wyckoff, ignorando `engine/Wyckoff/`. | `docs/wyckoff/00_indice.md:10` | BAJA (deriva documental) |

Los 5 paths del alcance del plan **existen** (`engine/Wyckoff/`, `analysis/wyckoff_agent.py`, `agents/wyckoff_agent.py`, `docs/wyckoff/`, `docs/reglas/WYCKOFF_RULEBOOK.md`); no se reporta path inexistente a nivel de alcance.

---

## 1. Clasificación de Wyckoff

### 1.1 Autoridad runtime
- **Única autoridad runtime designada:** `engine/Wyckoff/` — `__init__.py:1` declara *"Autoridad runtime única de la capa Wyckoff especializada"*.
- `WyckoffSnapshot.to_dict()` incrusta `policy = "WYCKOFF_CONTEXT_ONLY_NOT_ENTRY"` (`engine/Wyckoff/types.py:126`), confirmando la política de "sólo contexto, no entrada".
- La SDD respalda la autoridad única: `docs/tesis/SDD_LTF_ENTRY_LAYER.md:47‑57` (tabla de autoridad por TF con `authority_tf` explícito) y `:360‑362` (el legacy *"no puede seguir siendo la autoridad silenciosa del brief"*).
- La decisión de migración ya documentada: `reports/audits/wyckoff_runtime_inventory_2026-08-20.md:36` — *"Se crea engine/Wyckoff/ como única autoridad runtime"*.

### 1.2 Legacy (segundo motor latente)
- `analysis/wyckoff_agent.py:11` define `class WyckoffAgent` — un **agente completo** con `_classify_phase`, `_detect_*`, `_compute_confidence` que devuelve `bias` + `confidence` (`analysis/wyckoff_agent.py:80‑89`).
- `agents/wyckoff_agent.py:3` es sólo un re‑export (compat).
- **Consumidores activos del legacy:** `orchestration/orchestrator.py:14` (import) y `:56` (`self.wyckoff = wyckoff_agent or WyckoffAgent()`); `scripts/smoke/smoke_consensus.py:30` y `:92`.
- `docs/REPOSITORY_MAP.md:136` lo confirma: *"Implementación de agente anterior al engine/Wyckoff/ | Activo como adaptador; migración progresiva"*.
- El inventario lo clasifica `ANALYSIS_ONLY / LEGACY_COMPAT` (`reports/audits/wyckoff_runtime_inventory_2026-08-20.md:11‑12`).
- **Riesgo de política:** en la ruta `orchestrator → decision_agent`, el legacy aporta un `bias` ponderado (ICT 0.35 / Wyckoff 0.30 / Structure 0.20 / ML 0.15, `analysis/decision_agent.py:13‑16`), actuando como un **segundo motor de señal** que alimenta la decisión. La ruta **autoritativa del brief** (`scripts/daily/brief_lunes.py:228,245` usa `engine.Wyckoff`) sí es conforme; el legacy persiste en rutas paralelas (WYCKOFF‑1 IN PROGRESS).

### 1.3 Eventos implementados
- **Enum `WyckoffEventType`** (`engine/Wyckoff/types.py:29‑40`): 11 tipos → `SPRING, UPTHRUST, UTAD, SOS, SOW, LPS, LPSY, TEST, FAILED_TEST, RANGE_BREAK, EFFORT_RESULT_DIVERGENCE`.
- **`detect_events` realmente emite 6** (`engine/Wyckoff/events.py`): `SPRING` (:46), `UPTHRUST` (:48), `SOS` (:50), `SOW` (:52), `LPS` (:65), `LPSY` (:67).
- **Los 6 eventos core del rulebook están cubiertos**: Spring (`WYCKOFF_RULEBOOK.md:50,145`), LPS (:50,238), Upthrust (:76,162), LPSY (:76,263), SOS (:193), SOW (:216).
- **Gap de cobertura (enum sobre‑declarado):** 5 tipos del enum **nunca son emitidos** por `detect_events`: `UTAD` (enum :32), `TEST` (:37), `FAILED_TEST` (:38), `RANGE_BREAK` (:39), `EFFORT_RESULT_DIVERGENCE` (:40). `EFFORT_RESULT_DIVERGENCE` sí se calcula en `effort_result.py` (campo `divergence`, :25) pero no como `WyckoffEvent`. El legacy `analysis/wyckoff_agent.py:67` sí emite `EFFORT_RESULT_DIVERGENCE` y `STOCH_DIVERGENCE` (:78) con otra metodología.

### 1.4 Cobertura de tests
- `tests/test_wyckoff_engine.py` (4 tests) cubre: serialización + autoridad explícita (:41), **causalidad / invarianza al futuro** (:56‑77), **conflicto como evidencia, nunca veto** (:80‑97), estados de fase explícitos (:100‑104).
- **No cubre:** modos de `volume_mode` (effort/result), emisión de `LPS`/`LPSY`/`UPTHRUST`/`SOW`, cobertura ampliada de `TRANSITION`/`NEUTRAL` (WYCKOFF‑3), retest/lineage (WYCKOFF‑4).
- **No existe test** para el legacy `analysis/wyckoff_agent.py`.

### 1.5 Causalidad de fase (no look‑ahead)
- **Cierre de prefijo:** `engine/Wyckoff/adapter.py:15‑22` (`_prefix` filtra `times <= decision_time`) → todo se computa sobre el prefijo cerrado.
- `detect_events` usa sólo barras previas + la fila actual (`engine/Wyckoff/events.py:26‑69`); `classify_phase` usa sólo el frame recibido (`phases.py:31‑55`); `measure_effort_result` usa sólo `tail` (`effort_result.py:11‑33`).
- **Test de invarianza al futuro presente** (`test_wyckoff_engine.py:56‑77`): añadir barras futuras no cambia el snapshot → **sin look‑ahead confirmado**.

### 1.6 Anomalía de semántica de fase (MEDIO)
- `classify_phase` asigna **BEARISH→ACCUMULATION** y **BULLISH→DISTRIBUTION** (`engine/Wyckoff/phases.py:44‑50`), pero `phase_direction` (consumidor) mapea **ACCUMULATION→+1 (bullish)** y **DISTRIBUTION→‑1 (bearish)** (`classifier.py:9‑14`). El mapeo fase↔dirección queda **invertido** respecto a su propio consumidor y al Wyckoff estándar.
- Peor aún: un rango **lateral real** (dirección ≈ UNKNOWN) cae en `RANGE_UNCLASSIFIED` (`phases.py:34‑39`, rama `if span <= typical_range*12` con `direction==UNKNOWN`), mientras que sólo ventanas con deriva direccional reciben ACC/DIST. Es decir, las acumulaciones/distribuciones canónicas (laterales) **no** se clasifican como tales; sólo las ventanas en transición lo hacen. Esto es inverso a la intención.
- Impacto: no rompe la política "no veto" (el conflicto/alineación sigue funcionando, a menudo como `RANGE_UNCLASSIFIED`/`NEUTRAL`), pero **degrada la calidad de fase**. Requiere test explícito y revisión.

### 1.7 Limitaciones de `tick_volume`
- `measure_effort_result` → `VolumeMode.UNAVAILABLE` si no hay columna `tick_volume` (`effort_result.py:11‑13`); si existe, devuelve **`RELATIVE_ONLY`** (:33) — **nunca absoluto**.
- `detect_events` calcula `volume_ratio` **sólo si** `tick_volume` está presente (`events.py:57‑61`); `LPS`/`LPSY` se detectan igual sin volumen (`low_volume_test=False`, :62‑67).
- `VolumeMode.AVAILABLE` (enum `types.py:44`) **nunca se asigna** en el código; sólo `UNAVAILABLE`/`RELATIVE_ONLY` (`adapter.py:89‑90`).
- `WyckoffSnapshot.volume_mode` por defecto `UNAVAILABLE` (`types.py:104`), sube a `RELATIVE_ONLY` sólo si alguna capa tiene volumen.
- **Limitación dominante:** en datos **OTC/binarias (Quotex)** el volumen real no existe; `tick_volume` es un proxy débil. El esfuerzo/resultado queda como `RELATIVE_ONLY` (o `UNAVAILABLE`), y LPS/LPSY/divergencia se degradan sin volumen. Confirmado por diseño: `reports/audits/wyckoff_runtime_inventory_2026-08-20.md:41‑42`.

### 1.8 Conflictos ICT ↔ Wyckoff
- `classify_alignment` (`classifier.py:17‑46`): calcula `wy_direction` vs `ict_direction`; devuelve `conflict=True` cuando son opuestos, pero **nunca cambia `ict_direction` ni emite veto** (docstring :24; ramas :42‑46).
- `daily_motor._wyckoff_payload` → *"Conserva Wyckoff como evidencia especializada, nunca como veto"* (`engine/daily_motor.py:320‑321`); `entry_authorized` es `False` por defecto (:386) y el conflicto Wyckoff no lo habilita.
- **Test de evidencia‑no‑veto:** `test_wyckoff_engine.py:80‑97` — conflicto Wyckoff presente, `direction_label` ICT se mantiene `BULLISH` y `entry_authorized=False`.
- **Riesgo de perímetro (BAJO):** `analysis/decision_agent.py` tiene `conflict_mode` (default `"soft"`) con opción `"hard"` que fuerza `NEUTRAL`/confianza 0.0 ante cualquier conflicto multi‑agente (:19‑21, :214‑229). Es una política de decisión genérica (no Wyckoff‑específica) y está en `soft` por defecto; el motor Wyckoff en sí **nunca** vetó. Recomendación: asegurar que la config siga en `soft` o eliminar la rama `hard` para honrar plenamente "no hard veto" en el perímetro.

### 1.9 Estado de gates WYCKOFF‑0..5
Fuente: `docs/tesis/PLAN_LTF_ENTRY_LAYER.md:14‑19` + inventario + SDD.

| Gate | Estado | Evidencia / nota de auditoría |
|---|---|---|
| **WYCKOFF‑0** Inventario | **PASS** | `reports/audits/wyckoff_runtime_inventory_2026-08-20.md` (commit `8e78718`) |
| **WYCKOFF‑1** Runtime | **IN PROGRESS** | `engine/Wyckoff/` creado, pero `analysis/wyckoff_agent.py` aún tiene consumidores (`orchestrator.py`, `smoke_consensus.py`) → "segundo motor" latente (ver 1.2) |
| **WYCKOFF‑2** LTF/MTF | **IN PROGRESS** | `daily_motor._wyckoff_payload` (:320) y `brief_lunes.py:228,245` consumen `WyckoffSnapshot`; capas D1/H4/H1/M15 soportadas (`adapter.py:64`) |
| **WYCKOFF‑3** Clasificación ICT | **IN PROGRESS** | `PRO_TREND`/`COUNTERTREND`/conflicto probados (`test_wyckoff_engine.py:100‑104`); `TRANSITION`/`NEUTRAL` y la anomalía de fase (1.6) requieren cobertura ampliada |
| **WYCKOFF‑4** Retest | **PARTIAL** | snapshot convive con zona/retest canónicos; `evidence_refs`/`source_ref` dan provenancia por evento (`events.py:13,20`; `types.py:73‑78`), pero **lineage completo pendiente** |
| **WYCKOFF‑5** Histórico/MT5 | **PENDING** | falta evidencia versionada con la nueva capa (ningún reporte histórico/MT5 nuevo encontrado) |

---

## 2. Política Wyckoff — cumplimiento

| Política (plan línea 132) | Estado en el motor canónico | Evidencia |
|---|---|---|
| Sólo contexto | ✅ CUMPLE | `types.py:126` `WYCKOFF_CONTEXT_ONLY_NOT_ENTRY`; `daily_motor.py:386` `entry_authorized=False` |
| Régimen / evidencia / conflicto | ✅ CUMPLE | `WyckoffSnapshot` transporta `phase`, `events`, `ict_alignment`, `conflict` como evidencia |
| No segundo motor | ⚠️ PARCIAL | Motor canónico = snapshot read‑only; PERO legacy `analysis/wyckoff_agent.py` sigue activo en `orchestrator`/`smoke` (WYCKOFF‑1) |
| No segundo Context State | ✅ CUMPLE | `context_state` es **sólo entrada** (`adapter.py:25‑33,83`); el motor no crea estado |
| No hard veto | ✅ (motor) / ⚠️ (perímetro) | Motor nunca vetó (1.8); `decision_agent` tiene rama `hard` off‑por‑defecto (1.8) |
| No generador autónomo de entradas | ✅ CUMPLE | `WyckoffSnapshot` no produce señal/orden; `entry_authorized` siempre `False` |

---

## 3. Lista de HALLAZGOS

| ID | Severidad | Hallazgo | Evidencia |
|---|---|---|---|
| F‑1 | MEDIO | `classify_phase` asigna fase con dirección **invertida** vs `phase_direction` y clasifica rangos laterales como `RANGE_UNCLASSIFIED`, no como ACC/DIST. | `phases.py:44‑50`, `classifier.py:9‑14`, `phases.py:34‑39` |
| F‑2 | MEDIO | **Segundo motor latente:** `analysis/wyckoff_agent.py` (agente completo bias+conf) sigue activo en `orchestrator`/`smoke` y aporta peso a la decisión. | `orchestrator.py:14,56`; `smoke_consensus.py:30,92`; `decision_agent.py:13‑16` |
| F‑3 | BAJO | Enum `WyckoffEventType` sobre‑declara: 5 tipos (`UTAD, TEST, FAILED_TEST, RANGE_BREAK, EFFORT_RESULT_DIVERGENCE`) **nunca emitidos** por `detect_events`. | `types.py:29‑40` vs `events.py:26‑69` |
| F‑4 | BAJO | `tick_volume` es `RELATIVE_ONLY` (o `UNAVAILABLE`); sin volumen real en OTC, se degrada esfuerzo/resultado y LPS/LPSY. | `effort_result.py:11‑33`; `events.py:57‑67`; inventario `:41‑42` |
| F‑5 | BAJO | Riesgo de perímetro: `decision_agent` tiene rama `hard` veto (default `soft`); recomendable excluir/eliminar para honrar "no hard veto". | `decision_agent.py:19‑21,214‑229` |
| F‑6 | BAJO | Deriva documental: `docs/wyckoff/00_indice.md:10` y `REPOSITORY_MAP.md:136` citan el legacy como código Wyckoff; el brief usa `engine/Wyckoff`. | `00_indice.md:10`; `REPOSITORY_MAP.md:136` |
| F‑7 | BAJO | Cobertura de test parcial: no cubre modos de volumen, emisión LPS/LPSY/UPTHRUST/SOW, ni lineage/retest; legacy sin tests. | `tests/test_wyckoff_engine.py` (4 tests) |
| F‑8 | BAJO | WYCKOFF‑5 PENDING: falta evidencia histórica/MT5 versionada de la nueva capa. | `PLAN_LTF_ENTRY_LAYER.md:19` |
| C‑1/C‑2/C‑3 | BAJO | Discrepancias de contexto del plan (HEAD obsoleto, WYCKOFF‑6 fuera de tabla, doc índice legacy). | sección 0 |

---

## 4. VEREDICTO — GATE A4

### ✅ **PASS — Wyckoff clasificado como componente experimental/contextual con límites explícitos.**

**Justificación:**
1. El motor **canónico** (`engine/Wyckoff/`) es conforme a la política: read‑only, serializable, closed‑only, `policy=WYCKOFF_CONTEXT_ONLY_NOT_ENTRY`, `entry_authorized=False`, sin segundo Context State, sin veto (confirmado por código y por `test_wyckoff_engine.py:80‑97`).
2. **Causalidad verificada:** prefijo cerrado en `adapter._prefix` (`adapter.py:15‑22`) + test de invarianza al futuro (`test_wyckoff_engine.py:56‑77`) → sin look‑ahead.
3. **Límites explícitos documentados:** `tick_volume` `RELATIVE_ONLY`/`UNAVAILABLE` (F‑4), cobertura de eventos parcial (F‑3), gates WYCKOFF‑1..5 no cerrados (tabla 1.9), anomalía de fase (F‑1), segundo motor legacy latente (F‑2).

**Condición / límite explícito que acompaña el PASS:** el PASS es sobre la **capa canónica** `engine/Wyckoff/`. Subsiste un **segundo motor legacy** (`analysis/wyckoff_agent.py`) activo en rutas `orchestrator`/`smoke` (F‑2, WYCKOFF‑1 IN PROGRESS) que debe retirarse para cumplir estrictamente "no segundo motor". Hasta entonces, Wyckoff queda clasificado como **experimental/contextual con límites explícitos** — exactamente el criterio del GATE A4.

---

## 5. Entrega / trazabilidad

- **Rama:** `feature/a4-audit-wyckoff` (creada desde el árbol de trabajo actual; no se tocó `audit_state.json` ni `exp_seq_x_context*`).
- **Documento:** `reports/audits/A4_AUDITORIA_WYCKOFF.md` (convención existente en `reports/audits/`).
- **Commit:** *[semántico, sólo el documento — ver hash tras `git commit`]*.
- **Bloqueos:** ninguno que impida el PASS. Limitaciones documentadas en §1.6, §1.7, §1.9 y tabla de hallazgos. No se ejecutó código ni se modificó ningún módulo (auditoría documental pura).

### Separación IDENTITY ≠ LINK ≠ CAUSALITY (requerida por el plan)
- **IDENTITY:** `engine/Wyckoff/` es la autoridad runtime (tipos + adapter + classifier + events + phases + effort_result). `analysis/wyckoff_agent.py` es un agente legacy distinto (misma "familia Wyckoff", identidad de código distinta).
- **LINK:** `daily_motor._wyckoff_payload` ← `WyckoffSnapshot` (`daily_motor.py:320,393`); `brief_lunes.py:228,245` ← `build_wyckoff_snapshot`; `classifier.classify_alignment` ← `phase` + `ict_direction` (`adapter.py:84`).
- **CAUSALITY:** `build_wyckoff_snapshot` es **pura y prefix‑closed** (sin barras futuras); `classify_alignment` es **determinista y no muta** la dirección ICT. No hay causalidad circular: Wyckoff *consume* `context_state.direction_hint` (`adapter.py:25‑33`) pero no lo produce.
