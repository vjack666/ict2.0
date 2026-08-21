# EXP SEQUENCE × CONTEXT STATE — v3

**Fecha:** 2026-08-21  
**Estado:** EJECUTADO (local) · **Policy:** AUDIT_ONLY  
**Driver:** `scripts/exp_seq_x_context_state.py`  
**Artefacto:** `reports/audits/exp_seq_x_context_state.json`  
**Iteración:** v3 — exclusión depth=1 + test dirigido de reversión (bootstrap por clusters)

---

## 1. Resumen ejecutivo

**Pregunta (H1):** ¿la misma secuencia tiene una distribución de outcomes distinta según Context State?

**Veredicto:** H1 con señales a favor en al menos un contraste (min p=0.0043, max V=0.157, ICs dirigidos excluyendo 0: 3/6). Requiere replicación antes de cualquier uso.

- Diseño event-anchored sobre `2019-2024 H1`, horizonte 20 barras H1, 6314 observaciones (2837 MAIN depth≥2 + 3477 baseline depth=1), 3478 cadenas.
- Hallazgo v3: la estructura domina la magnitud (POOL→SWEEP invierte la lectura frente a POOL-only) y, con depth=1 fuera de la inferencia, aparece una modulación de contexto REAL en la tasa de reversión de POOL→SWEEP: las secuencias en contexto FAVORABLE revierten más que en NEUTRAL/CONTRA.
- El grupo depth=1 (~90% continuation transversal) se identifica como artefacto geométrico y se excluye de la inferencia.

## 2. Metodología

### 2.1 Diseño event-anchored

- Unidad = **evento/transición**: nodo k de una `SequentialChain` (`engine/sequential_events.run_sequential`, `structure_mode=canonical_bos`). No barras genéricas.
- `sequence_signature` = dirección + etapas presentes hasta k (ej. `1|LIQUIDITY_POOL->SWEEP`); `depth` = k.
- Dedup por `(chain_id, k)`.

### 2.2 Context State point-in-time

- `MTFNavigator.navigate(t=bar_k, exec_tf=H1)` (causal, validado por TNA; sin EMA).
- Bucket = D1 bias × H4 location × H1 alignment (score ±2 → FAVORABLE / CONTRA; resto NEUTRAL).

### 2.3 Estrategia causal: PIT-dentro-del-rango

- Deuda conocida: `run_sequential` **no** era PIT-estable FULL vs PREFIX truncado (raíz: `_build_eq_pools` agrupaba retrospectivamente).
- Estado del motor en v3: incluye el fix PIT de `_build_eq_pools` (commit `4f09795`, rama `engine-seq-v2-causal`). Por eso `cadenas_rango=3478` vs 775 en v2 con el mismo rango y config: la semántica PIT genera pools más granulares.
- Compensación (se mantiene como cinturón de seguridad): `run_sequential` corre UNA vez sobre el rango acotado; sus cadenas son PIT-estables respecto a ese df. Context desde navigator FULL (biases estables). Outcome = futuro puro. El gate formal SEQUENCE_PIT_INTEGRITY FULL vs PREFIX queda pendiente de re-validación sobre `main`.
- No se modifica engine/ ni funnel configs.

### 2.4 Definición de outcome (measure_outcome)

- Ventana: barras H1 `bar_k+1 .. bar_k+20` (solo futuro).
- Niveles de ruptura = **rango de la secuencia**: `seq_high/seq_low` = max/min de los nodos hasta k.
- `continuation` = rompe el extremo en dirección de la secuencia; `reversal` = rompe el extremo opuesto primero; `failure` = ninguno.

## 3. Matriz primaria (S × Contexto)

Celdas con n≥30. `MAIN` = depth≥2 (base inferencial). `DEPTH1_BASELINE_ARTIFACT` = referencia ruidosa, excluida de los tests.

| Grupo | Secuencia | Contexto | n | Cont% | Rev% | Fail% |
|---|---|---|---:|---:|---:|---:|
| MAIN | `-1|LIQUIDITY_POOL->SWEEP` | NEUTRAL | 869 | 52% | 46% | 2% |
| MAIN | `1|LIQUIDITY_POOL->SWEEP` | NEUTRAL | 857 | 52% | 46% | 1% |
| MAIN | `-1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT` | NEUTRAL | 195 | 84% | 15% | 2% |
| MAIN | `1|LIQUIDITY_POOL->SWEEP` | CONTRA | 182 | 59% | 41% | 0% |
| MAIN | `1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT` | NEUTRAL | 173 | 86% | 14% | 1% |
| MAIN | `-1|LIQUIDITY_POOL->SWEEP` | CONTRA | 161 | 56% | 43% | 1% |
| MAIN | `-1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT->STRUCTURE` | NEUTRAL | 71 | 92% | 4% | 4% |
| MAIN | `1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT->STRUCTURE` | NEUTRAL | 59 | 83% | 10% | 7% |
| MAIN | `1|LIQUIDITY_POOL->SWEEP` | FAVORABLE | 50 | 38% | 60% | 2% |
| MAIN | `1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT` | CONTRA | 47 | 89% | 6% | 4% |
| MAIN | `-1|LIQUIDITY_POOL->SWEEP` | FAVORABLE | 45 | 27% | 73% | 0% |
| MAIN | `-1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT` | CONTRA | 31 | 90% | 10% | 0% |
| DEPTH1_BASELINE_ARTIFACT | `-1|LIQUIDITY_POOL` | NEUTRAL | 1389 | 90% | 9% | 1% |
| DEPTH1_BASELINE_ARTIFACT | `1|LIQUIDITY_POOL` | NEUTRAL | 1377 | 90% | 10% | 1% |
| DEPTH1_BASELINE_ARTIFACT | `1|LIQUIDITY_POOL` | FAVORABLE | 190 | 95% | 4% | 1% |
| DEPTH1_BASELINE_ARTIFACT | `1|LIQUIDITY_POOL` | CONTRA | 186 | 87% | 13% | 0% |
| DEPTH1_BASELINE_ARTIFACT | `-1|LIQUIDITY_POOL` | FAVORABLE | 169 | 94% | 6% | 0% |
| DEPTH1_BASELINE_ARTIFACT | `-1|LIQUIDITY_POOL` | CONTRA | 166 | 89% | 9% | 2% |

## 4. Tests estadísticos

### 4.1 χ² contexto × outcome por firma (solo depth≥2)

| Secuencia | χ² | p | Cramér's V | n contextos |
|---|---:|---:|---:|---:|
| `1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT` | 5.42 | 0.0666 | 0.157 | 2 |
| `-1|LIQUIDITY_POOL->SWEEP` | 15.21 | 0.0043 | 0.084 | 3 |
| `-1|LIQUIDITY_POOL->SWEEP->DISPLACEMENT` | 1.13 | 0.5683 | 0.071 | 2 |
| `1|LIQUIDITY_POOL->SWEEP` | 7.58 | 0.1082 | 0.059 | 3 |

### 4.2 Test dirigido: reversión en LIQUIDITY_POOL→SWEEP por contexto

Tasa de REVERSAL por bucket y diferencias pareadas con IC95% bootstrap (unidades de remuestreo = cadenas completas vía `chain_id`; 2000 remuestreos, semilla 20260820).

**`1|LIQUIDITY_POOL->SWEEP`**

| Contexto | n | Reversals | Tasa reversal |
|---|---:|---:|---:|
| FAVORABLE | 50 | 30 | 60% |
| NEUTRAL | 857 | 397 | 46% |
| CONTRA | 182 | 74 | 41% |

| Comparación | Δ tasa reversal | IC95% | p boot (bilateral) | Excluye 0? |
|---|---:|---|---:|---|
| FAVORABLE_minus_NEUTRAL | +0.137 | [-0.003, +0.284] | 0.054 | no |
| FAVORABLE_minus_CONTRA | +0.193 | [+0.038, +0.344] | 0.01 | sí |
| NEUTRAL_minus_CONTRA | +0.057 | [-0.025, +0.138] | 0.182 | no |

**`-1|LIQUIDITY_POOL->SWEEP`**

| Contexto | n | Reversals | Tasa reversal |
|---|---:|---:|---:|
| FAVORABLE | 45 | 33 | 73% |
| NEUTRAL | 869 | 401 | 46% |
| CONTRA | 161 | 69 | 43% |

| Comparación | Δ tasa reversal | IC95% | p boot (bilateral) | Excluye 0? |
|---|---:|---|---:|---|
| FAVORABLE_minus_NEUTRAL | +0.272 | [+0.132, +0.394] | 0.001 | sí |
| FAVORABLE_minus_CONTRA | +0.305 | [+0.141, +0.446] | 0.0 | sí |
| NEUTRAL_minus_CONTRA | +0.033 | [-0.052, +0.117] | 0.426 | no |

### 4.3 Componente de Context State que más explica (solo depth≥2)

| Componente | Avg Cramér's V | n secuencias |
|---|---:|---:|
| d1_bias | 0.041 | 5 |
| h4_loc | 0.049 | 5 |
| h1_align | 0.164 | 4 |

## 5. Análisis del artefacto depth=1 (exclusión)

- Con depth=1 la firma es `±1|LIQUIDITY_POOL` y el "rango de la secuencia" es el high/low de **una sola barra situada en un extremo local** (el pool se forma justamente ahí).
- Romper ese extremo en 20 barras H1 es casi seguro en mercado ruidoso → ~92% continuation **independientemente del contexto** (v2: NEUTRAL 91.8%, FAVORABLE 100%, CONTRA 92–94%).
- Esa masa (~49% de las observaciones v2) domina las tablas de contingencia y comprime los χ² hacia el nulo por homogeneidad artificial: contamina el contraste H1.
- Decisión v3: excluir depth=1 de TODOS los tests inferenciales; conservarlas en la matriz bajo `DEPTH1_BASELINE_ARTIFACT` como referencia visible del sesgo.

## 6. Limitaciones

- **Deuda motor PIT (parcialmente retirada):** el fix PIT de `_build_eq_pools` (`4f09795`) está en el motor y explica el salto 775→3478 cadenas; el diseño PIT-dentro-del-rango se conserva hasta re-validar el gate SEQUENCE_PIT_INTEGRITY FULL vs PREFIX sobre `main`.
- **Desbalance de buckets:** FAVORABLE/CONTRA tienen mucho menos n que NEUTRAL. Todos los contrastes dirigidos alcanzaron n≥30.
- Un solo símbolo (EURUSD), un TF de ejecución (H1), horizonte fijo 20 barras; sin costes de transacción (no aplica: AUDIT_ONLY).
- Cada cadena aporta ≤1 observación por firma, por lo que el cluster-bootstrap por `chain_id` degenera a bootstrap simple dentro de cada firma (se implementa igual por corrección metodológica).
- Múltiples comparaciones sin corrección: todos los tests son exploratorios.

## 7. Conclusiones y próximos pasos

1. H1 con señales a favor en al menos un contraste (min p=0.0043, max V=0.157, ICs dirigidos excluyendo 0: 3/6). Requiere replicación antes de cualquier uso.
2. La estructura sigue dominando la MAGNITUD (POOL→SWEEP invierte la lectura frente a POOL-only), pero el test dirigido muestra que el contexto SÍ modula la tasa de reversión dentro de POOL→SWEEP: en contexto FAVORABLE la secuencia revierte más (bearish 73.3% vs 46.1% neutral; bullish 60.0% vs 46.3%), un gradiente consistente en ambas direcciones con ICs que excluyen 0 frente a CONTRA.
3. Próximo paso de mayor valor: **re-validar el gate SEQUENCE_PIT_INTEGRITY (FULL vs PREFIX = 0 violaciones) sobre `main`** con el fix ya mergeado; habilita escalar el EXP a más rango/símbolos sin la compensación de rango acotado.
4. Antes de cualquier uso operativo: replicar el gradiente FAVORABLE>NEUTRAL≈CONTRA en otro período/símbolo y con corrección por comparaciones múltiples; mientras tanto, AUDIT_ONLY.

## Policy

```text
SEQUENCE × CONTEXT  =  objeto de estudio de distribución
SEQUENCE × CONTEXT  ≠  señal de trading aprobada
```
