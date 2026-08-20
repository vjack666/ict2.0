# Contrato — Context State (v1)

**Estado:** NORMATIVO v1  
**Fecha:** 2026-08-19  
**SDD padre:** `docs/SDD_CONTEXT_STATE_MTF_NAVIGATION.md`  
**Implementación de referencia:** `engine/mtf_navigation.py` (`LayerSnapshot`, `ContextConstraints`, `MTFNavigator`)  
**Capas:** `CONTRATO_MULTI_TF_LAYERS.md`

---

## 1. Definición

**Context State** es el mapa de **restricciones** que el HTF/ITF emiten en un
`decision_time` \(t\) sobre el universo de setups del `exec_tf`.

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

Emitidos por `ContextConstraints` / snapshots de capa, todos **as-of(\(t\))**
(solo velas cerradas `time ≤ t`):

| Campo | Tipo | Semántica |
|-------|------|-----------|
| `decision_time` | timestamp | \(t\) de evaluación en exec_tf |
| `exec_tf` | str | TF de timing (p. ej. H1) |
| `direction_hint` | `BULLISH \| BEARISH \| MIXED \| UNKNOWN` | Bias estructural (D1 preferido; H4 si D1 unknown). **Fuente:** BOS/estructura, **no** EMA |
| `regime_stack` | `{tf: RegimeLabel}` | TREND_BULL/BEAR, RANGE, EXPANSION, RETRACEMENT, COMPRESSION, UNKNOWN |
| `location` | `DISCOUNT \| PREMIUM \| MID \| UNKNOWN` | Posición del close exec en dealing range HTF (geometría pure) |
| `location_favorable` | bool \| null | True si location apoya direction_hint (bull→discount; bear→premium) |
| `allow_long` / `allow_short` | bool \| null | Restricción de lado; null = sin restricción firme |
| `sequence_required` | bool | v1: siempre True (secuencia LTF obligatoria antes de SETUP) |
| `notes` | list[str] | Trazas humanas de por qué se fijó el hint |

### 2.1 Régimen (v1 heurística documentada)

Derivado de structure bias + posición en rango (ver `_regime_from_structure` en
`engine/mtf_navigation.py`). No es un clasificador ML.

### 2.2 Location

Dealing range HTF: rolling high/low geométrico (`engine/dealing_range.py` o
equivalente en navigator). **OTE residual:** el motor de dealing range puede
etiquetar bandas 0.62–0.79; **OTE como tesis de entrada sigue PROHIBIDO**
(índice Hermes). Location solo usa DISCOUNT/PREMIUM/MID para restricciones.

---

## 3. Buckets operativos para experimentos

Para estratificar **la misma secuencia** bajo distinto contexto:

| Bucket | Regla v1 |
|--------|----------|
| `CTX_ALIGNED` | `direction_hint` alineado con dirección de la secuencia **y** location no adversa (favorable o MID/UNKNOWN) |
| `CTX_AGAINST` | `direction_hint` opuesto a la dirección de la secuencia |
| `CTX_NEUTRAL` | `direction_hint` ∈ {UNKNOWN, MIXED} |

Una secuencia bullish (+1) con hint BEARISH → `CTX_AGAINST`.  
Una secuencia bullish con hint BULLISH y location PREMIUM → sigue `CTX_ALIGNED`
pero con nota de location débil (no se degrada a AGAINST en v1 para no mezclar
ejes; se reporta `location_favorable` aparte).

---

## 4. Anti-look-ahead

1. Toda evidencia HTF/ITF en \(t\) usa solo barras con `close_time ≤ t`.
2. Pivotes/BOS de contexto: causales (sin `center=True` sobre futuro).
3. Context State se congela en el bar de anclaje de la secuencia (p. ej. STRUCTURE
   o RETEST); no se reescribe con velas posteriores al ancla.

---

## 5. Policy

```text
Context State     =  restricciones / location / regime
Context State     ≠  entry
SETUP_READY       ≠  order
EMA20/50          ≠  direction_hint normativo
```

---

## 6. Gate de aceptación de este contrato

PASS cuando:

1. Este archivo está en `main` y referenciado desde el índice.
2. `engine/mtf_navigation.py` implementa los campos de §2 sin EMA normativa.
3. Experimentos que citen “Context State” usan los buckets de §3.
4. Ningún backtest de entry se autoriza solo por este contrato.
