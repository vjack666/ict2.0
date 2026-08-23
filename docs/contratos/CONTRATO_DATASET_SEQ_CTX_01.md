# Contrato — Dataset offline EXP-SEQ-CTX-01 (Sequence × Context State)

**Estado:** NORMATIVO (v1, congelado)
**Fecha:** 2026-08-23
**Autor:** Hermes (Dirección de Laboratorio)
**Alcance:** cada observación del dataset offline de EXP-SEQ-CTX-01. No autoriza
entry, PnL, backtest ni entrenamiento IA. `can_trade=false` siempre.

---

## 1. Esquema de cada fila (columnas obligatorias)

| Campo | Tipo | Semántica / regla |
|---|---|---|
| `event_id` | str | hash determinista de `(dataset_id, symbol, tf, event_time, structure_mode, chain_id, depth)` |
| `dataset_id` | str | id del dataset (p.ej. `SEQ_CTX_01_CANONICAL` / `SEQ_CTX_01_LITE`) |
| `dataset_sha256` | str | SHA-256 del archivo de ejemplos (integridad) |
| `generator_commit` | str | commit de `engine/` usado al generar |
| `contract_version` | str | versión de este contrato (`v1`) |
| `symbol` | str | `EURUSD` |
| `timeframe` | str | `H1` |
| `event_time` | datetime | barra `t` del nodo k (ancla point-in-time) |
| `direction` | int | `+1` / `-1` (bullish/bearish) |
| `structure_mode` | str | `canonical_bos` \| `lite` (NUNCA mezclar en un mismo dataset) |
| `sequence_depth` | int | `k` (profundidad del nodo; dimensión extra, no identidad) |
| `context_bucket` | str | `ALIGNED` \| `NEUTRAL` \| `AGAINST` |
| `features_at_t` | json | SOLO información con `time <= T` (contexto MTF causal + secuencia) |
| `label_end_6` | str | `continuation`\|`reversal`\|`failure` a +6 barras H1 (> t) |
| `label_end_12` | str | ídem a +12 |
| `label_end_24` | str | ídem a +24 |
| `label_end_48` | str | ídem a +48 |
| `split` | str | `DESIGN`\|`VALIDATION`\|`HOLDOUT` (temporal, no aleatorio) |
| `can_trade` | bool | **siempre `false`** |

## 2. Reglas de frontera causal (obligatorias)

- `features_at_t` usa EXCLUSIVAMENTE información con `time <= T`.
- Frontera causal: `time <= T` para todo lo que alimenta el contexto.
- Contexto MTF calculado con **prefijo causal** (navigator `precompute_sequences=False`, gate causal FULL-vs-PREFIX en PASS).
- Las etiquetas futuras (`label_*`) SOLO pueden aparecer en `label_*`; nunca en `features_at_t`.
- **No** incluir entry, stop, PnL ni decisiones operativas en ninguna columna.
- **No** incluir columnas calculadas con información posterior a `T`.
- Mantener `canonical_bos` y `lite` en datasets SEPARADOS (dos `dataset_id` distintos).

## 3. Lineage y procedencia

- Cada fila conserva `event_id` + `generator_commit` + `dataset_sha256` para reproducibilidad.
- El manifest del dataset (`manifest.json`) registra:
  `dataset_id, symbol, tf, period, generator_commit, contract_version,
   schema, rows_by_split, sha256_per_split, structure_mode,
   gate_causal_status, gate_tna_status, canonical_gate_status`.

## 4. Validación obligatoria (script `validate_seq_ctx_dataset.py`)

El validador debe fallar cerrado si:
- falta el gate causal (`reports/audits/experiments/seq_ctx_01/gate_causal.json` != PASS);
- falta el gate TNA (`behavioral/full-span` != PASS);
- falta `dataset_sha256`;
- falta `generator_commit`;
- existe leakage (`features_at_t` con `time > T`, o `label_*` usado en features);
- no existe split temporal;
- `can_trade != false`;
- hay duplicados en `event_id` o nulos en columnas obligatorias.

## 5. Purga/embargo en límites temporales

- `label_end_48` requiere 48 barras posteriores a `T` DENTRO del mismo bloque.
- Si `+48` cruza el límite de un bloque (DESIGN/VAL/HOLDOUT), la observación
  se **excluye** de ese bloque (reporte de exclusiones) y no se reclasifica.
- No se rellena el holdout moviendo observaciones entre bloques.

## 6. Política

```text
DATASET OFFLINE (can_trade=false)  =  evidencia de investigación
DATASET OFFLINE (can_trade=false)  ≠  señal / modelo operativo / autorización
```

Un PASS descriptivo (sample suficiente) NO autoriza edge, órdenes, backtest,
entrenamiento IA ni promoción de reglas.
