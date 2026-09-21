"""Mission 1 six-TF funnel/backtest/AI shadow pipeline.

This module is a small contractual bridge from the already-certified six
timeframe lineage machinery to Episodes/Funnel, economic accounting and a
shadow-only learning report.  It is deliberately deterministic and local-only:
it does not connect MT5, modify market data, execute orders or claim edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from backtest.economics import EconomicScenario, account_trade_economics
from engine import episodes as EP
from engine.lineage_hierarchy import (
    LineageStatus,
    build_hierarchical_lineage,
    lineage_result_to_snapshot_summary,
)
from engine.market_object import MarketObject, ObjectState, ObjectType, Role
from engine.market_state import MarketState
from engine.setup_builder import Setup, SetupEligibility


MISSION1_SCHEMA_VERSION = "1.0"
SIX_TFS = ("D1", "H4", "H1", "M15", "M5", "M1")
OUTCOME_CLASSES = ("continuation", "reversal", "failure")


@dataclass(frozen=True)
class Mission1Config:
    """Configuration for a deterministic local Mission 1 run."""

    symbol: str = "EURUSD"
    rows: int = 60
    start_time: datetime = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    step_minutes: int = 15
    entry: float = 1.1000
    risk_pips: float = 10.0


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _object(
    *,
    object_id: str,
    symbol: str,
    object_type: ObjectType,
    role: Role,
    tf: str,
    direction: int,
    when: datetime,
    bar_index: int,
    parent: str | None = None,
    related: Iterable[str] = (),
) -> MarketObject:
    return MarketObject(
        id=object_id,
        symbol=symbol,
        type=object_type,
        origin_tf=tf,
        role=role,
        direction=direction,
        zone_high=1.1010 + bar_index * 0.00001,
        zone_low=1.0990 + bar_index * 0.00001,
        creation_time=when,
        candidate_time=when,
        confirmation_time=when,
        tradable_time=when,
        bar_index=bar_index,
        candidate_bar=bar_index,
        confirmation_bar=bar_index,
        tradable_bar=bar_index,
        state=ObjectState.ACTIVE,
        parent_object=parent,
        related_objects=list(related),
    )


def _six_tf_chain(
    *,
    symbol: str,
    index: int,
    decision_time: datetime,
    direction: int,
) -> tuple[MarketState, Setup, dict[str, MarketObject]]:
    """Build one point-in-time six-TF causal chain.

    The H4 POI intentionally has no ``parent_object`` because the existing
    Episodes v1 contract treats the POI as the local funnel root.  The D1
    context is still connected through ``related_objects`` and is validated by
    ``build_hierarchical_lineage(require_all_six_tfs=True)``.
    """

    base = decision_time - timedelta(hours=6)
    ids = {
        "D1": f"M1_{index:03d}_D1_CONTEXT",
        "H4": f"M1_{index:03d}_H4_POI",
        "H1": f"M1_{index:03d}_H1_CONTEXT",
        "M15": f"M1_{index:03d}_M15_REFINEMENT",
        "M5": f"M1_{index:03d}_M5_CONFIRMATION",
        "M1": f"M1_{index:03d}_M1_TRIGGER",
    }
    d1 = _object(
        object_id=ids["D1"],
        symbol=symbol,
        object_type=ObjectType.ORDER_BLOCK,
        role=Role.POI,
        tf="D1",
        direction=direction,
        when=base,
        bar_index=index * 10,
        related=[],
    )
    h4 = _object(
        object_id=ids["H4"],
        symbol=symbol,
        object_type=ObjectType.ORDER_BLOCK,
        role=Role.POI,
        tf="H4",
        direction=direction,
        when=base + timedelta(hours=1),
        bar_index=index * 10 + 1,
        related=[ids["D1"]],
    )
    h1 = _object(
        object_id=ids["H1"],
        symbol=symbol,
        object_type=ObjectType.ORDER_BLOCK,
        role=Role.POI,
        tf="H1",
        direction=direction,
        when=base + timedelta(hours=2),
        bar_index=index * 10 + 2,
        parent=ids["H4"],
        related=[],
    )
    m15 = _object(
        object_id=ids["M15"],
        symbol=symbol,
        object_type=ObjectType.FVG,
        role=Role.REFINEMENT,
        tf="M15",
        direction=direction,
        when=base + timedelta(hours=3),
        bar_index=index * 10 + 3,
        parent=ids["H4"],
        related=[],
    )
    m5 = _object(
        object_id=ids["M5"],
        symbol=symbol,
        object_type=ObjectType.BOS,
        role=Role.CONFIRMATION,
        tf="M5",
        direction=direction,
        when=base + timedelta(hours=4),
        bar_index=index * 10 + 4,
        parent=ids["M15"],
        related=[ids["M1"]],
    )
    m1 = _object(
        object_id=ids["M1"],
        symbol=symbol,
        object_type=ObjectType.DISPLACEMENT,
        role=Role.TRIGGER,
        tf="M1",
        direction=direction,
        when=base + timedelta(hours=5),
        bar_index=index * 10 + 5,
        parent=ids["M15"],
        related=[],
    )
    objects = {obj.origin_tf: obj for obj in (d1, h4, h1, m15, m5, m1)}
    ms = MarketState()
    for tf in SIX_TFS:
        ms.ingest(objects[tf])
    setup = Setup(
        id=f"M1_SETUP_{index:03d}",
        symbol=symbol,
        direction=direction,
        context_htf=d1,
        poi=h4,
        refinement=m15,
        confirmation=m5,
        trigger=m1,
        eligibility=SetupEligibility.ELIGIBLE,
        created_at=decision_time,
        meta={
            "mission": "MISION1",
            "six_tf_chain": list(SIX_TFS),
            "lineage_required": True,
        },
    )
    return ms, setup, objects


def build_six_tf_episode_artifact(config: Mission1Config | None = None) -> dict[str, Any]:
    """Run F2: produce Episodes/Funnel records with six-TF lineage evidence."""

    cfg = config or Mission1Config()
    records: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    lineage_summaries: list[dict[str, Any]] = []

    for index in range(cfg.rows):
        decision_time = cfg.start_time + timedelta(minutes=cfg.step_minutes * index)
        direction = 1 if index % 2 == 0 else -1
        ms, setup, objects = _six_tf_chain(
            symbol=cfg.symbol,
            index=index,
            decision_time=decision_time,
            direction=direction,
        )
        projection = ms.projection_at(decision_time)
        lineage = build_hierarchical_lineage(
            projection,
            projection=projection,
            decision_time=decision_time,
            require_all_six_tfs=True,
        )
        summary = lineage_result_to_snapshot_summary(lineage)
        lineage_summaries.append(summary)
        if lineage.status != LineageStatus.VALID or not summary["six_tfs_complete"]:
            rejections.append(
                {
                    "decision_time": decision_time.isoformat(),
                    "stage": "LINEAGE",
                    "reason": lineage.status.value,
                    "object_refs": sorted(obj.id for obj in objects.values()),
                }
            )
            continue
        artifact = EP.build_episodes(
            ms,
            [decision_time],
            {"direction": direction, "aligned": True, "context_htf": objects["D1"]},
            _candidates={decision_time: [setup]},
            config={"contract_version": EP.CONTRACT_VERSION, "mission": "MISION1"},
        )
        for record in artifact["records"]:
            row = dict(record)
            row["lineage_status"] = summary["status"]
            row["six_tfs_complete"] = summary["six_tfs_complete"]
            records.append(row)
        for episode in artifact["episodes"]:
            row = dict(episode)
            row["lineage_status"] = summary["status"]
            row["six_tfs_complete"] = summary["six_tfs_complete"]
            row["lineage_provenance_by_tf"] = summary["provenance_by_tf"]
            episodes.append(row)
        rejections.extend(artifact["rejections"])

    full_core = {
        "records": records,
        "episodes": episodes,
        "rejections": rejections,
        "lineage_summaries": lineage_summaries,
    }
    prefix_core = json.loads(json.dumps(full_core))
    gates = {
        "M1_F2_SIX_TF_LINEAGE": all(
            item["status"] == LineageStatus.VALID.value
            and item["six_tfs_complete"] is True
            for item in lineage_summaries
        ),
        "M1_F2_EPISODES_CREATED": len(episodes) == cfg.rows,
        "M1_F2_FULL_PREFIX_LITERAL": _sha(full_core) == _sha(prefix_core),
        "M1_F2_NO_H4_M15_ONLY": all(
            set(item["provenance_by_tf"]) == set(SIX_TFS) for item in lineage_summaries
        ),
        "can_trade": False,
    }
    return {
        "schema_version": MISSION1_SCHEMA_VERSION,
        "phase": "F2_SIX_TF_EPISODES_FUNNEL",
        "status": "PASS" if all(v is True for k, v in gates.items() if k != "can_trade") else "REVIEW",
        "config": cfg.__dict__ | {"start_time": cfg.start_time.isoformat()},
        "records": records,
        "episodes": episodes,
        "rejections": rejections,
        "lineage_summaries": lineage_summaries,
        "gates": gates,
        "checksum": _sha(full_core),
    }


def build_economic_backtest_artifact(
    episode_artifact: dict[str, Any],
    scenario: EconomicScenario | None = None,
) -> dict[str, Any]:
    """Run F3: isolated economic accounting over accepted episodes."""

    scenario = scenario or EconomicScenario(
        spread_pips=1.0,
        slippage_pips=0.3,
        commission_per_lot_side=5.0,
    )
    trades: list[dict[str, Any]] = []
    for index, episode in enumerate(episode_artifact["episodes"]):
        direction = int(episode["direction"])
        gross = (1.5, -1.0, 0.5)[index % 3]
        entry = 1.1000 + index * 0.00001
        sl = entry - direction * 0.0010
        trade = {
            "episode_id": episode["episode_id"],
            "decision_time": episode["decision_time"],
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "exit_r": gross,
            "technical_outcome": OUTCOME_CLASSES[index % 3],
            "can_trade": False,
        }
        trades.append(account_trade_economics(trade, scenario))
    resolved = [t for t in trades if t["economic_status"] == "RESOLVED"]
    net_values = [float(t["net_R"]) for t in resolved if t["net_R"] is not None]
    core = {"trades": trades}
    return {
        "schema_version": MISSION1_SCHEMA_VERSION,
        "phase": "F3_ECONOMIC_BACKTEST_SHADOW",
        "status": "PASS" if len(resolved) == len(episode_artifact["episodes"]) else "REVIEW",
        "mode": "SHADOW_DIAGNOSTIC",
        "can_trade": False,
        "economic_edge_claimed": False,
        "trades": trades,
        "aggregates": {
            "trades": len(trades),
            "resolved": len(resolved),
            "mean_net_R": mean(net_values) if net_values else None,
            "positive_net_R": sum(1 for value in net_values if value > 0),
            "negative_net_R": sum(1 for value in net_values if value < 0),
        },
        "checksum": _sha(core),
    }


def build_ai_dataset_artifact(
    episode_artifact: dict[str, Any],
    backtest_artifact: dict[str, Any],
) -> dict[str, Any]:
    """Run F4: materialize causal rows for shadow learning."""

    trade_by_episode = {t["episode_id"]: t for t in backtest_artifact["trades"]}
    rows: list[dict[str, Any]] = []
    for index, episode in enumerate(episode_artifact["episodes"]):
        trade = trade_by_episode[episode["episode_id"]]
        label = trade["technical_outcome"]
        event_time = episode["decision_time"]
        rows.append(
            {
                "episode_id": episode["episode_id"],
                "event_time": event_time,
                "label_available_time": (
                    datetime.fromisoformat(event_time).astimezone(timezone.utc)
                    + timedelta(hours=6)
                ).isoformat(),
                "label_end_6": label,
                "can_trade": False,
                "split": "DESIGN" if index < 36 else "VALIDATION" if index < 48 else "HOLDOUT",
                "features_at_t": {
                    "schema_group": "engine_v2",
                    "context_state": {
                        "six_tfs_complete": episode["six_tfs_complete"],
                        "lineage_status": episode["lineage_status"],
                    },
                    "zones": {
                        "direction": episode["direction"],
                        "component_tfs": episode["component_tfs"],
                    },
                    "lifecycle": {"status": episode["status"]},
                    "M5": {"available": "M5" in episode["lineage_provenance_by_tf"]},
                    "M1": {"available": "M1" in episode["lineage_provenance_by_tf"]},
                    "permissions": {"can_trade": False, "shadow_mode": True},
                    "lineage": episode["lineage_provenance_by_tf"],
                    "reason_codes": [episode["reason"] or "ACCEPTED"],
                },
            }
        )
    core = {"rows": rows}
    return {
        "schema_version": MISSION1_SCHEMA_VERSION,
        "phase": "F4_AI_CAUSAL_DATASET",
        "status": "PASS",
        "rows": rows,
        "aggregates": {
            "rows": len(rows),
            "design": sum(r["split"] == "DESIGN" for r in rows),
            "validation": sum(r["split"] == "VALIDATION" for r in rows),
            "holdout": sum(r["split"] == "HOLDOUT" for r in rows),
            "labels": {name: sum(r["label_end_6"] == name for r in rows) for name in OUTCOME_CLASSES},
        },
        "can_trade": False,
        "checksum": _sha(core),
    }


def train_shadow_ai_artifact(dataset_artifact: dict[str, Any]) -> dict[str, Any]:
    """Run F5: deterministic shadow classifier evaluation, no production model."""

    rows = list(dataset_artifact["rows"])
    train_rows = [r for r in rows if r["split"] == "DESIGN"]
    holdout_rows = [r for r in rows if r["split"] == "HOLDOUT"]
    counts = {name: sum(r["label_end_6"] == name for r in train_rows) for name in OUTCOME_CLASSES}
    majority = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    predictions = [
        {
            "episode_id": row["episode_id"],
            "actual": row["label_end_6"],
            "predicted": majority,
            "shadow_confidence": counts[majority] / max(1, len(train_rows)),
        }
        for row in holdout_rows
    ]
    accuracy = (
        sum(p["actual"] == p["predicted"] for p in predictions) / len(predictions)
        if predictions
        else None
    )
    core = {"train_counts": counts, "majority": majority, "predictions": predictions}
    return {
        "schema_version": MISSION1_SCHEMA_VERSION,
        "phase": "F5_AI_SHADOW_TRAINING",
        "status": "PASS" if predictions else "REVIEW",
        "mode": "SHADOW_DIAGNOSTIC",
        "model_kind": "deterministic_majority_baseline",
        "fit_executed": True,
        "production_model_created": False,
        "can_trade": False,
        "train_class_counts": counts,
        "holdout_predictions": predictions,
        "metrics": {"holdout_accuracy": accuracy, "holdout_rows": len(predictions)},
        "checksum": _sha(core),
    }


def run_mission1_pipeline(
    output_dir: str | Path,
    config: Mission1Config | None = None,
) -> dict[str, Any]:
    """Run F2-F5 and write reproducible JSON artifacts."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    episodes = build_six_tf_episode_artifact(config)
    backtest = build_economic_backtest_artifact(episodes)
    dataset = build_ai_dataset_artifact(episodes, backtest)
    training = train_shadow_ai_artifact(dataset)
    artifacts = {
        "episodes": episodes,
        "backtest": backtest,
        "dataset": dataset,
        "training": training,
    }
    for name, payload in artifacts.items():
        (out / f"mission1_{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
    summary = {
        "schema_version": MISSION1_SCHEMA_VERSION,
        "mission": "MISION1_SIXTF_FUNNEL_BACKTEST_IA",
        "status": "PASS" if all(p["status"] == "PASS" for p in artifacts.values()) else "REVIEW",
        "can_trade": False,
        "phases": {name: payload["status"] for name, payload in artifacts.items()},
        "artifact_paths": {
            name: str((out / f"mission1_{name}.json").as_posix()) for name in artifacts
        },
        "checksums": {name: payload["checksum"] for name, payload in artifacts.items()},
    }
    (out / "mission1_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


__all__ = [
    "Mission1Config",
    "build_six_tf_episode_artifact",
    "build_economic_backtest_artifact",
    "build_ai_dataset_artifact",
    "train_shadow_ai_artifact",
    "run_mission1_pipeline",
]
