# EXP-SEQ-CTX-01 — cierre de gate causal

## AGENTE

Codex / Hermes

## DEPARTAMENTO

D2 Ingeniería, D5 Assurance y D1 PMO.

## TAREA

Reproducir el gate FULL-vs-PREFIX de `EXP-SEQ-CTX-01`, verificar la frontera
temporal y dejar la matriz protegida contra ejecución sin evidencia causal.

## STATUS

COMPLETED — gate causal `PASS`, 0 divergencias en 120 decisiones H1. La matriz
canónica quedó `INSUFFICIENT_N` con 53 observaciones; la expansión canonical
`depth>=3` no cambió la población. La enmienda exploratoria `lite` alcanzó
suficiencia descriptiva pooled, pero no demuestra edge ni autoriza backtest.

## EVIDENCIA

- Driver local: `scripts/lab/experiments/exp_seq_ctx_01_gate.py`.
- Artefacto: `reports/audits/experiments/seq_ctx_01/gate_causal.json`.
- Frontera: inclusiva, `time <= decision_time` para D1/H4/H1.
- Configuración causal: `MTFNavigator(precompute_sequences=False)` para aislar
  la ruta MTF Context State.
- Resultado: `status=PASS`, `usable_for_inference=true`, `violations=0/120`.
- Matriz: `reports/audits/experiments/seq_ctx_01/matrix.json` —
  `INSUFFICIENT_N`; `ALIGNED=13`, `AGAINST=33`, `NEUTRAL=7`.
- Regresión focalizada: `11 passed` en `tests/test_mtf_navigation.py` y
  `tests/test_sequential_events.py`.
- El candidato aislado de Ohm no se integró porque el código actual ya publica
  el swing con la barra de confirmación; sumarle `swing_left` lo retrasaría dos
  veces.
- Se calcularon únicamente outcomes observacionales de la matriz; no hubo PnL,
  entradas, backtest, Funnel ni TNA nuevos en este cierre.
- Revalidación posterior local: TNA `124377/124377`, `mismatch_count=0`,
  `gate=PASS`; Funnel `COMPLETE/PASS` con H1/H4/D1=702/206/58, secuencia
  1427 cadenas/2 completas y 1239 muestras MTF.
- Regresión completa posterior: `72 passed`, 1 warning Pandas no relacionado.
- EXP-SEQ-CTX-01B: `INSUFFICIENT_N`; `depth>=3` no puede crear un stage
  `STRUCTURE` nuevo y dejó `ALIGNED=13`, `AGAINST=33`, `NEUTRAL=7`.
- EXP-SEQ-CTX-01C: `PASS_SAMPLE_SUFFICIENT` solo descriptivo, con
  `structure_mode=lite`, `min_depth=4`, 117 eventos OOS-elegibles:
  `ALIGNED=40`, `AGAINST=66`, `NEUTRAL=11`.
- EXP-SEQ-CTX-01C +24: `ALIGNED=55.00%`, `AGAINST=56.06%`, delta `-1.06 pp`.
  Bloques: DESIGN 27/49, VALIDATION 6/10, HOLDOUT 7/7; los bloques no tienen
  potencia mínima individual y el holdout no es concluyente.

## ARCHIVOS

- `scripts/lab/experiments/exp_seq_ctx_01_gate.py`
- `scripts/lab/experiments/exp_seq_ctx_01.py`
- `scripts/lab/experiments/exp_seq_ctx_01_diag_root.py`
- `docs/experimentos/EXP_SEQ_CTX_01.md`
- `reports/audits/experiments/seq_ctx_01/gate_causal.json`
- `reports/audits/experiments/seq_ctx_01/matrix.json`
- `reports/audits/experiments/seq_ctx_01/matrix.md`
- `.hermes-index.md`
- `docs/auditoria/AUDITORIAS_ESTADO.md`
- `docs/experimentos/EXP_SEQ_CTX_01B_SAMPLE_EXPANSION.md`
- `docs/experimentos/EXP_SEQ_CTX_01C_LITE_AMENDMENT.md`
- `scripts/lab/experiments/exp_seq_ctx_01b_oos.py`
- `reports/audits/experiments/seq_ctx_01b_oos/report.json`
- `reports/audits/experiments/seq_ctx_01c_lite_oos/report.json`

## RIESGOS

- El gate valida la ruta MTF sin secuencias precomputadas; no certifica por sí
  solo cualquier otra ruta del navegador.
- `PASS_SAMPLE_SUFFICIENT` en 01C solo indica que los buckets pooled alcanzan
  el umbral descriptivo; no es un PASS de edge ni de robustez OOS.
- `INSUFFICIENT_N` en 01B documenta que la variante causal no amplió la muestra;
  `lite` es otra población y no se puede mezclar con `canonical_bos`.
- El resultado `31/120` comunicado previamente no se reprodujo con este
  contrato; debe conservarse como evidencia externa no integrada hasta que se
  entregue su artefacto exacto.

## SIGUIENTE ACCIÓN

Conservar separados los resultados `canonical_bos` y `lite`; no entrenar IA ni
ejecutar backtest. Antes de cualquier backtest, solicitar decisión explícita del
cliente y exigir una revisión independiente de la estabilidad OOS.
