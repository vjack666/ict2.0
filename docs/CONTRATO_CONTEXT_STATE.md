# Contrato — Context State (v1)

**Estado:** NORMATIVO v1  
**Fecha:** 2026-08-19  
**SDD padre:** `docs/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`  
**Implementación de referencia:** `engine/mtf_navigation.py` (`LayerSnapshot`, `ContextConstraints`, `MTFNavigator`)  
**Capas:** `docs/CONTRATO_MULTI_TF_LAYERS.md`

---

## 1. Definición

**Context State** es el mapa de **restricciones** que el HTF/ITF emiten en un
`decision_time` (t) sobre el universo de setups del `exec_tf`.

```text
Context State  ≠  señal de entrada
Context State  ≠  score tabular de flags
Context State  ≠  EMA20/50 bias
```

Es la respuesta auditable a:

| Pregunta | Capa |
|----------|------|
| ¿Hay contexto relevante? | D1 (HTF) |
| ¿Dónde estoy dentro del contexto? | H4 (ITF) |
| ¿Qué régimen / bias estructural rige? | D1 → H4 |
| ¿Qué zonas de liquidez / dealing limitan? | D1/H4 |

---

## 2. Campos obligatorios (v1)

Emitidos por `ContextConstraints` / snapshots de capa, todos **as-of(t)**
(solo velas cerradas `time ≤ t`):

| Campo | Tipo | Semántica |
|-------|------|-----------|
| `decision_time` | timestamp | t de evaluación en exec_tf |
| `exec_tf` | str | TF de timing (p. ej. H1) |
| `direction_hint` | `BULLISH \| BEARISH \| MIXED \| UNKNOWN` | Bias estructural (D1 preferido). **Fuente:** BOS/estructura, **no** EMA |
| `regime_stack` | `{tf: RegimeLabel}` | TREND_BULL/BEAR, RANGE, EXPANSION, RETRACEMENT, COMPRESSION, UNKNOWN |
| `location` | `DISCOUNT \| PREMIUM \| EQ \| UNKNOWN` | Posición del close en dealing range HTF (geometría pura) |
| `location_favorable` | bool \| null | True si location apoya direction_hint |
| `allow_long` / `allow_short` | bool \| null | Restricción de lado |
| `sequence_required` | bool | v1: siempre True |
| `notes` | list[str] | Trazas humanas |

### 2.1 Régimen

Derivado de structure bias + posición en rango. No es un clasificador ML.

### 2.2 Location

Dealing range HTF: rolling high/low geométrico (`engine/dealing_range.py`).
**Solo EQ 50%:** zonas `DISCOUNT | EQ | PREMIUM`.
**OTE / Fibonacci 62–79% PROHIBIDOS** (ICT_RULEBOOK §9, CONTRATO_FUNNEL_AUDIT).
Sin ATR, sin medias, sin OTE como gate ni etiqueta operativa.

---

## 3. Buckets operativos

| Bucket | Regla v1 |
|--------|----------|
| `CTX_ALIGNED` | direction_hint alineado con dirección de la secuencia |
| `CTX_AGAINST` | direction_hint opuesto |
| `CTX_NEUTRAL` | direction_hint ∈ {UNKNOWN, MIXED} |

---

## 4. Anti-look-ahead

1. Solo barras HTF/ITF con `close_time ≤ t`.
2. Pivotes/BOS causales (sin center=True sobre futuro).
3. Context State se congela en el bar de anclaje.

---

## 5. Policy

```text
Context State     =  restricciones / location / regime
Context State     ≠  entry
EMA20/50          ≠  direction_hint normativo
OTE / Fibonacci   ≠  location normativa
```

---

## 6. Gate

PASS cuando este archivo está en main; dealing_range solo emite DISCOUNT/EQ/PREMIUM; sin EMA normativa; experiments usan buckets §3; ningún backtest de entry solo por este contrato.
