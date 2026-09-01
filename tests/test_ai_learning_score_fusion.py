import pytest

from runtime.ai_learning.score_fusion import (
    CallableScoreSource,
    OOSContractError,
    ScoreCompatibilityError,
    ScoreDataset,
    ScoreObservation,
    ScoreFusionWeights,
    TrainingDataError,
    WeightValidationError,
    evaluate_offline_oos,
    fit_baseline,
    fit_score_fusion,
    register_score_fusion_weights,
    score_pair,
)


def _row(sample_id, split, ict, wyckoff, label, *, feature_names=("f1",)):
    return ScoreObservation(
        sample_id=sample_id,
        split=split,
        ict_score=ict,
        wyckoff_score=wyckoff,
        label=label,
        features={name: 1.0 for name in feature_names},
    )


def _dataset(oos_label=0.8):
    return ScoreDataset(
        rows=(
            _row("train-1", "TRAIN", 1.0, 0.0, 1.0),
            _row("train-2", "TRAIN", 0.0, 1.0, 0.0),
            _row("train-3", "TRAIN", 0.9, 0.1, 0.9),
            _row("oos-1", "OOS", 0.8, 0.2, oos_label),
        ),
        features=("f1",),
        labels=("label",),
    )


def test_ict_and_wyckoff_share_one_score_source_interface():
    ict = CallableScoreSource("ICT", lambda features: features["f1"])
    wyckoff = CallableScoreSource("WYCKOFF", lambda features: 1.0 - features["f1"])

    pair = score_pair({"f1": 0.75}, ict=ict, wyckoff=wyckoff)

    assert pair.to_dict() == {"ict": 0.75, "wyckoff": 0.25}


def test_weights_are_learned_from_train_only_and_are_deterministic():
    first = fit_score_fusion(_dataset(oos_label=0.0))
    second = fit_score_fusion(_dataset(oos_label=1.0))

    assert first.to_dict() == second.to_dict()
    assert first.weights.trained_on_split == "TRAIN"
    assert first.weights.train_sample_ids == ("train-1", "train-2", "train-3")
    assert first.weights.weight_ict == pytest.approx(1.0)
    assert first.weights.weight_wyckoff == pytest.approx(0.0)


def test_baseline_is_separate_and_is_learned_from_train():
    baseline = fit_baseline(_dataset(oos_label=99.0))

    assert baseline.value == pytest.approx((1.0 + 0.0 + 0.9) / 3.0)
    assert baseline.trained_on_split == "TRAIN"
    assert baseline.train_sample_ids == ("train-1", "train-2", "train-3")


def test_registered_weights_round_trip_and_oos_evaluation_are_pure():
    model = fit_score_fusion(_dataset())
    registered = register_score_fusion_weights(model.to_dict())
    restored = type(model)(registered)
    result = evaluate_offline_oos(
        restored, _dataset().rows[-1:], baseline=fit_baseline(_dataset())
    )

    assert result.sample_ids == ("oos-1",)
    assert result.fused_predictions == pytest.approx((0.8,))
    assert result.baseline_predictions == pytest.approx(((1.0 + 0.0 + 0.9) / 3.0,))
    assert result.fused_mse == pytest.approx(0.0)


def test_oos_evaluation_rejects_train_rows_and_never_refits():
    model = fit_score_fusion(_dataset())

    with pytest.raises(OOSContractError, match="TRAIN"):
        evaluate_offline_oos(model, _dataset().rows[:2])


def test_features_and_labels_must_match_exactly():
    model = fit_score_fusion(_dataset())
    incompatible = _row("oos-2", "OOS", 0.5, 0.5, 0.5, feature_names=("other",))

    with pytest.raises(ScoreCompatibilityError, match="features"):
        model.predict(incompatible)


def test_invalid_or_oos_registered_weights_are_rejected():
    model = fit_score_fusion(_dataset())
    payload = model.to_dict()
    payload["weight_ict"] = 0.4
    payload["weight_wyckoff"] = 0.4
    with pytest.raises(WeightValidationError, match="sumar 1"):
        register_score_fusion_weights(payload)

    payload = model.to_dict()
    payload["trained_on_split"] = "OOS"
    with pytest.raises(WeightValidationError, match="TRAIN"):
        register_score_fusion_weights(payload)


def test_unidentifiable_train_data_is_rejected_instead_of_using_arbitrary_weights():
    rows = (
        _row("train-1", "TRAIN", 0.5, 0.5, 0.0),
        _row("train-2", "TRAIN", 0.5, 0.5, 1.0),
        _row("oos-1", "OOS", 0.2, 0.8, 0.4),
    )
    with pytest.raises(TrainingDataError, match="identifica pesos"):
        fit_score_fusion(rows)
