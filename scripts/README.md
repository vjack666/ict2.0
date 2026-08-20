# Scripts — manifiesto de roles

Los scripts son entrypoints. Ningún script es autoridad semántica del mercado;
la autoridad está en `engine/` y sus contratos.

## Roles

| Rol | Scripts |
|---|---|
| `DAILY` | `daily/brief_lunes.py`, `daily/update_mt5_ict.py`, `run_brief_lunes.bat` |
| `PRESENTATION` | `presentation/make_bos_chart.py`, `presentation/plot_htf_reading.py`, `presentation/plot_tradingview_zones.py` |
| `SMOKE` | `smoke/smoke_consensus.py`, `smoke/smoke_motor.py`, `smoke/smoke_motor_lectura.py`, `smoke/verify_engine.py`, `smoke/_htf_check.py` |
| `DATA` | `data/import_forex_data.py`, `data/gen_bos_dataset.py`, `data/gen_choch_dataset.py`, `data/gen_swing_dataset.py`, `acquire_eurusd_20y.sh` |
| `AUDIT` | `audit/diag_nav_baseline.py`, `audit/diag_nav_baseline_csv.py`, `audit/grok_mtf_batches.py`, `audit/grok_run_funnel_20y_full.py`, `audit/regression_nav_strict.py`, `audit/tna_20y_parallel.py`, `audit/tna_audit_runner.py`, `audit/tna_fullish_runner.py`, `audit/tna_sandbox_runner.py` |
| `EXPERIMENT` | `lab/experiments/exp_sequence_x_context_state.py` |
| `LEARNING` | `lab/learning/b0_baseline_measure.py`, `lab/learning/b1_label_audit.py`, `lab/learning/b2_dataset_factory.py`, `lab/learning/b3_walkforward.py`, `lab/learning/b4_nature_head.py`, `lab/learning/eval_choch_model.py`, `lab/learning/eval_model_small.py`, `lab/learning/label_human.py`, `lab/learning/learning_pipeline.py`, `lab/learning/probe_choch_nature.py`, `lab/learning/scan_classify.py`, `lab/learning/train_block_encoder.py`, `lab/learning/train_choch_full.py`, `lab/learning/train_choch_score.py`, `lab/learning/train_nature_head.py` |
| `CLOUD_REFERENCE` | `scripts/aws/benchmark.py`, `scripts/aws/launch_ec2.sh`, `scripts/aws/user_data.sh` |

## Reglas

- El script llama a `engine`; no reemplaza al motor.
- Todo script nuevo debe declarar su rol y autoridad (`CANONICAL_AUTHORITY =
  False` salvo entrypoints explícitamente aprobados).
- Los scripts de aprendizaje producen evidencia y modelos, nunca cambian
  automáticamente el runtime.
- Las rutas antiguas de Python se mantienen como wrappers de compatibilidad y
  delegan a la ruta canónica. El código nuevo debe importarse o ejecutarse
  desde la ruta clasificada, no desde el wrapper.
