# PRE-REGISTRO — Ampliación OOS EXP-SEQ-CTX-01

**ID:** OOS-EXPANSION-PREREG-01
**Fecha de preregistro:** 2026-08-24 (ANTES de generar cualquier observación nueva)
**Autor:** Hermes (Agente 2 — Científico/Estadística), bajo `AGENTS.md`
**Experimento base:** EXP-SEQ-CTX-01 (Sequence × Context State)
**Estado del experimento al preregistrar:** `WAITING_FOR_OOS_EVIDENCE`; OOS actual = `SUBPOWERED`
**Criterio vigente congelado:** `n >= 30` por celda `(structure_mode, context_bucket, HOLDOUT)`

**Erratum editorial:** el universo contiene 7 pares FX y `XAUUSD`; en este
documento, “8 símbolos” significa 8 instrumentos. Esta aclaración no cambia
el universo, los conteos ni el veredicto ya emitido.

---

## 0. Motivación (sin ver resultados de la ampliación)

El HOLDOUT 2021–2025 de EURUSD arrojó (manifest vigente 2026-08-24):

| Variante | ALIGNED | NEUTRAL | AGAINST |
|---|---:|---:|---:|
| canonical_bos | 6 ❌ | 11 ❌ | 3 ❌ |
| lite | 10 ❌ | 36 ✅ | 10 ❌ |

Ninguna celda de `canonical_bos` alcanza `n>=30`. `lite/NEUTRAL` es la única
que pasa. Con muestras de un dígito/low-double-digit, la estimación OOS puede
variar engañosamente. El bloqueo científico es **potencia muestral**, no
ingeniería de IA.

La evidencia de viabilidad multi-símbolo se ejecutó en piloto determinista
(`_pilot_oos_multisymbol.py`) **después** de este preregistro lógico pero **antes**
de cualquier conteo final: el piloto solo confirma que el motor produce
observaciones HOLDOUT en otros símbolos; no altera ningún parámetro aquí
contenido.

---

## 1. Diseño de la ampliación

### 1.1 Estrategia de selección (pre-registrada, por criterios previos)

Prioridad del cliente y de la FASE 2 del mandato:
1. **Más símbolos compatibles** (prioridad 1)
2. Más timeframes compatibles (prioridad 2 — NO usado aquí, ver §1.4)
3. Otras extensiones metodológicas (prioridad 3 — NO usadas)

La elección de símbolos NO se basa en ningún resultado histórico favorable, sino
en: disponibilidad local de datos, cobertura temporal del HOLDOUT, calidad,
compatibilidad con la estructura ICT (mismo detector `run_sequential` +
`MTFNavigator`), granularidad H1, y ausencia de leakage (contexto PIT estricto).

### 1.2 Universo preregistrado (congelado)

- **Instrumentos (8):** EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF, USDJPY, XAUUSD
- **Timeframes (3):** D1, H4, H1 (contexto PIT completo)
- **Estructura (`structure_mode`):** `canonical_bos`, `lite` (jamás mezclados)
- **Períodos / splits:**
  - `DESIGN` 2006–2015, `VALIDATION` 2016–2020 → **SOLO EURUSD** (los otros 7
    símbolos no tienen D1/H4 antes de 2020-01-02; construir contexto PIT sin
    D1/H4 sería inválido y se prohíbe).
  - `HOLDOUT` 2021–2025 → **los 8 símbolos** (todos tienen D1/H4/H1 cubriendo
    el período; ver `OOS_DATA_INVENTORY.json`).

### 1.3 Parámetros congelados (idénticos al factory vigente)

- `MIN_DEPTH = 4` (nodo k con k+1 >= 4; sin relajar profundidad post-hoc).
- `HORIZONS = [6, 12, 24, 48]` (labels `continuation/reversal/failure`).
- `MAX_ACTIVE_CHAINS = 10_000_000`.
- Purga +48: si `T+48` cae fuera del bloque → observación **excluida** (no reclasificada).
- Deduplicación intra-variante: `(structure_bar, direction)` dentro de cada variante.
- `context_bucket` reconstruido desde `sequence_direction, d1_bias, h4_location,
  h1_alignment` con la puntuación normativa del contrato (D1/H4 relativos a
  dirección; H1 +1/0/-1; umbrales >=2 ALIGNED, <=-2 AGAINST).
- Contexto PIT: `MTFNavigator` con prefijo causal `time <= T`
  (`precompute_sequences=False`, `sequence_tf="H1"`).
- `can_trade = false` siempre.
- `dataset_sha256` = SHA-256 del payload canónico (excluye su propio campo).
- `event_id` = SHA-256 de `(dataset_id, symbol, tf, event_time, structure_mode, chain_id, depth)`.

### 1.4 Timeframes adicionales

NO se añaden timeframes nuevos en esta ampliación (prioridad 2 no activada).
El TF de ejecución de la secuencia es **H1** en todos los símbolos, igual que el
baseline. Mantener exactamente el mismo detector es la garantía anti-leakage.

### 1.5 Tratamiento de resultados negativos

Todos los conteos por celda se registran, incluidos los que no alcanzan `n>=30`.
NO se ocultan celdas con n bajo. NO se recalcula el umbral tras ver resultados.

---

## 2. Criterio de suficiencia (pre-registrado)

**Celda obligatoria:** `(structure_mode, context_bucket, HOLDOUT)`.
**Umbral:** `n >= 30` en CADA celda obligatoria.

Celdas obligatorias (6):

```
canonical_bos × {ALIGNED, NEUTRAL, AGAINST} × HOLDOUT
lite          × {ALIGNED, NEUTRAL, AGAINST} × HOLDOUT
```

Solo se evalúa el split **HOLDOUT** (regla del mandato y del SDD/OOS vigente).
Los splits DESIGN/VALIDATION (EURUSD) se reportan para trazabilidad pero NO
participan del veredicto de suficiencia OOS.

---

## 3. Criterio de parada (pre-registrado)

Detener la ampliación cuando ocurra **primero**:

- **(A)** todas las 6 celdas HOLDOUT alcanzan `n >= 30`; **o**
- **(B)** se agota el universo preregistrado (8 símbolos × 2 modos × HOLDOUT
  2021–2025) sin alcanzar (A).

Si (B): el estadístico independiente (Agente 6 / FASE 6) emite
`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`. NO se inventa otra ampliación
sin un nuevo preregistro.

---

## 4. Prohibiciones (iguales al mandato)

1. No cambiar `n>=30` tras ver resultados.
2. No mover HOLDOUT 2021–2025.
3. No ajustar thresholds para inflar muestras.
4. No eliminar resultados negativos.
5. No mezclar `canonical_bos` con `lite`.
6. No declarar edge.
7. No entrenar IA antes del cierre de gates.
8. No activar trading.
9. No modificar datasets fuente.
10. Toda modificación metodológica se preregistra antes de ejecutar.

---

## 5. Artefactos de la ampliación

- `OOS_DATA_INVENTORY.json` — inventario de fuentes locales (Agente 3).
- Este preregistro — `docs/planificacion/OOS_EXPANSION_PREREGISTRATION.md`.
- `exp_seq_ctx_01_dataset.py` (generalizado a multi-símbolo) — fábrica.
- `data/learning/seq_ctx_01/OOS_EXPANSION/manifest.json` — manifest de la ampliación.
- `data/learning/seq_ctx_01/OOS_EXPANSION/*.jsonl` — observaciones por variante.
- `OOS_EXPANSION_COUNTS.json` — conteos por (símbolo, modo, bucket, split, año).
- Reporte de auditoría independiente (Agente 6 / FASE 6).

---

## 6. Declaración anti-p-hacking

Este documento se escribió fijando universo, parámetros, umbral y criterio de
parada **antes** de ejecutar la ampliación. El objetivo es **potencia muestral
OOS**, no "encontrar dónde funciona". Si tras agotar el universo alguna celda
queda < 30, eso es evidencia de insuficiencia, no un fallo a corregir rebajando
el umbral.
