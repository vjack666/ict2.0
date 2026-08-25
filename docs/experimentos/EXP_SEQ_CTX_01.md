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

## Reconciliación 2026-08-25 (autoridad: TNA canónico)

Este experimento quedó cerrado científicamente como negativo
(`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE`) en la rama de trabajo
`feature/a5-audit-datos`. La reconciliación selectiva (sin merge completo de
`feature/a5`) trae únicamente los artefactos documentales a un nuevo worktree
desde el estado TNA (`reconcile/tna-canonical-sci`, base `c2e9aec`), manteniendo
como autoridad canónica los archivos de motor de TNA:

- `engine/mtf_navigation.py` → sha256 `66a4008ea77282f51484ce8dcebb3384d52ccd7dbd520befd5c368f2dfa6ab9e`
- `engine/sequential_events.py` → sha256 `70e86170bead5dba094f20413e814ea48471e3e24b1125805230c738791e7901`

El gate causal se **re-ejecutó** contra exactamente ese motor TNA y regeneró
`reports/audits/experiments/seq_ctx_01/gate_causal.json`:

- `status=PASS`, `violations=[]`, `decision_count=120`, `n_violations=0`.
- `commit=c2e9aecbff16a69fe3df61ddef60812a97b62f03` (TNA real, no A5).
- `generated_at=2026-08-25T19:15Z`, `elapsed_s=272.95`.
- Dataset: `datasets/eurusd_dukascopy_20y` (D1=6258, H4=32133, H1=124377 filas).

**Nota de cadena de autoridad:** la bitácora previa en `feature/a5` registraba
hashes de motor `2905f8…`/`dc56cc…` que NO corresponden a ninguna punta de rama
(TNA ni A5) — eran de un motor transitorio. Esos valores se descartan; los
hashes canónicos son los de arriba, generados contra código que sí existe en un
commit reproducible (TNA `c2e9aec`).

**Veredicto del experimento (no cambia):** el gate PASS habilita la matriz, pero
la escasez de muestra persiste. Cierre canónico:
`OOS_EXPANSION_EXHAUSTED_NO_SUFFICIENT_EVIDENCE` (canonical 19/110/23, lite
24/177/44; 3/6 celdas `< n≥30`). Sin snapshot elegible, sin entrenamiento de IA,
`can_trade=false`. El pre-registro de `EXP-WYCKOFF-ICT-01` (Wyckoff × ICT,
documento separado) queda congelado y pendiente de go; su adaptador Wyckoff por
barra sigue BLOQUEADO.

**Cambios de A5 que quedaron FUERA de esta reconciliación:** el motor de
`feature/a5` (`engine/mtf_navigation.py`/`engine/sequential_events.py` con hashes
divergentes `43abb663…`/`d21f20b7…`), cualquier `gate_causal.json` generado contra
ese motor, los parquet M1/M5 (decisión de datos separada, legítimos pero fuera),
charts/briefs generados, y el resto de commits de laboratorio de `feature/a5`.
No se fusionó `feature/a5`; solo se integraron los documentos científicos
necesarios.
