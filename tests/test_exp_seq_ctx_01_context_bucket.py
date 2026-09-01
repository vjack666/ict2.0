"""Tests focales de la semántica de contexto de EXP-SEQ-CTX-01."""

from scripts.lab.experiments.exp_seq_ctx_01_dataset import context_bucket, h1_alignment


def test_context_bucket_is_directional_for_bullish_sequence():
    assert context_bucket(1, "BULLISH", "DISCOUNT", "ALIGNED") == "ALIGNED"


def test_context_bucket_is_directional_for_bearish_sequence():
    assert context_bucket(-1, "BEARISH", "PREMIUM", "ALIGNED") == "ALIGNED"


def test_context_bucket_marks_opposing_context_for_bearish_sequence():
    assert context_bucket(-1, "BULLISH", "DISCOUNT", "AGAINST") == "AGAINST"


def test_h1_alignment_uses_canonical_bias_values():
    assert h1_alignment(1, "BULLISH") == "ALIGNED"
    assert h1_alignment(-1, "BEARISH") == "ALIGNED"
    assert h1_alignment(1, "BEARISH") == "AGAINST"


def test_unknown_context_does_not_create_alignment():
    assert context_bucket(1, "UNKNOWN", "EQUILIBRIUM", "NEUTRAL") == "NEUTRAL"
    assert h1_alignment(-1, "UNKNOWN") == "NEUTRAL"

