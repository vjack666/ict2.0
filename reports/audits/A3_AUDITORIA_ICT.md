# AUDITORÍA ICT — TRAMO A3

**Fecha:** 2026-08-21
**Modo:** DOCUMENTAL — lectura + documentación (cero código nuevo)
**Rama:** feature/a3-audit-ict
**Regla de Oro:** toda afirmación cita `archivo:línea` real. Separar IDENTITY ≠ LINK ≠ CAUSALITY.

---

## 0. Hallazgos de contexto (discrepancias del plan vs código)

| # | Discrepancia | Evidencia | Severidad |
|---|---|---|---|
| C-1 | El plan (líneas 88-99) lista `Liquidity`, `Sweep`, `FVG`, `Order Block`, `POI`, `Retest/Touch`, `Power of Three`, `MTF navigation`, `HTF bias`, `LTF confirmation`, `invalidation`, `lineage`, `sincronización temporal` como módulos a auditar. | `ls tools/*.py` → solo existen: `swing, bos, bos_filter, bos_validate, choch, choch_quality, displacement, block_builder, quality_score, teacher_rubric, confirmation_thresholds, base, event, swing_state`. | ALTA: el plan sobre-lista módulos; varios NO son `Tool` independientes en `tools/`. |
| C-2 | `Power of Three` no existe como módulo. | No aparece en `tools/` ni `engine/` (grep). | BAJA |
| C-3 | `MTF navigation` / `HTF bias` / `LTF confirmation` / `sincronización temporal` viven en `engine/` (no en `tools/`). | `engine/` contiene la navegación MTF; `tools/` es solo detección de eventos base. | MEDIA (perímetro de auditoría distinto al listado) |

**Conclusión C:** los módulos ICT *implementados como detectores aislados* en `tools/` son: **Swing, BOS, CHOCH, Displacement**. El resto (Liquidity/Sweep/FVG/OB/POI/Retest/MTF/HTF/LTF) o están integrados dentro de bos/sweep/choch, o son responsabilidad de `engine/`, o NO están implementados. Se auditan los existentes y se marca la brecha.

---

## 1. Módulos ICT auditados (tools/)

### 1.1 Swing — `tools/swing.py`
- **Definición:** pivotes clásicos por ventana central; solo la vela pivot lleva valor, confirmado SIN look-ahead (`origin_bar + lookback`) (`swing.py:14-15,31`).
- **Causalidad (ID≠LINK≠CAUS):** SWING es IDENTITY geométrica (pivot real). No es LINK a nada ni CAUSA CHOCH por sí solo; es input de BOS/CHOCH.
- **Look-ahead:** NINGUNO. `confirmation_bar = origin_bar + lookback`; todo evento usa solo filas ≤ k (`event.py:5,12`).
- **Tests:** no stub; cubierto por `gen_choch_dataset` (lo consume).
- **Consumidores:** `bos.py` (swing_ids), `choch.py`, `block_builder.py`.
- **Limitaciones:** lookback fijo; en TFs grandes (D1) pocos pivotes.

### 1.2 BOS — `tools/bos.py` (+ `detectors.bos.detect_bos`)
- **Definición:** evento hijo del swing roto; usa `swing_high.shift(1)` como nivel roto, empareja con swing padre por barra (`bos.py:11-12,51-57`).
- **Causalidad:** BOS es evento de RUPTURA (LINK entre swing roto y break). Linaje padre-hijo explícito (`bos.py:6-7,15`).
- **Look-ahead:** NINGUNO. `swing_high.shift(1)` es el nivel YA confirmado del padre; `break_bar` es la vela de ruptura (no futura).
- **Tests:** `bos_validate.py` valida vida del BOS (`bos_validate.py:17,43` — "solo recorre velas desde break_bar en adelante").
- **Consumidores:** `choch.py` (último BOS vigente), `bos_filter.py`, `gen_choch_dataset.py`.
- **Limitaciones:** depende de swings previos; anti-flood `is_unique` (commit a91d055) reduce conteo (ver B0 regresión).

### 1.3 CHOCH — `tools/choch.py`
- **Definición:** primera ruptura del swing CONTRARIO al último BOS (`choch.py:3-15`). Tesis `02_MSS_CHOCH`. NO usa medias móviles (bug de `detectors.choch: rolling(50)` en TFs grandes, `choch.py:5-6,20-21`).
- **Causalidad:** CHOCH = aviso de giro (LINK estructural BOS→CHOCH). parent_id = swing roto (linaje).
- **Look-ahead:** NINGUNO. Deriva de swings/BOS ya confirmados (`choch.py:11-15`).
- **Tests:** `choch_quality.py` marca `choch_real` (after_bos AND lvl_present, `choch_quality.py:279,321`); `gen_choch_dataset` lo usa.
- **Consumidores:** `gen_choch_dataset.py`, `block_builder.py`, `train_nature_head.py`.
- **Limitaciones:** en H4/D1 pocos eventos (B0/B2 hallazgo: H4=38, D1=4).

### 1.4 Displacement — `tools/displacement.py`
- **Definición:** `detect_displacement(df, period)`; mide rango de vela vs media móvil (`displacement.py:30,33,36`: `candle_range.rolling(period).mean()`).
- **Causalidad:** Displacement es momentum del break (LINK entre BOS y continuación). No es IDENTITY ni CAUSA por sí solo.
- **Look-ahead:** rolling usa solo histórico (`rolling(period).mean()` es causal).
- **Tests:** consumido por `gen_choch_dataset`, `b1_sequential.py`.
- **Consumidores:** `b1_sequential.py`, features de CHOCH dataset.
- **Limitaciones:** `period` fijo; sensible a volatilidad.

### 1.5 Block builder — `tools/block_builder.py`
- **Definición:** extrae ventana de velas crudas alrededor del break_bar (`block_builder.py:1-29`). Ventana causal `[-W_pre, break_bar]` (input) + `[break_bar+1, +W_post]` (solo label).
- **Causalidad:** el bloque es CONTEXTO (no causa el evento). Normalización anti-estacionariedad (`block_builder.py:14-17,42-75`).
- **Look-ahead:** NINGUNO en input; `W_post` solo para label (nunca al encoder en inferencia, `block_builder.py:9-12`).
- **Optimización:** `599d8c3` eliminó cuello O(eventos×chunks) y `_normalize` vectorizado (numpy cumsum).
- **Consumidores:** `train_nature_head.py`, `b5_ablation.py`.
- **Limitaciones:** reconstruye 61×7 por evento (costo, ya optimizado).

### 1.6 BosValidate / BosFilter / ChoChQuality — `tools/bos_validate.py`, `bos_filter.py`, `choch_quality.py`
- **bos_validate:** valida vida del BOS sin look-ahead (`bos_validate.py:17,43`).
- **bos_filter:** sesgo de TF mayor en el momento de la vela cerrada, sin look-ahead (`bos_filter.py:47`). `filter_bos_thesis` (HTF alignment/confirm) — OJO: este filtro mata CHOCH en `gen_choch_dataset` (regresión B0 resuelta por Opción A).
- **choch_quality:** `choch_real = after_bos AND lvl_present` (`choch_quality.py:279`); escribe `choch_after_bos` (`choch_quality.py:323`).

---

## 2. Módulos del plan NO implementados como Tool en tools/ (BRECHA)

| Módulo plan | Estado en código | Evidencia |
|---|---|---|
| Liquidity | NO existe `tools/liquidity.py` | `ls tools/*.py` (arriba) |
| Sweep | NO existe `tools/sweep.py` | ídem |
| FVG | NO existe `tools/fvg.py` | ídem |
| Order Block | NO existe `tools/ob.py` | ídem (OB se infiere vía BOS nivel) |
| POI | NO existe `tools/poi.py` | ídem |
| Retest/Touch | NO existe `tools/retest.py` | ídem |
| Power of Three | NO existe | grep negativo |
| MTF navigation / HTF bias / LTF confirmation / sincronización | en `engine/` (no tools/) | perímetro distinto |
| invalidation / lineage | lineage sí (parent_id en eventos); invalidation en `bos_validate` | `event.py:39` |

**HALLAZGO A3-1:** el plan lista 19 componentes ICT; solo 4 (Swing/BOS/CHOCH/Displacement) son detectores aislados en `tools/`. La cadena secuencial del plan (B1: LIQUIDITY→SWEEP→DISPLACEMENT→STRUCTURE→OB→FVG→RETEST) es **parcialmente inexistente en código** — B1 tuvo que reducirla a SWING→DISPLACEMENT→BOS→CHOCH (ver EXP-007).

---

## 3. GATE A3

**Resultado: PASS (con salvedad documentada).**
- Ningún componente CRÍTICO (Swing/BOS/CHOCH/Displacement) tiene semántica desconocida: todos documentados con definición, causalidad (ID≠LINK≠CAUS), look-ahead NULO verificado, consumidores y limitaciones.
- La salvedad: el plan sobre-lista módulos no implementados (HALLAZGO A3-1). Esto es documentación de brecha, no bloqueo de semántica desconocida.

**Acción recomendada:** actualizar el plan para reflejar que Liquidity/Sweep/FVG/OB/POI/Retest NO son detectores separados, o implementarlos antes de B1/B2 que los asumen.
