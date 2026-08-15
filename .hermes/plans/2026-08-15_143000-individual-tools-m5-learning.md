# Plan: Herramientas ICT individuales + Aprendizaje M5 (plantilla de gráfico vela-a-vela)

> **For Hermes:** Modo plan. No ejecutar. Implementar task-by-task con subagent-driven-development cuando el Director apruebe.

**Goal:** Construir, una por una, herramientas de lectura ICT (BOS, CHOCH, FVG, OB, displacement, bias/TF, liquidez/sweep) que operen SOBRE M5, 1 mes de datos, de forma INDIVIDUAL e AISLADA; y un subsistema de APRENDIZAJE donde cada herramienta registra su desempeño, un agente trader humano + el Director califican, y Hermes entrega SOLO un veredicto por encima de lo esperado. Base del futuro "estilo plantilla de gráfico" que evoluciona vela a vela.

**Architecture:** Cada detector ya existe en `engine/` y `detectors/` como función aislada. Fase 1 = envolver cada uno en un módulo `tools/<tool>.py` que: (a) corre sobre un DataFrame M5 de 1 mes, (b) emite eventos vela-a-vela, (c) escribe su resultado a un log append-only de aprendizaje. Un orquestador `learning/` recoge los logs, los presenta al agente trader humano (vía archivo/markdown, no interactivo), y Hermes produce un INFORME RESUMIDO (solo lo que supera el umbral esperado). NO hay backtest de rendimiento (prohibido por el Director). El sesgo HTF para M5 se lee de D1/H4/H1 ya disponibles en `data/raw`.

**Tech Stack:** Python 3.11 (venv ICT SYSTEM), pandas, parquet (`data/raw/<SYM>/<SYM>_M5.parquet`), detectores existentes (`detectors/*.py`, `engine/*.py`).

---

## RESTRICCIONES DURAS (del Director)
- INDIVIDUAL PRIMERO: una herramienta a la vez, aislada. No ensamblar setups aún.
- Solo M5, solo 1 mes de datos. Suficientes setups en un mes.
- Vela a vela: la plantilla futura marca alto/bajo → BOS/CHOCH según tesis; bias por TF; aparece FVG/OB/etc. Fase 1 solo prepara los ladrillos individuales.
- APRENDIZAJE con calificador humano: agente trader humano + Director califican; Hermes NO entrega detalle, solo resultado por encima de lo esperado.
- Sin backtest (regla del Director).
- Hermes entrega SOLO lo que está "por encima de lo esperado" — el resto queda en los logs, no en el informe.

---

## INVENTARIO REAL DE HERRAMIENTAS (verificado en repo)
Ya existen como funciones aisladas (se envuelven, no se reescriben):
1. BOS — `detectors/bos.py::detect_bos` / `engine/bos/structure.py::detect_market_structure`
2. CHOCH — `detectors/choch.py::detect_choch`
3. FVG — `detectors/fvg.py::detect_fvg` / `engine/fvg_poi.py::detect_fvg`
4. OB (Order Block) — `detectors/ob.py::detect_order_blocks` / `engine/order_block.py::detect_order_blocks`
5. Displacement — `detectors/displacement.py::detect_displacement`
6. Bias/Trend por TF — `detectors/trend.py::detect_trend` / `engine/bias/*`
7. Liquidez / Sweep — `detectors/liquidity.py::detect_liquidity` / `engine/liquidity_levels.py::detect_liquidity_htf` / `engine/micro.py::detect_m1_liquidity_sweeps`
8. Swing high/low — soporte interno de BOS/CHOCH (no separado aún; Fase 1 lo expone como herramienta `swing`).

---

## FASE 1 — HERRAMIENTAS INDIVIDUALES (una por una)

### Task 1: Esqueleto `tools/` + contrato de evento vela-a-vela
**Objective:** Definir la interfaz común que TODA herramienta individual cumplirá.
**Files:** Create `tools/base.py`, `tools/event.py`
- `event.py`: dataclass `ToolEvent(bar_index, time, symbol, tf, tool_name, signal, detail, confidence_raw)`.
- `base.py`: clase `SingleTool` con `run(df_m5, context) -> list[ToolEvent]` y `log_path`.
**Step:** escribir, sin ejecutar aún. Commit.

### Task 2: Herramienta SWING (alto/bajo) — la base de la plantilla
**Objective:** Primera herramienta individual: marca swing high/low vela a vela (es el ladrillo de "alto o bajo" de la plantilla futura).
**Files:** Create `tools/swing.py`
- usa `_swing_points` / `_label_swings` ya en `engine/bos/structure.py` o `detectors/bos.py`.
- emite `ToolEvent(tool='swing', signal='HH'|'LH'|'HL'|'LL')`.
**Test:** sobre 100 velas M5 sintéticas, confirma que marca el primer swing. Commit.

### Task 3: Herramienta BOS (individual)
**Objective:** BOS aislado sobre M5.
**Files:** Create `tools/bos.py` (envuelve `detectors/bos.detect_bos`).
- `ToolEvent(tool='bos', signal='BOS_UP'|'BOS_DOWN', level, idx)`.
**Test:** M5 EURUSD 1 mes → cuenta BOS y muestra 5 primeros con índice/nivel. Commit.

### Task 4: Herramienta CHOCH (individual)
**Objective:** CHOCH aislado.
**Files:** Create `tools/choch.py`.
**Test:** igual que BOS. Commit.

### Task 5: Herramienta FVG (individual)
**Objective:** FVG aislado, con tier (T1/T2) ya calculado por `detectors/fvg`.
**Files:** Create `tools/fvg.py`.
**Test:** muestra FVG con mid/tier/fill. Commit.

### Task 6: Herramienta OB (individual)
**Objective:** Order Block aislado.
**Files:** Create `tools/ob.py`.
**Test:** muestra OB top/bottom. Commit.

### Task 7: Herramienta DISPLACEMENT (individual)
**Objective:** Impulso direccional aislado.
**Files:** Create `tools/displacement.py`.
**Test:** muestra velas con flag displacement. Commit.

### Task 8: Herramienta BIAS/TREND por TF (individual)
**Objective:** Sesgo D1/H4/H1 leído para contexto de M5 (la "lectura de bias de diferentes temporalidades" de la plantilla).
**Files:** Create `tools/bias.py` (usa `detectors/trend.detect_trend` + `engine/bias`).
- emite sesgo por TF, no mezcla.
**Test:** sobre M5 EURUSD, lee D1/H4/H1 y reporta 3 sesgos por separado. Commit.

### Task 9: Herramienta LIQUIDEZ / SWEEP (individual)
**Objective:** Niveles BSL/SSL y barridas aisladas.
**Files:** Create `tools/liquidity.py` (usa `detectors/liquidity` + `engine/liquidity_levels`).
**Test:** muestra BSL/SSL y sweeps. Commit.

---

## FASE 2 — APRENDIZAJE INDIVIDUAL (por herramienta)

### Task 10: Log append-only de aprendizaje
**Objective:** Cada herramienta escribe sus eventos + un campo `human_score` (vacío) a `data/learning/<tool>/<sym>_M5_<mes>.jsonl`.
**Files:** Modify `tools/base.py` para escribir jsonl; Create `data/learning/` (gitkeep).
**Test:** correr BOS sobre 1 mes → el jsonl existe y tiene N líneas. Commit.

### Task 11: Hoja de calificación para agente trader humano
**Objective:** Generar, por herramienta, un markdown de MUESTRA (primeros 20-30 eventos con contexto de velas) que el agente trader humano + Director califican (correcto/incorrecto/duudoso).
**Files:** Create `learning/export_review.py` → `data/learning/<tool>/review_<tool>.md`.
**Test:** genera el md con 20 eventos BOS y su contexto. Commit.

### Task 12: Agregador de calificación + umbral "por encima de lo esperado"
**Objective:** Tras calificación humana, `learning/aggregate.py` lee jsonl con `human_score`, calcula % acierto por herramienta, y define umbral esperado (p.ej. baseline 50%). Solo reporta hallazgos > umbral.
**Files:** Create `learning/aggregate.py`.
**Test:** con jsonl de ejemplo (mezcla de scores), imprime "herramienta X: 72% (>50% esperado) — SOBRESALIENTE". Commit.

### Task 13: Informe de Hermes (SOLO lo por encima de lo esperado)
**Objective:** `learning/hermes_report.py` produce un INFORME CORTO que NO lista detalle, solo: qué herramienta superó el umbral, en cuánto, y una recomendación de ajuste. Esto cumple "a mi solo me entregas un resultado por encima de lo esperado".
**Files:** Create `learning/hermes_report.py` → `docs/learning/report_<fecha>.md`.
**Test:** corre sobre agregado de ejemplo, entrega solo la línea sobresaliente. Commit.

---

## FASE 2B — DOCUMENTACIÓN DE APRENDIZAJE (EXHAUSTIVA, obligatoria para aprender)
> El Director exige documentación hasta el último detalle: para aprender se lleva bitácora viva, no solo salida.

### Task 13b: Contrato documentado por herramienta (anclado a tesis)
**Objective:** Por cada herramienta individual, crear `docs/tools/<tool>.md` que diga QUÉ mide, de qué libro/tesis ICT sale el criterio (cita capítulo), y qué SALIDA emite. Esto evita reglas hardcoded sin justificación y deja trazabilidad de aprendizaje.
**Files:** Create `docs/tools/swing.md`, `docs/tools/bos.md`, `docs/tools/choch.md`, `docs/tools/fvg.md`, `docs/tools/ob.md`, `docs/tools/displacement.md`, `docs/tools/bias.md`, `docs/tools/liquidity.md`.
- Cada uno cita la fuente tesis (ej. BOS/CHOCH → libro de Market Structure; FVG → libro 05/06).
**Test:** los 8 md existen y cada uno referencia un capítulo de tesis. Commit.

### Task 13c: Bitácora de aprendizaje acumulativa
**Objective:** `data/learning/LEARNING_JOURNAL.md` (append-only) donde se registra, por herramienta y fecha: muestra usada, calificación humana (con quién calificó: agente trader humano / Director), decisión de ajuste tomada, y POR QUÉ. Es la memoria de aprendizaje del sistema.
**Files:** Create `learning/journal.py` (append a `data/learning/LEARNING_JOURNAL.md`) + el md inicial.
**Test:** tras una calificación de ejemplo, el journal tiene 1 entrada con los 4 campos. Commit.

### Task 13d: Registro de ajustes de parámetros (trazabilidad de cambio)
**Objective:** Cuando tras calificar se cambia un parámetro de una herramienta, `learning/adjust.py` registra: herramienta, parámetro anterior → nuevo, motivo (cita journal entry), fecha. Esto permite auditar CÓMO evolucionó cada herramienta.
**Files:** Create `learning/adjust.py` + `data/learning/ADJUST_LOG.jsonl`.
**Test:** ajuste de ejemplo queda en ADJUST_LOG con motivo. Commit.

### Task 13e: Vincular AUDIT_REQUEST a la bitácora
**Objective:** El AUDIT_REQUEST (Fase 4) debe incluir un enlace a `LEARNING_JOURNAL.md` y `ADJUST_LOG.jsonl` de esa herramienta, para que el auditor externo certifique no solo el código, sino el PROCESO de aprendizaje.
**Files:** Modify `audit/TEMPLATE.md` (Fase 4) para exigir sección "Bitácora y ajustes".
**Test:** template incluye la sección. Commit.

---

## FASE 3 — PLANTILLA DE GRÁFICO VELA-A-VELA (preparación, NO ensamble aún)
> Solo deja listos los ladrillos; el ensamble BOS→CHOCH→FVG→OB en cascada es Fase 4 (fuera de este plan).

### Task 14: Contrato de plantilla (esqueleto)
**Objective:** Documentar el "estilo plantilla": alto/bajo → BOS/CHOCH (según tesis), bias por TF, aparición de FVG/OB, TODO vela a vela. Sin implementar el motor de ensamble.
**Files:** Create `docs/plantilla_grafico.md` (contrato, no código).
**Test:** markdown existe y describe el flujo vela-a-vela. Commit.

---

## FASE 4 — CIERRE POR OBJETIVO + CERTIFICACIÓN EXTERNA (OBLIGATORIA)
> Regla del Director: cada objetivo terminado se sube a GitHub para que el auditor externo lo verifique y certifique.

### Task 15: Script de cierre + push por objetivo
**Objective:** Automatizar commit + push a `origin/main` de todo lo producido en el objetivo, con mensaje que invita a certificar.
**Files:** Create `scripts/close_objective.bat` — recibe `OBJETIVO` y `EVIDENCIA`; hace `git add` de los archivos del objetivo, `git commit -m "feat(<obj>): ... [CERTIFICAR] <qué>"`, `git push origin main`.
- Rama: `main` (upstream `origin/main` ya existe, push directo autorizado por contrato §16).
**Test:** dry-run con un objetivo ficticio, confirma que el commit message lleva `[CERTIFICAR]`.

### Task 16: AUDIT_REQUEST por objetivo
**Objective:** Por cada objetivo cerrado, generar `audit/AUDIT_REQUEST_<obj>_<fecha>.md` que diga QUÉ se hizo, QUÉ evidencia existe (rutas reales), y QUÉ se espera que el auditor externo certifique (ej. "la herramienta BOS emite eventos vela-a-vela sobre M5 1 mes sin error; calificación humana 72% > 50%").
**Files:** Create `audit/AUDIT_REQUEST_<obj>_<fecha>.md` (plantilla en `audit/TEMPLATE.md`).
**Test:** genera el request para el objetivo BOS; el auditor externo podría clonar `github.com/vjack666/ict2.0` y verificar.

### Task 17: Evidencia mínima subida (no artifacts pesados)
**Objective:** Subir al repo el código + AUDIT_REQUEST + evidencia legible (brief .md, report .md, jsonl de learning). EXCLUIR graphify-out/*.html (730KB) y graphify-tmp/ (ruido) vía .gitignore.
**Files:** Modify `.gitignore` (agregar `graphify-out/`, `graphify-tmp/`, `__pycache__/`).
**Test:** `git status` tras ignore confirma que no se suben los pesados.

### Task 18: Verificación de push real (prueba de la regla)
**Objective:** ANTES de cerrar el primer objetivo real, probar el flujo completo con el plan ya escrito (`.hermes/plans/...md`) para confirmar que el auditor externo SÍ puede clonar y ver.
**Files:** `git ls-remote origin` + `git log origin/main -1` post-push.
**Test:** tras push, `git ls-remote` muestra el commit en origin/main (evidencia de push real, no afirmación).

---

## ARCHIVOS QUE SE CREAN
- `tools/base.py`, `tools/event.py`, `tools/swing.py`, `tools/bos.py`, `tools/choch.py`, `tools/fvg.py`, `tools/ob.py`, `tools/displacement.py`, `tools/bias.py`, `tools/liquidity.py`
- `learning/export_review.py`, `learning/aggregate.py`, `learning/hermes_report.py`
- `data/learning/` (logs jsonl + reviews)
- `docs/plantilla_grafico.md`
- `docs/learning/report_<fecha>.md` (salida)

## VALIDACIÓN
- Cada `tools/<tool>.py` corre sobre `data/raw/EURUSD/EURUSD_M5.parquet` (1 mes) y emite eventos sin error.
- `learning/hermes_report.py` entrega SOLO líneas > umbral esperado.
- Sin backtest en ningún paso.

## RIESGOS / ABIERTO
- ¿El agente trader humano califica en archivo .md o vía otro canal? (definir al cerrar Task 11).
- Baseline "esperado" inicial: 50% propuesto; el Director puede fijarlo.
- M5 1 mes ≈ suficiente para BOS/CHOCH/FVG; OB y liquidity pueden necesitar más muestras (ajustar mes si el Director lo pide).

## ORDEN DE EJECUCIÓN PROPUESTO
Task 1 → 2 (swing, base de plantilla) → 3-9 (herramientas individuales una a una) → 10-13 (aprendizaje + informe Hermes) → 14 (contrato de plantilla).
