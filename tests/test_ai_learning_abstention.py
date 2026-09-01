from __future__ import annotations

import json

from runtime.ai_learning.abstention import (
    ACCEPT,
    ABSTAIN,
    REVIEW,
    AbstentionPolicy,
    ReasonCode,
    evaluate_abstention,
)


def test_accept_is_advisory_and_has_deterministic_audit_record():
    first = evaluate_abstention(
        {"swing": 1.0, "liquidity": 0.4},
        0.90,
        True,
        required_features=["liquidity", "swing"],
    )
    second = evaluate_abstention(
        {"liquidity": 0.4, "swing": 1.0},
        0.90,
        True,
        required_features=["liquidity", "swing"],
    )

    assert first.state is ACCEPT
    assert first.reasons == (ReasonCode.ACCEPTED_WITHIN_POLICY,)
    assert first.audit_id == second.audit_id
    assert "buy" not in json.dumps(first.to_dict()).lower()
    assert "sell" not in json.dumps(first.to_dict()).lower()


def test_review_band_is_distinct_from_abstention():
    result = evaluate_abstention(
        {"swing": 1.0}, 0.65, True, required_features=["swing"]
    )

    assert result.state is REVIEW
    assert result.reasons == (ReasonCode.REVIEW_REQUIRED,)
    assert not result.abstained


def test_missing_features_abstain_and_report_sorted_contract_order():
    result = evaluate_abstention(
        {"swing": 1.0},
        0.99,
        True,
        required_features=["swing", "bos", "liquidity"],
    )

    assert result.state is ABSTAIN
    assert result.reasons == (ReasonCode.MISSING_FEATURES,)
    assert result.missing_features == ("bos", "liquidity")


def test_low_confidence_abstains():
    result = evaluate_abstention(
        {"swing": 1.0}, 0.49, True, required_features=["swing"]
    )

    assert result.state is ABSTAIN
    assert result.reasons == (ReasonCode.LOW_CONFIDENCE,)


def test_out_of_domain_abstains_even_with_high_confidence():
    result = evaluate_abstention(
        {"swing": 1.0}, 1.0, False, required_features=["swing"]
    )

    assert result.state is ABSTAIN
    assert result.reasons == (ReasonCode.OUT_OF_DOMAIN,)


def test_unknown_domain_is_fail_closed():
    result = evaluate_abstention(
        {"swing": 1.0}, 0.99, None, required_features=["swing"]
    )

    assert result.state is ABSTAIN
    assert result.reasons == (ReasonCode.DOMAIN_UNCERTAIN,)


def test_multiple_abstention_reasons_are_stable_and_auditable():
    result = evaluate_abstention(
        {}, 0.10, False, required_features=["swing", "liquidity"]
    )

    assert result.state is ABSTAIN
    assert result.reasons == (
        ReasonCode.MISSING_FEATURES,
        ReasonCode.OUT_OF_DOMAIN,
        ReasonCode.LOW_CONFIDENCE,
    )
    assert result.to_dict()["reasons"] == [
        "MISSING_FEATURES",
        "OUT_OF_DOMAIN",
        "LOW_CONFIDENCE",
    ]


def test_invalid_inputs_fail_closed_without_throwing():
    cases = [
        ({"swing": 1.0}, float("nan"), True),
        ({"swing": float("inf")}, 0.9, True),
        ({"swing": 1.0}, 0.9, "unknown"),
        (None, 0.9, True),
    ]

    for features, confidence, domain in cases:
        result = evaluate_abstention(
            features, confidence, domain, required_features=["swing"]
        )
        assert result.state is ABSTAIN
        assert result.reasons == (ReasonCode.INVALID_INPUT,)


def test_invalid_policy_configuration_fails_closed():
    result = evaluate_abstention(
        {"swing": 1.0},
        0.90,
        True,
        required_features=["swing"],
        review_threshold=0.90,
        accept_threshold=0.80,
    )

    assert result.state is ABSTAIN
    assert result.reasons == (ReasonCode.INVALID_INPUT,)


def test_policy_is_deterministic_and_rejects_invalid_thresholds():
    policy = AbstentionPolicy(review_threshold=0.4, accept_threshold=0.7)
    result = policy.evaluate(
        {"swing": 1.0}, 0.7, True, required_features=["swing"]
    )
    assert result.state is ACCEPT
    assert result.audit_id == policy.evaluate(
        {"swing": 1.0}, 0.7, True, required_features=["swing"]
    ).audit_id
