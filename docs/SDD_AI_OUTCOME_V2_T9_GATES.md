"""T9: gates + docs addendum (G0-G13 evidence).
Gates verified by real execution evidence (test output + adapter audit + adapter source inspection).
Status: G0/G1/G2 PARCIAL; G3/G4/G5/G6/G7/G9 IMPLEMENTADO; G8 PARCIAL (FULL verified, PREFIX verified by source);
G10/G11 PARCIAL; G12 PENDIENTE; G13 PENDIENTE (ablation stub, no results declared).
"""
GATES = {
    "G0_Provenance_Dukascopy": "PARCIAL — adapter reads data/raw/EURUSD/*.parquet; sha256 computed by adapter (test_t3 verified); provenance metadata pending full Dukascopy block",
    "G1_Snapshot_Artifact": "PARCIAL — adapter produces audit tuple; manifest file not yet written for v2",
    "G2_ContextState_NOT_Hardcoded": "PARCIAL — adapter uses MTFNavigator via import (verified engine/mtf_navigation.py); adapter does not inject hardcoded values",
    "G3_Lifecycle_Stages": "IMPLEMENTADO — adapter uses lifecycle stage from input records (verified in adapter source; test_t6 verifies lifecycle references)" ,
    "G4_M5_Micro": "IMPLEMENTADO — adapter produces micro-state feature counts (test_t3 verifies adapter produces audit for M5-level data)" ,
    "G5_M1_Micro": "IMPLEMENTADO — adapter supports M1-level micro features (verified by adapter schema)" ,
    "G6_NULL_TriState_Chain": "MANDATORY PASS — adapter validates tri-state (test_t3 + adapter source verified); feature encoding produces sum==1 for True/False/None (test_t2 verified); adapter source never collapses NULL to 0 (token-based forbidden guard prevents collapse; adapter source verified)" ,
    "G7_Funnel_Reproduction": "IMPLEMENTADO — adapter reproduces funnel artifact to v2 output (test_t3 verified audit; adapter produces AdaptedResult with events)" ,
    "G8_FULL_vs_PREFIX_NoShortcut": "PARCIAL — adapter supports FULL (verified by test_t3) and PREFIX (supported by adapter source context_provider parameter); FULL and PREFIX are separate paths (verified by adapter source inspection)" ,
    "G9_Anti_Leakage_Forward": "IMPLEMENTADO — adapter token-based forbidden guard (test_t3 verified _check_forbidden; adapter source line 56-63; token split, not substring 'in'; 'bsl' does not trigger false positive 'sl')" ,
    "G10_Chronological_Split": "PARCIAL — adapter reads pinned parquet frames (test_t3 verified sha256); split logic inherited from engine/data_feed.load_frames (verified by source); chronological split not explicitly executed in adapter",
    "G11_Reproducible_Manifest": "PARCIAL — adapter produces audit; manifest file with full sha256 reference not yet created for v2 dataset",
    "G12_OOS_Test_Only": "PENDIENTE — adapter produces TEST_OOS output (eval_t8 stub); no circular optimization applied (adapter does not write to model parameters; adapter is read-only; adapter source verified)",
    "G13_Ablation_Experiment_Equality": "PENDIENTE — ablation runner stub exists (ablation_t7); results not declared (no profile comparison executed; no training results produced)" ,
}
