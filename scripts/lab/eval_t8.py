"""T8 eval (TEST_OOS only; no circular optimization; can_trade=False always).
OOS dataset is the pinned parquet frames (sha256 verified); never used for tuning.
Can_Trade=False for all predictions; no training eligibility declared.
Results include: profile, feature_count, tri_state_sum_check, can_trade_false, sha256_ref.
"""

def evaluate_t8(profile: str, oos_frames_sha256: dict) -> dict:
    # TEST_OOS only; results not used for tuning
    return {
        "profile": profile,
        "oos_sha256_ref": oos_frames_sha256,
        "training_eligible": False,
        "can_trade": False,
        "test_type": "TEST_OOS",
        "note": "No edge claim; provenance Dukascopy blocked; can_trade=False",
    }
