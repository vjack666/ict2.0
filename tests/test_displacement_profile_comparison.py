from scripts.lab.experiments.run_displacement_profile_comparison import PROFILES


def test_ict_comparison_profile_contains_direct_m15_displacement_columns():
    assert set(PROFILES) == {"BASELINE", "ICT_ONLY"}
    assert "ict_m15_displacement_bullish" in PROFILES["ICT_ONLY"]
    assert "ict_m15_displacement_bearish" in PROFILES["ICT_ONLY"]
