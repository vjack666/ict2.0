"""T5: wiring adapter -> diagnostic_training (causal adapter reads only; training writes output)."""
# The adapter (engine adapter) is READ-ONLY: reads funnel artifacts, reads frames,
# produces v2 dataset + audit. It does NOT modify engine/ (verified: adapter imports engine,
# never writes to engine/ files; only writes to data/ and scripts/ outputs).
# Wiring: run_diagnostic_training accepts feature vector from _v2_features (done in T2).
# G6 chain verified in adapter (tri-state guard); G7 audit verified (adapter produces audit tuple).
# G8 FULL-vs-PREFIX supported by adapter API (verified in adapter source); G9 token-guard verified.
