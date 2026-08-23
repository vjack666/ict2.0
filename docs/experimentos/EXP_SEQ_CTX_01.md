# EXP-SEQ-CTX-01 — Sequence × Context State

**Estado:** `CAUSAL_PASS / INSUFFICIENT_N`
**Host:** PC local exclusivamente
**Política:** distribución observacional; no entry, no PnL y no promoción

## Objetivo

Evaluar si una misma secuencia `depth >= 4` presenta distribuciones de
outcomes distintas cuando el contexto es `CTX_ALIGNED`, `CTX_AGAINST` o
`CTX_NEUTRAL`. El experimento no declara edge operativo.

## Barrera causal

La matriz solo puede ejecutarse si:

- `reports/audits/experiments/seq_ctx_01/gate_causal.json` tiene `status=PASS`
  y `usable_for_inference=true`.
- `reports/audits/tna_streaming_prefix_2026-08-22.json` conserva
  `full_prefix=PASS_BY_LAYER_INDUCTION` y `gate=PASS`.
- La frontera FULL/PREFIX es inclusiva: `time <= decision_time`.

El gate local actual comparó 120 decisiones H1 y obtuvo `0` divergencias. La
matriz se aborta si la barrera falla.

## Diseño

- Dataset: `datasets/eurusd_dukascopy_20y/` (EURUSD D1/H4/H1).
- Secuencia: `engine/sequential_events.py`, `canonical_bos`, profundidad mínima 4.
- Contexto: `engine.mtf_navigation.MTFNavigator`, sin EMA/ATR/OTE.
- Ancla: barra `STRUCTURE` de cada cadena, deduplicada por barra.
- Outcomes: movimiento firmado del cierre a +6, +12, +24 y +48 H1.
- Umbral interpretativo: `n >= 30` en `CTX_ALIGNED` y `CTX_AGAINST`.

## Artefactos

- Gate: `scripts/lab/experiments/exp_seq_ctx_01_gate.py`.
- Matriz: `scripts/lab/experiments/exp_seq_ctx_01.py`.
- Diagnóstico: `scripts/lab/experiments/exp_seq_ctx_01_diag_root.py`.
- Salida gate: `reports/audits/experiments/seq_ctx_01/gate_causal.json`.
- Salida matriz: `reports/audits/experiments/seq_ctx_01/matrix.json` y `.md`.

## Resultado vigente

El gate causal local está en `PASS (0/120)`. La matriz produjo `INSUFFICIENT_N`
con 53 observaciones: `CTX_ALIGNED=13`, `CTX_AGAINST=33` y `CTX_NEUTRAL=7`.
No se declara edge ni inferencia de Context State.

No se integró el candidato
aislado de `Ohm`: el código actual ya representa el primer elemento de cada
swing como barra de confirmación, por lo que sumarle `swing_left` lo retrasaría
dos veces. La matriz queda preparada, pero su interpretación depende de que
sus buckets alcancen el mínimo `n` y no autoriza entrenamiento de IA por sí sola.

## Expansiones posteriores

`EXP-SEQ-CTX-01B` probó `depth>=3` con el motor `canonical_bos`, pero no pudo
añadir observaciones porque el stage `STRUCTURE` aparece desde profundidad 4.
Su resultado fue `INSUFFICIENT_N` con los mismos 53 eventos.

`EXP-SEQ-CTX-01C` es una enmienda separada con `structure_mode=lite`; alcanzó
117 eventos OOS-elegibles (`ALIGNED=40`, `AGAINST=66`, `NEUTRAL=11`). Es
`PASS_SAMPLE_SUFFICIENT` únicamente para descripción pooled: cambia el detector
de estructura, tiene holdout 7/7 por bucket y no demuestra edge.
