"""B2-V2 — DATASET FACTORY V2 (compat con ai-outcome-v2). NO modifica original."""
# Usa engine/data_feed.load_frames (pinned), adapter v2, V2_FEATURE_PROFILES.
# Produce dataset con manifest sha256 + schema_group=engine_v2 + tri-state.
MAN_DIR = "data/learning/pipeline/manifests"
OUT_ROOT = "data/learning/choch/v2"
SYMS = ["EURUSD"]
TFS = ["M1", "M5", "H1", "H4", "D1"]
# V2 profiles: A=48 (baseline) -> F=125
# Cada fila: event + features (tri-state encoded) + audit_ref + sha256
# No entrenamiento; solo generacion + registro (mismo contrato B2 original).
# CAN_TRADE=False; TRAINING_ELIGIBLE=False; NO edge claim; DIAGNOSTIC_ONLY.
# ADAPTER: scripts.lab.experiments.ai_outcome_v2_adapter (ya creado, verificado).
# Referencia: b2_dataset_factory.py lineas 1-156 (original); b3_walkforward.py lineas 1-109 (original).
# Estado actual: T3 adapter ejecutado con EURUSD real (D1 sha256 dd4939f...).
V2_PROFILES = {"V2_A": 48, "V2_B": 82, "V2_C": 93, "V2_D": 99, "V2_E": 104, "V2_F": 125}
# Output: data/learning/choch/v2/EURUSD/<tf>/features.jsonl + manifest .json
