"""T5 — ENTRENAMIENTO V2 A-F (B5 + v2 adapter + tri-state + G6/MANDATORY).
NO usa TEST_OOS para tuneo. NO declara TRAINING_ELIGIBLE.
CAN_TRADE=False; DIAGNOSTIC_ONLY.
Referencias: train_choch_full.py, train_block_encoder.py (orig), b4_nature_head.py.
Estado: T5 ejecutado con funnel replay_2006_2010_h200_funnel.json.
"""
# Datos: reports/audits/experiments/ai/replay_2006_2010_h200_funnel.json (1852 filas)
# Features: V2_FEATURE_PROFILES (A=48, B=82, C=93, D=99, E=104, F=125)
# Modelo: LogisticRegression / sklearn (mismo que b3_walkforward, no nuevo tipo)
# Ejecución: C:/Python314/python.exe scripts/lab/learning/train_v2_full.py
# Salida: data/ml/v2/{profile}.npz + .summary.json
# Verificación: tests/test_train_v2_real.py (RED→GREEN)
# Gate B6 (promotion) NO cumplido; gate B8 NO cumplido; por tanto NO TRAINING_ELIGIBLE.
# Git: commit local; NO push.
