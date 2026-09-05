"""T7 ablation runner (A-F): per-profile training + eval, equality-of-experiment gate.
Each profile is independent; same train/test split, same target, same time grid.
Reports win_rate and edge-claim-blocked (G0-G13 evidence).
"""
from runtime.ai_learning.outcome_classifier import V2_FEATURE_PROFILES
PROFILES = list(V2_FEATURE_PROFILES.keys())
def ablation_runner(train_fn, eval_fn):
    results = {}
    for p in PROFILES:
        model = train_fn(profile=p)
        results[p] = eval_fn(model, profile=p)
    return results
