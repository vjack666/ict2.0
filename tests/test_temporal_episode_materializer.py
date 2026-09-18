from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from engine.episodes import available_time
from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState
from scripts.lab.experiments.mt_temporal_episode_materializer import (
    order_reversal_report,
    temporalize_episode_artifact,
)


UTC = timezone.utc
T0 = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)


def _obj(
    oid: str,
    object_type: ObjectType,
    at: datetime,
    *,
    parent: str | None = None,
    candidate: datetime | None = None,
    confirmed: datetime | None = None,
    tradable: datetime | None = None,
    role: Role = Role.CONTEXT,
    tf: str = "M15",
) -> MarketObject:
    return MarketObject(
        id=oid,
        symbol="EURUSD",
        type=object_type,
        origin_tf=tf,
        role=role,
        direction=1,
        zone_high=1.1010,
        zone_low=1.1000,
        creation_time=at,
        candidate_time=candidate,
        confirmation_time=confirmed,
        tradable_time=tradable,
        state=ObjectState.ACTIVE,
        parent_object=parent,
        meta={"close": 1.1005},
    )


def _state(*objects: MarketObject) -> MarketState:
    ms = MarketState()
    for obj in objects:
        ms.ingest(obj)
    return ms


def _artifact(decision_time: datetime, refs: list[str]) -> dict:
    return {
        "contract_version": "EPISODES_FUNNEL_V1",
        "episodes": [
            {
                "episode_id": "EP_TEST",
                "canonical_setup_key": "EURUSD|TEST",
                "symbol": "EURUSD",
                "decision_time": decision_time,
                "direction": 1,
                "status": "ACCEPTED",
                "reason": "",
                "component_tfs": {"trigger": "M15"},
                "lineage": {"trigger": refs[-1]},
                "object_refs": refs,
            }
        ],
    }


def _chain():
    # LIQUIDITY and SWEEP become known on the same closed bar. Parent depth must
    # break the tie causally: LIQUIDITY -> SWEEP, never UUID/lexicographic order.
    liquidity = _obj("Z_LIQ", ObjectType.LIQUIDITY, T0)
    sweep = _obj("A_SWEEP", ObjectType.SWEEP, T0, parent=liquidity.id)
    t1 = T0 + timedelta(minutes=15)
    displacement = _obj(
        "DISP",
        ObjectType.DISPLACEMENT,
        t1,
        parent=sweep.id,
        candidate=t1,
        confirmed=t1,
        tradable=t1,
        role=Role.TRIGGER,
    )
    return liquidity, sweep, displacement


def test_available_at_is_candidate_time_not_confirmation_or_tradable():
    candidate = T0
    confirmation = T0 + timedelta(minutes=15)
    obj = _obj(
        "FVG",
        ObjectType.FVG,
        confirmation,
        candidate=candidate,
        confirmed=confirmation,
        tradable=confirmation,
        role=Role.REFINEMENT,
    )
    assert available_time(obj) == candidate


def test_available_at_falls_back_to_creation_for_legacy_sequence_object():
    obj = _obj("SWEEP", ObjectType.SWEEP, T0)
    assert obj.candidate_time is None
    assert available_time(obj) == T0


def test_materializer_orders_equal_timestamp_parent_before_child_and_preserves_time_states():
    liquidity, sweep, displacement = _chain()
    decision = T0 + timedelta(hours=1)
    ms = _state(liquidity, sweep, displacement)
    result = temporalize_episode_artifact(ms, _artifact(decision, [displacement.id]))

    assert result["episodes_total"] == 1
    episode = result["episodes"][0]
    assert [event["event_type"] for event in episode["events"]] == [
        "LIQUIDITY",
        "SWEEP",
        "DISPLACEMENT",
    ]
    assert episode["events"][0]["available_at"] == T0.isoformat()
    assert episode["events"][2]["candidate_time"] == (T0 + timedelta(minutes=15)).isoformat()
    assert episode["events"][2]["confirmed_at"] == (T0 + timedelta(minutes=15)).isoformat()
    assert episode["events"][2]["tradable_at"] == (T0 + timedelta(minutes=15)).isoformat()
    assert episode["events"][1]["parent_id"] == liquidity.id
    assert episode["events"][2]["parent_id"] == sweep.id


def test_order_reversal_is_sequence_sensitive():
    liquidity, sweep, displacement = _chain()
    decision = T0 + timedelta(hours=1)
    result = temporalize_episode_artifact(
        _state(liquidity, sweep, displacement),
        _artifact(decision, [displacement.id]),
    )
    report = order_reversal_report(result["episodes"])
    assert report["episodes_tested"] == 1
    assert report["different"] == 1
    assert report["identical"] == 0
    assert report["verdict"] == "PASS"


def test_future_candidate_fails_closed_even_if_object_creation_is_before_decision():
    decision = T0 + timedelta(hours=1)
    obj = _obj(
        "FUTURE_CANDIDATE",
        ObjectType.FVG,
        T0,
        candidate=decision + timedelta(minutes=1),
        confirmed=decision + timedelta(minutes=2),
        tradable=decision + timedelta(minutes=2),
        role=Role.REFINEMENT,
    )
    ms = _state(obj)
    with pytest.raises(ValueError, match="TEMPORAL_FUTURE_DATA"):
        temporalize_episode_artifact(ms, _artifact(decision, [obj.id]))


def test_full_prefix_and_future_injection_are_identical_at_decision_time():
    liquidity, sweep, displacement = _chain()
    decision = T0 + timedelta(hours=1)

    prefix = _state(liquidity, sweep, displacement)

    # FULL has information that only exists after decision_time.
    future = _obj(
        "FUTURE",
        ObjectType.RETURN,
        decision + timedelta(hours=1),
        parent=displacement.id,
    )
    full = _state(liquidity, sweep, displacement, future)

    artifact = _artifact(decision, [displacement.id])
    prefix_result = temporalize_episode_artifact(prefix, artifact)
    full_result = temporalize_episode_artifact(full, artifact)

    assert prefix_result == full_result


def test_wyckoff_is_explicitly_missing_when_not_supplied():
    liquidity, sweep, displacement = _chain()
    decision = T0 + timedelta(hours=1)
    result = temporalize_episode_artifact(
        _state(liquidity, sweep, displacement),
        _artifact(decision, [displacement.id]),
    )
    wyckoff = result["episodes"][0]["wyckoff_context"]
    assert wyckoff["status"] == "MISSING"
    assert "no causal Wyckoff context" in wyckoff["reason"]


def test_wyckoff_context_is_preserved_without_invention():
    liquidity, sweep, displacement = _chain()
    decision = T0 + timedelta(hours=1)
    result = temporalize_episode_artifact(
        _state(liquidity, sweep, displacement),
        _artifact(decision, [displacement.id]),
        wyckoff_by_decision={
            decision: {
                "phase": "ACCUMULATION",
                "source": "engine/Wyckoff",
                "asof_time": decision.isoformat(),
            }
        },
    )
    wyckoff = result["episodes"][0]["wyckoff_context"]
    assert wyckoff["status"] == "AVAILABLE"
    assert wyckoff["phase"] == "ACCUMULATION"
    assert wyckoff["source"] == "engine/Wyckoff"
