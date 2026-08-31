from __future__ import annotations

from scripts.lab.experiments.ai_outcome_funnel_bridge import build_funnel_artifact


def _payload(prefix=False):
    return {
        "schema_version": "1.0",
        "symbol": "TEST",
        "timeframe": "H1",
        "candles": [{"index": 0, "time": "2024-01-01T00:00:00+00:00"}],
        "events": [],
        "signals": [{
            "signal_index": 0,
            "episode_id": "EP_0",
            "decision_time": "2024-01-01T00:00:00+00:00",
            "direction": 1,
            "features_at_t": {
                "sequence": ["SWEEP", "DISPLACEMENT", "STRUCTURE"],
                "sequence_depth": 3,
                "context_inputs": {
                    "sequence_direction": 1,
                    "d1_bias": "UNKNOWN",
                    "h4_location": "UNKNOWN",
                    "h1_alignment": "NEUTRAL",
                },
            },
            "lineage": {"BOS": "BOS_1"},
            "event_objects": {"BOS_1": {"id": "BOS_1"}},
        }],
        "trades": [{
            "id": "TRADE_1",
            "signal_index": 0,
            "entry_index": 0,
            "outcome": "TP",
        }],
        "metadata": {
            "causal": True,
            "full_prefix": {"prefix_matches_full": prefix},
            "provenance": {"source": "fixture"},
        },
    }


def test_bridge_links_trade_without_copying_outcome_into_features():
    artifact = build_funnel_artifact(_payload(prefix=True), generator_commit="a" * 40)
    assert artifact["aggregated_status"] == "PASS"
    assert artifact["episodes"][0]["meta"]["backtest_signal_index"] == 0
    assert "outcome" not in artifact["episodes"][0]["features_at_t"]
    assert artifact["backtest_linkage"]["outcome_not_copied_into_features"] is True


def test_bridge_stays_blocked_without_prefix_proof():
    artifact = build_funnel_artifact(_payload(prefix=False), generator_commit="a" * 40)
    assert artifact["aggregated_status"] == "BLOCKED"
    assert artifact["gates"]["causal_full_vs_prefix"] == "BLOCKED"
