from __future__ import annotations

from backtest.sixtf_forensic import (
    audit_episode_sequence,
    build_ai_shadow_dataset,
    build_timeframe_worker_evidence,
    classify_entry_protocols,
    classify_session,
    write_blackbox_jsonl,
)


def _episode(component_audit: dict, decision_time: str = "2022-03-15T10:00:00Z") -> dict:
    return {
        "episode_id": "EP_FORENSIC",
        "decision_time": decision_time,
        "direction": 1,
        "component_tfs": {
            "context_htf": "D1",
            "poi": "H4",
            "refinement": "M15",
            "confirmation": "M5",
            "trigger": "M1",
        },
        "object_refs": ["D1", "H4", "M15", "M5", "M1"],
        "meta": {"component_audit": component_audit},
    }


def _component(tf: str, ts: str, *, bar: int, closed: bool = True) -> dict:
    return {
        "present": True,
        "id": f"{tf}-{bar}",
        "origin_tf": tf,
        "type": "ORDER_BLOCK",
        "role": "POI",
        "bar_time": ts,
        "bar_index": bar,
        "candidate_time": ts,
        "creation_time": ts,
        "confirmation_time": ts,
        "tradable_time": ts,
        "closed_bar_only": closed,
    }


def test_same_bar_multi_stage_blocks_episode_for_ai_calibration():
    ts = "2022-03-15T09:30:00Z"
    audit = audit_episode_sequence(
        _episode(
            {
                "refinement": _component("M15", ts, bar=10),
                "confirmation": _component("M5", ts, bar=10),
                "trigger": _component("M1", ts, bar=10),
            }
        )
    )

    assert audit["sequence_audit_status"] == "BLOCKED"
    assert "SAME_BAR_CORE_STAGE" in audit["reasons"]
    assert "SAME_TIMESTAMP_STAGE" in audit["reasons"]


def test_future_component_blocks_episode():
    audit = audit_episode_sequence(
        _episode(
            {
                "refinement": _component("M15", "2022-03-15T09:30:00Z", bar=10),
                "confirmation": _component("M5", "2022-03-15T09:45:00Z", bar=11),
                "trigger": _component("M1", "2022-03-15T10:01:00Z", bar=12),
            }
        )
    )

    assert audit["sequence_audit_status"] == "BLOCKED"
    assert "FUTURE_CONTEXT" in audit["reasons"]


def test_htf_not_closed_blocks_episode():
    audit = audit_episode_sequence(
        _episode({"poi": _component("H4", "2022-03-15T08:00:00Z", bar=5, closed=False)})
    )

    assert audit["sequence_audit_status"] == "BLOCKED"
    assert "HTF_NOT_CLOSED" in audit["reasons"]


def test_ordered_episode_passes_when_evidence_is_not_compressed():
    audit = audit_episode_sequence(
        _episode(
            {
                "context_htf": {
                    **_component("D1", "2022-03-14T00:00:00Z", bar=1),
                    "confirmation_time": "2022-03-14T00:01:00Z",
                    "tradable_time": "2022-03-14T00:02:00Z",
                },
                "poi": {
                    **_component("H4", "2022-03-15T04:00:00Z", bar=2),
                    "confirmation_time": "2022-03-15T04:01:00Z",
                    "tradable_time": "2022-03-15T04:02:00Z",
                },
                "refinement": {
                    **_component("M15", "2022-03-15T09:00:00Z", bar=3),
                    "confirmation_time": "2022-03-15T09:01:00Z",
                    "tradable_time": "2022-03-15T09:02:00Z",
                },
                "confirmation": {
                    **_component("M5", "2022-03-15T09:20:00Z", bar=4),
                    "confirmation_time": "2022-03-15T09:21:00Z",
                    "tradable_time": "2022-03-15T09:22:00Z",
                },
                "trigger": {
                    **_component("M1", "2022-03-15T09:40:00Z", bar=5),
                    "confirmation_time": "2022-03-15T09:41:00Z",
                    "tradable_time": "2022-03-15T09:42:00Z",
                },
            }
        )
    )

    assert audit["sequence_audit_status"] == "PASS"
    assert audit["reasons"] == []
    assert audit["review_flags"] == []


def test_london_new_york_session_classifier_uses_local_dst():
    london = classify_session("2022-03-15T09:00:00Z")
    new_york = classify_session("2022-03-15T13:00:00Z")
    off = classify_session("2022-03-15T22:00:00Z")

    assert london["session"] == "LONDON"
    assert new_york["session"] == "NEW_YORK"
    assert off["session"] == "OFF_SESSION"


def test_ai_shadow_features_do_not_include_future_labels():
    trade = {
        "episode_id": "EP_FORENSIC",
        "decision_time": "2022-03-15T13:00:00Z",
        "direction": 1,
        "session": "NEW_YORK",
        "in_london": False,
        "in_new_york": True,
        "risk_pips": 10.0,
        "reward_r": 2.0,
        "horizon_m1_bars": 240,
        "component_tfs": {"trigger": "M1"},
        "object_refs": ["M1"],
        "exit_status": "SL",
        "net_R": -1.23,
        "economic_status": "RESOLVED",
    }
    dataset = build_ai_shadow_dataset(
        [trade],
        [{"episode_id": "EP_FORENSIC", "sequence_audit_status": "PASS", "reasons": [], "review_flags": []}],
        {"EP_FORENSIC": {"primary_family": "PO3", "complete_families": ["PO3"]}},
    )

    assert dataset["feature_label_leakage_pass"] is True
    assert dataset["rows"][0]["ai_shadow_decision"] == "ACEPTAR_ANALISIS"
    assert "net_R" not in dataset["rows"][0]["features"]
    assert "exit_status" not in dataset["rows"][0]["features"]


def test_ai_shadow_abstains_without_complete_entry_protocol():
    dataset = build_ai_shadow_dataset(
        [
            {
                "episode_id": "EP_NO_PROTOCOL",
                "decision_time": "2022-03-15T13:00:00Z",
                "direction": 1,
                "session": "NEW_YORK",
                "in_london": False,
                "in_new_york": True,
                "component_tfs": {},
                "object_refs": [],
            }
        ],
        [{"episode_id": "EP_NO_PROTOCOL", "sequence_audit_status": "PASS", "reasons": [], "review_flags": []}],
        {"EP_NO_PROTOCOL": {"primary_family": "NONE", "complete_families": []}},
    )

    assert dataset["rows"][0]["ai_shadow_decision"] == "ABSTENERSE"
    assert dataset["rows"][0]["features"]["entry_protocol_primary"] == "NONE"


def test_entry_protocol_classifier_uses_existing_po3_and_silver_bullet_modules():
    episode = _episode({}, decision_time="2022-03-15T14:55:00Z")
    audit = {
        "episode_id": "EP_FORENSIC",
        "sequence_evidence": {
            "sequence_status": "PASS",
            "nodes": [
                {"stage": "SWEEP", "time": "2022-03-15T14:10:00Z", "detail": "sweep_EQL"},
                {"stage": "STRUCTURE", "time": "2022-03-15T14:20:00Z"},
                {"stage": "OB", "time": "2022-03-15T14:25:00Z"},
                {"stage": "FVG", "time": "2022-03-15T14:30:00Z"},
                {"stage": "RETEST", "time": "2022-03-15T14:45:00Z"},
            ],
        },
    }
    frames = {
        "M1": __import__("pandas").DataFrame(
            [
                {"time": "2022-03-14T00:00:00Z", "open": 1.10, "high": 1.11, "low": 1.09, "close": 1.10},
                {"time": "2022-03-15T14:10:00Z", "open": 1.10, "high": 1.101, "low": 1.089, "close": 1.1005},
                {"time": "2022-03-15T14:11:00Z", "open": 1.1005, "high": 1.103, "low": 1.1004, "close": 1.1028},
            ]
        )
    }

    protocol = classify_entry_protocols(episode, audit, frames, ltf="M1")

    assert protocol["families"]["PO3"]["complete"] is True
    assert protocol["families"]["SILVER_BULLET"]["complete"] is True
    assert "PO3" in protocol["complete_families"]
    assert "SILVER_BULLET" in protocol["complete_families"]


def test_timeframe_worker_evidence_keeps_six_tf_workers_diagnostic_only():
    pd = __import__("pandas")
    frames = {}
    for tf, freq in {
        "D1": "1D",
        "H4": "4h",
        "H1": "1h",
        "M15": "15min",
        "M5": "5min",
        "M1": "1min",
    }.items():
        times = pd.date_range("2022-03-01T00:00:00Z", periods=240, freq=freq)
        frames[tf] = pd.DataFrame(
            {
                "time": times,
                "open": [1.10 + i * 0.0001 for i in range(len(times))],
                "high": [1.101 + i * 0.0001 for i in range(len(times))],
                "low": [1.099 + i * 0.0001 for i in range(len(times))],
                "close": [1.1005 + i * 0.0001 for i in range(len(times))],
                "volume": [100 + i for i in range(len(times))],
            }
        )

    evidence = build_timeframe_worker_evidence(
        frames,
        ["2022-03-05T12:00:00Z"],
        {"EP_FORENSIC": {"sequence_status": "PASS"}},
    )

    assert set(evidence["worker_model"]) >= {"D1", "H4", "H1", "M15", "M5", "M1", "COORDINATOR"}
    assert evidence["layer_counts"]["D1"]["available"] == 1
    assert evidence["m1_sequence_status_counts"]["PASS"] == 1
    assert evidence["policy"]["can_trade"] is False
    assert evidence["policy"]["entry_authorized"] is False


def test_real_sequence_evidence_supersedes_synthetic_compression_review():
    ts = "2022-03-15T09:30:00Z"
    audit = audit_episode_sequence(
        _episode(
            {
                "refinement": _component("M15", ts, bar=10),
                "confirmation": _component("M5", ts, bar=11),
                "trigger": _component("M1", ts, bar=12),
            }
        ),
        {
            "sequence_status": "PASS",
            "timeframe": "M1",
            "chain_id": "SEQ_M1_1",
            "stages": ["LIQUIDITY_POOL", "SWEEP", "DISPLACEMENT", "STRUCTURE", "OB", "FVG", "RETEST"],
            "strictly_increasing_bars": True,
        },
    )

    assert audit["sequence_audit_status"] == "PASS"
    assert "SYNTHETIC_STAGE_COMPRESSION" not in audit["review_flags"]
    assert audit["sequence_evidence"]["chain_id"] == "SEQ_M1_1"


def test_blackbox_jsonl_records_forensic_and_policy(tmp_path):
    path = tmp_path / "blackbox.jsonl"
    write_blackbox_jsonl(
        path=path,
        trades=[
            {
                "episode_id": "EP_FORENSIC",
                "decision_time": "2022-03-15T13:00:00Z",
                "exit_status": "TP",
                "net_R": 0.77,
                "session": "NEW_YORK",
            }
        ],
        audit_rows=[
            {
                "episode_id": "EP_FORENSIC",
                "sequence_audit_status": "PASS",
                "sequence_evidence": {"chain_id": "SEQ_M1_1"},
            }
        ],
        ai_rows=[
            {
                "features": {"episode_id": "EP_FORENSIC"},
                "ai_shadow_decision": "ACEPTAR_ANALISIS",
            }
        ],
    )

    line = path.read_text(encoding="utf-8").strip()
    assert '"kind": "SIXTF_FORENSIC_BLACKBOX_V1"' in line
    assert '"can_trade": false' in line
    assert '"chain_id": "SEQ_M1_1"' in line
