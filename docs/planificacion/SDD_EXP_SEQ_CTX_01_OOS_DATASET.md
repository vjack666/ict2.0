# SDD — EXP-SEQ-CTX-01: validación OOS, separación de modos y dataset offline

**Estado:** PLAN (no ejecutado)
**Fecha:** 2026-08-23
**Autor:** Hermes (Dirección de Laboratorio) bajo `AGENTS.md` / `autonomy_policy.md`
**Alcance:** los 4 ítems del Director para madurar EXP-SEQ-CTX-01 de
"gate INVALIDATED" a "evidencia OOS congelada, sin leakage, no operativa".
**No autoriza:** entry, PnL operativo, promoción, ni modelo en producción.

---

## 0. Contexto

EXP-SEQ-CTX-01 (rediseño de `EXP_SEQUENCE_X_CONTEXT_STATE`) descubrió que el
motor de navegación MTF tiene leakage en la capa H1 (`_causal_swings` ventana
centrada mira futuro → gate causal 31/120 violaciones → SUSPENDIDO). Hasta
cerrar esa raíz, la matriz S×Context no se ejecuta.

Los 4 ítems de esta lista son **trabajo de maduración científica independiente**
del gate causal: incluso con el motor limpio, el experimento necesita (a) validar
el modo `lite` por separado de `canonical_bos`, (b) evidencia OOS robusta con
holdout pre-registrado, (c) un contrato de datos congelado sin leakage, y
(d) un dataset offline versionado y no operativo. Este SDD los registra como
plan; el cumplimiento de cada ítem se hace contra este documento.

---

## ÍTEME 1 — Cerrar validación de `lite` y separar `canonical_bos` de `structure_mode=lite`

### 1.1 Hecho verificado (código actual)
- `engine/sequential_events.py:76` define `structure_mode: str = "canonical_bos"  # canonical_bos | lite`.
- `:291-292` ramifica: `canonical_bos` usa `BOSTool` completo; `lite` usa BOS-lite (cierre más allá del último swing).
- Consumidores distintos: `ltf_canonical_feed.py:64` usa `canonical_bos`; el navigator de índice usa `canonical_bos` con `max_active_chains=10_000_000` (`mtf_navigation.py:729`).
- `EXP_SEQUENTIAL_EXPECTANCY_DEPTH4_LITE_H1` (2019-2024 acotado) ya corrido con `lite` → **GATE PASS** (WR 54.5% vs 43.9% baseline, Δ+10.6pp).

### 1.2 Plan
- **No mezclar**: `canonical_bos` y `lite` se reportan SIEMPRE como filas separadas. Nunca un "modo mixto".
- **Validación de `lite` (cierre)**: re-ejecutar `lite` sobre el rango 20Y (no solo 2019-2024) con las mismas métricas del EXP lite (WR Wilson95, meanR, bootstrap por `chain_id`, seed 42) para cerrar la validación fuera del rango acotado.
- **Separación canónica**: documentar en `CONTRATO_SEQUENTIAL_EVENTS.md` (o addéndum) qué significa cada modo y que `canonical_bos` es la raíz del funnel 20Y mientras `lite` es modo de ablación/validación. El EXP-SEQ-CTX-01 usará `canonical_bos` como modo primario y `lite` como ablation explícita.
- **Criterio de cierre**: `lite` 20Y con n≥30/bucket y Δ WR estable vs baseline → validación cerrada; si `lite` 20Y rompe el gate del EXP lite acotado, se documenta la deuda de rango.

---

## ÍTEME 2 — Mejorar la evidencia OOS (holdout ampliado, PRE-REGISTRADO)

### 2.1 Problema
El holdout actual es "solo 7/7 por bucket" (n insuficiente por celda; el EXP
legado cayó en `INSUFFICIENT_N` con n=24). No se puede afirmar robustez OOS.

### 2.2 Regla de oro (anti-p-hacking)
- La ampliación del holdout se **registra aquí, antes de ver resultados**.
- **No se ajustan criterios ni horizontes tras ver resultados.** El horizonte
  de outcome (T+6/12/24/48) y los umbrales n≥30 están congelados en §3.
- Aumento de observaciones = ampliar el universo temporal (20Y completo) y/o
  relajar la restricción de depth (incluir depth≥3 además de ≥4) **como decisión
  previa**, no como reacción al número.

### 2.3 Plan de ampliación pre-registrada
- Universo: EURUSD H1 20Y completo (2006-2025, 124.377 barras) en lugar de
  2019-2024 acotado.
- Incluir depth ≥ 3 y ≥ 4 como dos niveles de análisis (no para inflar, sino para
  medir estabilidad de efecto por profundidad).
- Split temporal ROLL-FORWARD (no aleatorio), alineado con `b3_walkforward.py`:
  - TRAIN ≤ 2018 · VAL 2019-2021 · TEST 2022
  - TRAIN ≤ 2019 · VAL 2022 · TEST 2023
  - … hasta TEST 2026 (5 folds anuales).
- Por cada celda (S × Context) se reporta n por fold; solo se interpretan celdas
  con n≥30 en el fold TEST.
- El "7/7" se reemplaza por "n≥30 por celda en ≥ K de los 5 folds TEST con
  dirección de efecto consistente".

---

## ÍTEME 3 — Congelar el contrato de datos (sin leakage)

### 3.1 Esquema de cada ejemplo (fila del dataset)
Cada fila contiene **únicamente** información disponible en T (point-in-time):

| Campo | Origen | Ventana |
|---|---|---|
| `t` (ancla) | barra del nodo k de la cadena | — |
| `symbol`, `tf` | fijo (EURUSD H1) | — |
| `secuencia` | stages visibles hasta k (`direction + stages_present_hasta_k`) | solo barras ≤ t |
| `contexto_mtf` | `MTFNavigator.navigate(t)` → D1 bias × H4 location × H1 alignment relativo a la dirección de la secuencia → ALIGNED/NEUTRAL/AGAINST | solo barras ≤ t |
| `label_T+6 / T+12 / T+24 / T+48` | continuation/reversal/failure a N barras futuras | **solo barras > t** |
| `depth` | k (dimensión extra, no identidad) | — |

### 3.2 Anti-look-ahead (obligatorio, heredado de `CONTRATO_CONTEXT_STATE.md` §4)
- Contexto MTF usa solo `close_time ≤ t` (gate as-of).
- El label usa solo barras `> t` (futuro puro).
- El motor de navegación debe pasar el **gate causal full-vs-prefix** (ítem
  previo del experimento) antes de generar contexto para el dataset; si no, el
  dataset se marca `BLOCKED` y no se usa.
- Ruptura de outcome = rango de la secuencia (no `high[bar_k]` aislado) para
  evitar el artefacto 94% continuation de LIQUIDITY_POOL.

### 3.3 Regla congelada del bucket

`context_bucket` no se deriva de `allow_long`, `allow_short` ni del
`direction_hint` del navegador. La fábrica debe guardar y usar explícitamente
`sequence_direction`, `d1_bias`, `h4_location` y `h1_alignment`. La puntuación
normativa es la del contrato de datos: D1 y H4 se puntúan relativos a la
dirección de la secuencia, H1 aporta `+1/0/-1`, y los umbrales son `>=2`
ALIGNED, `<=-2` AGAINST y NEUTRAL en otro caso.

### 3.3 Congelamiento
Este esquema es el **contrato de datos**: una vez escrito, no se añaden columnas
posteriores al label ni se re-etiqueta según resultados.

---

## ÍTEME 4 — Dataset offline versionado (hashes, splits, can_trade=false)

### 4.1 Generación
- Script: `scripts/lab/experiments/exp_seq_ctx_01_dataset.py` (nuevo, siguiendo
  el patrón de `b2_dataset_factory.py`: hash + manifest).
- Salida implementada: `data/learning/seq_ctx_01/` con dos JSONL separados y
  `manifest.json`:
  `SEQ_CTX_01_CANONICAL_BOS.jsonl`, `SEQ_CTX_01_LITE.jsonl` y
  `exclusions_report.json`.
  El manifest registra:
  `{dataset_id, symbol, tf, period, generator_commit, schema_version,
    feature_schema, label_schema, rows_by_split, sha256_per_split,
    structure_mode, canonical_gate_status`, junto con hashes canónicos del
  payload, hashes de fuentes relevantes y estado del worktree.
- Cada dataset se hashea con la definición canónica del contrato; el campo
  `dataset_sha256` se excluye del propio payload para evitar circularidad.

### 4.2 Splits temporales
- DESIGN / VALIDATION / HOLDOUT por corte temporal (§2.3), nunca aleatorio.
- Manifest registra los bordes de cada split.

### 4.3 No operativo
- `can_trade = false` se escribe en el manifest y en el header de cada ejemplo.
- No hay módulo de inferencia en el loop de trading; el dataset es para
  evaluación OOS estadística únicamente.
- No es un modelo operativo: solo datos + etiquetas + splits versionados.

---

## 5. Orden de ejecución (dependencias)

1. **Gate causal del motor** (fuera de este SDD, pero bloquea): cerrar raíz
   `_causal_swings` antes de generar contexto para el dataset.
2. **Ítem 1**: validación `lite` 20Y + separación documentada.
3. **Ítem 3**: congelar contrato de datos (este documento §3 es la fuente).
4. **Ítem 4**: generar dataset offline versionado (requiere ítems 1 y 3).
5. **Ítem 2**: ampliación OOS pre-registrada sobre el dataset (requiere ítem 4).

## 6. Guardas de integridad

- `status: BLOCKED` si el gate causal del motor no es PASS.
- `status: INVALIDATED` si algún ejemplo tiene `contexto_mtf` con `time > t`
  (leakage detectado por re-chequeo as-of).
- Sin ajuste de horizonte/criterio post-resultado (anti-p-hacking).
- Commit por objetivo; push/integración solo con autorización expresa.

## 7. Archivos de este plan

- Este SDD: `docs/planificacion/SDD_EXP_SEQ_CTX_01_OOS_DATASET.md`
- Datos: `data/learning/seq_ctx_01/` (nuevo)
- Generador: `scripts/lab/experiments/exp_seq_ctx_01_dataset.py` (nuevo)
- Reusa: `b2_dataset_factory.py` (patrón hash/manifest), `b3_walkforward.py`
  (roll-forward), `CONTRATO_CONTEXT_STATE.md`, `CONTRATO_SEQUENTIAL_EVENTS.md`

## 8. Estado de implementación posterior (2026-08-24)

- Dataset V3 regenerado y validado: 292 filas; Gate OOS `SUBPOWERED`.
- Snapshot certificado materializado para ambos modos como artefacto de
  infraestructura; no equivale a suficiencia OOS ni a entrenamiento.
- `TrainingPipeline` ejecutado únicamente como skeleton contractual:
  `model_training.executed=false`, sin pesos aprendidos.
- Registry/checkpoints y Shadow Mode se mantienen con `can_trade=false`, sin
  promoción ni operación.
- La bitácora `2026-08-24_MISION_REGEN_OOS_GATE.md` es la fuente de detalle de
  la comparación V2/V3 y de las decisiones pendientes del cliente.

---

## 9. Reconciliación de ampliación OOS multi-símbolo (2026-08-24, fecha de cierre)

**HECHO VERIFICADO — ejecución de ampliación pre-registrada:**
Se ejecutó `scripts/lab/experiments/exp_seq_ctx_01_oos_expansion.py` (pre-registro en
`docs/planificacion/OOS_EXPANSION_PREREGISTRATION.md`) sobre el universo de 8 símbolos
× {canonical_bos, lite} × HOLDOUT 2021–2025 (+ EURUSD DESIGN/VALIDATION). El universo
pre-registrado se **agotó** (los 8 símbolos procesados).

**Conteos HOLDOUT agregados (evidencia en `data/learning/seq_ctx_01/OOS_EXPANSION/`):**
- `canonical_bos`: ALIGNED=19, NEUTRAL=110, AGAINST=23
- `lite`: ALIGNED=24, NEUTRAL=177, AGAINST=44
- Total ampliación = 625 filas (236 canonical + 389 lite); HOLDOUT = 397 filas.

**VEREDICTO (estadístico independiente, FASE 6):**
`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE` — 3 de 6 celdas (canonical ALIGNED,
canonical AGAINST, lite ALIGNED) quedaron < 30 pese a agotar el universo. NO se rebajó
el umbral `n>=30`. NO se combinaron celdas.

**Red Team (FASE 10):** `PASS_READY_FOR_CERTIFIED_SNAPSHOT` **SOBRE LA INTEGRIDAD**
(no leakage, no mezcla canonical/lite, buckets reconstruibles 100%, `can_trade=false`).
Esto NO equivale a suficiencia OOS.

**Snapshot (FASE 9):** NO creado — `exp_seq_ctx_01_oos_snapshot.py` requiere OOS_SUFFICIENT
y permanece bloqueado por diseño. `can_trade=false` preservado.

**Estado de EXP-SEQ-CTX-01 (expresión canónica):**
`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE` — 625 filas totales, 397 HOLDOUT,
canonical_bos 19/110/23, lite 24/177/44, 3/6 celdas < n>=30, sin snapshot elegible,
sin entrenamiento, sin edge, sin promoción, `can_trade=false`.

**DEUDA DOCUMENTAL / PROVENANCE detectada en esta reconciliación:**
1. Este SDD §8 y el addendum (§7) describen solo V3 (EURUSD, SUBPOWERED). No mencionan
   la ampliación multi-símbolo ni el veredicto EXHAUSTED. Se añade esta sección para
   cerrar la brecha; el addendum debe actualizarse aparte por el PMO.
2. `data/learning/seq_ctx_01/OOS_EXPANSION/manifest.json` carece del campo `total_rows`
   (sí lo tiene `OOS_EXPANSION_COUNTS.json`, que suma 625). El validador oficial
   `validate_seq_ctx_dataset.py` no se aplica a este manifest de ampliación (usa claves
   distintas); la integridad se verificó vía red team, no vía ese validador.
3. `gate_causal.json` NO registra `generator_commit` ni hashes de fuente; su
   `motor_lineage` es solo textual. No es reproducible verificar contra qué código exacto
   se corrió (aunque los hashes actuales de `engine/mtf_navigation.py` /
   `engine/sequential_events.py` coinciden con los del manifest V3/OOS).
4. El worktree está `DIRTY` (datasets `data/raw/EURUSD/EURUSD_M1.parquet` y
   `EURUSD_M5.parquet` modificados sin commit, entre otros). El dataset NO es
   reproducible desde un checkout limpio hoy; requiere commit autorizado del cliente.

**Autoridad:** la evidencia en disco (`OOS_EXPANSION/manifest.json`,
`OOS_SUFFICIENCY_VERDICT.json`, `OOS_REDTEAM_VERDICT.json`) manda sobre cualquier
texto de planificación desactualizado.
