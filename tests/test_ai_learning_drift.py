from __future__ import annotations

import json

import pytest

from runtime.ai_learning.drift import (
    DriftError,
    DriftStatus,
    DriftThresholds,
    KnownDomain,
    analyze_drift,
    build_known_domain,
)


def _reference() -> list[dict]:
    return [
        {"symbol": "EURUSD", "tf": "H1", "regime": "trend", "period": "2024-Q1", "f1": 0.0, "f2": "low", "label": 0},
        {"symbol": "EURUSD", "tf": "H1", "regime": "trend", "period": "2024-Q1", "f1": 1.0, "f2": "low", "label": 0},
        {"symbol": "GBPUSD", "tf": "M15", "regime": "range", "period": "2024-Q2", "f1": 2.0, "f2": "high", "label": 1},
        {"symbol": "GBPUSD", "tf": "M15", "regime": "range", "period": "2024-Q2", "f1": 3.0, "f2": "high", "label": 1},
    ]


def test_known_domain_is_frozen_and_has_stable_identity():
    thresholds = DriftThresholds(warning=0.05, abstain=0.20)
    first = build_known_domain(_reference(), ["f1", "f2"], label_names=["label"], thresholds=thresholds, source_id="certified-001")
    second = KnownDomain.from_reference(_reference(), ["f1", "f2"], label_names=["label"], thresholds=thresholds, source_id="certified-001")

    assert first == second
    assert first.domain_id == second.domain_id
    assert first.to_dict()["thresholds"] == thresholds.to_dict()
    with pytest.raises(AttributeError):
        first.source_id = "changed"  # type: ignore[misc]


def test_identical_observations_are_normal_and_report_is_reproducible():
    domain = build_known_domain(_reference(), ["f1", "f2"], label_names=["label"])
    first = analyze_drift(domain, _reference())
    second = analyze_drift(domain, list(reversed(_reference())))

    assert first.status == DriftStatus.NORMAL
    assert first.report_id == second.report_id
    assert first.to_json() == second.to_json()
    assert len(first.groups) == 1 + 4 * 2  # global plus each present dimension value
    assert all(metric.status == DriftStatus.NORMAL for metric in first.groups[0].feature_metrics)
    assert first.groups[0].label_metrics[0].variable_type == "label"


def test_feature_drift_reaches_abstain_and_is_reported_by_all_scopes():
    domain = build_known_domain(
        _reference(), ["f1", "f2"], thresholds={"warning": 0.05, "abstain": 0.20}
    )
    observed = [
        {"symbol": "EURUSD", "tf": "H1", "regime": "trend", "period": "2024-Q3", "f1": 100.0, "f2": "new"},
        {"symbol": "EURUSD", "tf": "H1", "regime": "trend", "period": "2024-Q3", "f1": 101.0, "f2": "new"},
    ]
    report = analyze_drift(domain, observed)

    assert report.status == DriftStatus.ABSTAIN
    assert any(group.scope_dict == {"symbol": "EURUSD"} and group.status == DriftStatus.ABSTAIN for group in report.groups)
    global_f1 = report.groups[0].feature_metrics[0]
    assert global_f1.status == DriftStatus.ABSTAIN
    assert global_f1.drift_score >= domain.thresholds.abstain


def test_label_drift_is_optional_and_missing_labels_do_not_change_feature_result():
    domain = build_known_domain(_reference(), ["f1"], label_names=["label"])
    observed = [{"symbol": "EURUSD", "f1": 0.0}, {"symbol": "EURUSD", "f1": 1.0}]

    report = analyze_drift(domain, observed)
    assert report.groups[0].label_metrics == ()
    symbol_group = next(group for group in report.groups if group.scope_dict == {"symbol": "EURUSD"})
    assert symbol_group.feature_metrics[0].status == DriftStatus.NORMAL


def test_label_drift_is_measured_when_labels_are_present():
    domain = build_known_domain(_reference(), ["f1"], label_names=["label"])
    observed = [
        {"symbol": "EURUSD", "f1": 0.0, "label": 1},
        {"symbol": "EURUSD", "f1": 1.0, "label": 1},
        {"symbol": "GBPUSD", "f1": 2.0, "label": 1},
        {"symbol": "GBPUSD", "f1": 3.0, "label": 1},
    ]

    report = analyze_drift(domain, observed)
    label_metric = report.groups[0].label_metrics[0]
    assert label_metric.variable_type == "label"
    assert label_metric.status == DriftStatus.ABSTAIN


def test_threshold_override_requires_exact_frozen_values_and_no_recalibration():
    domain = build_known_domain(_reference(), ["f1"], thresholds=DriftThresholds(warning=0.1, abstain=0.3))
    with pytest.raises(DriftError, match="congelados"):
        analyze_drift(domain, _reference(), thresholds={"warning": 0.01, "abstain": 0.02})
    assert domain.thresholds == DriftThresholds(warning=0.1, abstain=0.3)


def test_metrics_are_available_by_symbol_tf_regime_and_period():
    domain = build_known_domain(_reference(), ["f1"])
    report = analyze_drift(domain, _reference())
    scopes = {tuple(group.scope_dict) for group in report.groups}
    assert ("symbol",) in scopes
    assert ("tf",) in scopes
    assert ("regime",) in scopes
    assert ("period",) in scopes
    assert json.loads(report.to_json())["report_id"] == report.report_id


def test_empty_oos_data_abstains_without_mutating_domain():
    domain = build_known_domain(_reference(), ["f1"])
    before = domain.to_dict()
    report = analyze_drift(domain, [])
    assert report.status == DriftStatus.ABSTAIN
    assert report.groups[0].row_count == 0
    assert domain.to_dict() == before
