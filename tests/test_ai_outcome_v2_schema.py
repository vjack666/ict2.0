"""Tests for v2 schema validation in load_causal_jsonl (T1)."""
import json
import tempfile
from pathlib import Path

import pytest

from runtime.ai_learning.diagnostic_training import load_causal_jsonl, DiagnosticTrainingError


def _v1_row():
    return {
        "episode_id": "ep1",
        "event_time": "2006-01-02T10:00:00Z",
        "label_available_time": "2006-01-02T13:00:00Z",
        "label_end_12": "continuation",
        "can_trade": False,
        "direction": 1,
        "sequence_depth": 5,
        "features_at_t": {
            "context_inputs": {
                "sequence_direction": 1,
                "d1_bias": "BULLISH",
                "h4_location": "EQUILIBRIUM",
                "h1_alignment": "NEUTRAL",
            },
            "sequence": ["LIQUIDITY_POOL"],
        },
    }


def _v2_row(episode_id="ep2"):
    return {
        "episode_id": episode_id,
        "event_time": "2006-01-02T11:00:00Z",
        "label_available_time": "2006-01-02T14:00:00Z",
        "label_end_12": "reversal",
        "can_trade": False,
        "direction": -1,
        "sequence_depth": 3,
        "features_at_t": {
            "schema_group": "engine_v2",
            "context_state": {
                "layer_status": {"D1": "OK", "H4": "INCOMPLETE", "H1": "BLOCKED"},
                "direction_hint": "BEARISH",
                "regime_stack": {"D1": "TREND_BEAR", "H4": "RANGE", "H1": "UNKNOWN"},
                "location": "EQUILIBRIUM",
            },
            "zones": {
                "poi": {"count": 2},
                "bsl": {"count": 0},
                "ssl": {"count": 1},
                "proximity": 0.5,
            },
            "lifecycle": {"stage": "SETUP"},
            "M5": {"m5_bos": False, "m5_displacement": True, "m5_fvg": False},
            "M1": {"m1_trigger": True, "m1_retest": "NO_RETEST"},
            "permissions": {"allow_long": True, "allow_short": None},
            "lineage": {"depth": 2, "count": 3},
            "reason_codes": [],
            "intraday_v2": {
                "ict_m15": {
                    "ict_m15_fvg_bullish": False,
                    "ict_m15_fvg_bearish": True,
                    "ict_m15_ob_bullish": False,
                    "ict_m15_ob_bearish": False,
                    "ict_m15_choch_bullish": False,
                    "ict_m15_choch_bearish": False,
                    "ict_m15_displacement_bullish": True,
                    "ict_m15_displacement_bearish": False,
                    "ict_m15_sweep_up": False,
                    "ict_m15_sweep_down": False,
                },
                "wyckoff": {
                    "H1": {"phase": "DISTRIBUTION", "phase_progress": 0.7, "events": ["SPRING"]},
                    "M15": {"phase": "ACCUMULATION", "phase_progress": 0.3, "events": ["UTAD"]},
                },
            },
        },
    }


def _v2_missing_row(episode_id="ep3"):
    """v2 row with empty features_at_t (no schema_group) — should still fail."""
    return {
        "episode_id": episode_id,
        "event_time": "2006-01-02T12:00:00Z",
        "label_available_time": "2006-01-02T15:00:00Z",
        "label_end_12": "failure",
        "can_trade": False,
        "direction": 0,
        "sequence_depth": 0,
        "features_at_t": {},
    }


@pytest.fixture
def v1_v2_jsonl_path():
    """Create a temp jsonl with v1 and v2 rows only (valid ones)."""
    lines = [json.dumps(_v1_row()), json.dumps(_v2_row(episode_id="ep2"))]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(lines))
        p = f.name
    yield p
    Path(p).unlink(missing_ok=True)


@pytest.fixture
def v2_missing_jsonl_path():
    """Create a temp jsonl with a v2 row missing required keys."""
    lines = [json.dumps(_v2_missing_row())]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(lines))
        p = f.name
    yield p
    Path(p).unlink(missing_ok=True)


@pytest.fixture
def mixed_jsonl_path():
    """Create a temp jsonl with v1, v2 and missing rows."""
    lines = [
        json.dumps(_v1_row()),
        json.dumps(_v2_row()),
        json.dumps(_v2_missing_row()),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(lines))
        p = f.name
    yield p
    Path(p).unlink(missing_ok=True)


def test_v2_rows_pass_load_causal_jsonl_v1_row_loads(v1_v2_jsonl_path):
    """The v1 row (no schema_group) loads without error (backward compat)."""
    result = load_causal_jsonl(v1_v2_jsonl_path, target="label_end_12")
    ids = [r["episode_id"] for r in result.rows]
    assert "ep1" in ids
    # raw_sha256 and schema_hash are present
    assert len(result.raw_sha256) == 64
    assert len(result.schema_hash) == 64


def test_v2_rows_pass_load_causal_jsonl_v2_row_loads(v1_v2_jsonl_path):
    """The v2 row (schema_group='engine_v2') loads without raising 'causal incompleto'."""
    result = load_causal_jsonl(v1_v2_jsonl_path, target="label_end_12")
    ids = [r["episode_id"] for r in result.rows]
    assert "ep2" in ids
    v2 = next(r for r in result.rows if r["episode_id"] == "ep2")
    assert v2["features_at_t"]["schema_group"] == "engine_v2"
    assert v2["features_at_t"]["permissions"]["allow_short"] is None  # NULL preserved


def test_v2_rows_pass_load_causal_jsonl_missing_row_raises(v2_missing_jsonl_path):
    """The missing v2 row (no v1 context_inputs, no v2 keys) raises DiagnosticTrainingError."""
    with pytest.raises(DiagnosticTrainingError) as exc_info:
        load_causal_jsonl(v2_missing_jsonl_path, target="label_end_12")
    msg = str(exc_info.value)
    # Must mention missing engine_v2 keys or "causal incompleto" (empty features_at_t falls back to v1 checks, which also fail)
    assert "causal incompleto" in msg or "faltan" in msg or "desconocido" in msg or "engine_v2" in msg


def test_mixed_v1_v2_missing_jsonl_detects_missing_first(tmp_path):
    """When mixing v1, v2, and missing rows in the same JSONL."""
    lines = [
        json.dumps(_v1_row()),
        json.dumps(_v2_row()),
        json.dumps(_v2_missing_row()),
    ]
    p = tmp_path / "mixed_with_missing.jsonl"
    p.write_text("\n".join(lines))
    with pytest.raises(DiagnosticTrainingError) as exc_info:
        load_causal_jsonl(p, target="label_end_12")
    msg = str(exc_info.value)
    # The error must reference an invalid row
    assert "fila" in msg.lower()


def test_v2_only_row_alone_loads(tmp_path):
    """A pure v2 JSONL (no v1 rows) loads and preserves permissions NULL."""
    only_v2 = [_v2_row(episode_id="only1")]
    p = tmp_path / "v2_only.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in only_v2))
    result = load_causal_jsonl(p, target="label_end_12")
    assert len(result.rows) == 1
    assert result.rows[0]["features_at_t"]["permissions"]["allow_short"] is None


def test_unknown_schema_group_raises(tmp_path):
    """A row with an unknown schema_group must be rejected."""
    row = _v2_row(episode_id="bad")
    row["features_at_t"]["schema_group"] = "weird_v99"
    p = tmp_path / "bad.jsonl"
    p.write_text(json.dumps(row))
    with pytest.raises(DiagnosticTrainingError) as exc_info:
        load_causal_jsonl(p, target="label_end_12")
    assert "schema_group" in str(exc_info.value)


def test_v1_row_survives_in_mixed_v1_v2_context(tmp_path):
    """v1 rows mixed with v2 rows both load correctly in the same file."""
    # Two valid rows, one v1 one v2
    lines = [json.dumps(_v1_row()), json.dumps(_v2_row(episode_id="ep2b"))]
    p = tmp_path / "mixed_valid.jsonl"
    p.write_text("\n".join(lines))
    result = load_causal_jsonl(p, target="label_end_12")
    assert len(result.rows) == 2
    ids = {r["episode_id"] for r in result.rows}
    assert ids == {"ep1", "ep2b"}