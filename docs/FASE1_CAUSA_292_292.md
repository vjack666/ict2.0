# FASE 1 — Causa 292/292 congelada

**Fecha:** 2026-09-18  
**Estado:** CONGELADA — documentada; la corrección se realiza en la representación temporal, no reescribiendo el modelo viejo.

## Causa raíz

La representación de `setup_quality_v1` destruye el orden de la secuencia antes de que la red la consuma:

```text
features_at_t.sequence (lista ordenada)
        ↓
sequence_set / set-comprehension
        ↓
set[str] sin orden
        ↓
features por presencia
        ↓
original == reversed
```

### Punto 1 — materializador

`scripts/lab/experiments/materialize_setup_grammar_dataset_v1_fixed.py`

La función `sequence_set(row)` convierte `features_at_t.sequence` a `set[str]`.
Luego `materialize_row()` usa ese conjunto para derivar presencia de PO3,
liquidity sweep, displacement, structure confirmation, PD array y retest.

Resultado: la inversión temporal conserva exactamente el mismo conjunto.

### Punto 2 — encoder de setup quality

`scripts/lab/experiments/train_setup_quality_v1.py`

El extractor repite el patrón:

```python
sequence = {str(item).upper() for item in raw_features.get("sequence") or []}
```

Por tanto el tensor tabular tampoco puede distinguir permutaciones.

### Punto 3 — semantic_pd_array_eval_v1

`scripts/lab/experiments/semantic_pd_array_eval_v1.py` no introduce por sí mismo
la conversión a set. Consume features ya reducidos/materializados. No se le
atribuye la causa raíz del 292/292.

## Decisión

No modificar `setup_quality_v1` para simular memoria temporal.

La nueva ruta autorizada es:

```text
MarketState / Episodes
        ↓
Temporal Episode v1
        ↓
representación secuencial
        ↓
baseline temporal
        ↓
GRU solo si añade valor OOS
```

Hasta entonces:

```text
training_eligible=false
can_trade=false
entry_authorized=false
```
