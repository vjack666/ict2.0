"""Fronteras contractuales de B1-O1; no carga ni modifica datos de mercado."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parent.parents[1]s[1]
SCRIPT = ROOT / "scripts" / "b1_extract_corpus_v2.py"
SPEC = importlib.util.spec_from_file_location("b1_extract_corpus_v2", SCRIPT)
assert SPEC and SPEC.loader
b1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b1)


def test_b1_uses_the_immutable_design_m15_artifact() -> None:
    assert b1.M15_DESIGN.name == "EURUSD_M15_2006_2015.parquet"
    assert b1.M15_DESIGN != b1.M15_FRAME


def test_epoch_milliseconds_are_not_misread_as_1970_nanoseconds() -> None:
    normalized = b1.normalize_b1_time_column(pd.Series([1136073600000]))
    assert str(normalized.iloc[0]) == "2006-01-01 00:00:00+00:00"


def test_h4_derivation_is_in_memory_and_labels_the_bar_at_close() -> None:
    frame = pd.DataFrame({
        "timestamp": [1136073600000, 1136074500000, 1136075400000, 1136076300000],
        "open": [1.0, 1.1, 1.2, 1.3], "high": [1.2, 1.3, 1.4, 1.5],
        "low": [0.9, 1.0, 1.1, 1.2], "close": [1.1, 1.2, 1.3, 1.4],
        "volume": [1, 2, 3, 4],
    })
    h4 = b1.derive_h4_from_design_m15(frame)
    assert len(h4) == 2
    assert str(h4.loc[1, "time"]) == "2006-01-01 04:00:00+00:00"


@pytest.mark.parametrize(
    ("timestamp", "allowed"),
    [
        ("2005-12-31T23:59:59Z", False),
        ("2006-01-01T00:00:00Z", True),
        ("2015-12-31T23:59:59Z", True),
        ("2016-01-01T00:00:00Z", False),
        ("2020-12-31T23:59:59Z", False),
        ("2021-01-01T00:00:00Z", False),
    ],
)
def test_design_frontier_is_half_open_and_excludes_holdout(timestamp: str, allowed: bool) -> None:
    assert b1.is_design_time(pd.Timestamp(timestamp)) is allowed


@pytest.mark.parametrize("timestamp", ["2016-01-01T00:00:00Z", "2021-01-01T00:00:00Z"])
def test_outside_design_fails_closed_before_evaluation(timestamp: str) -> None:
    with pytest.raises(ValueError, match="DESIGN_ONLY violation"):
        b1.assert_design_time(timestamp)


def test_selector_never_returns_validation_or_holdout() -> None:
    selected = b1.select_design_decision_times(
        pd.Series(pd.to_datetime([
            "2015-12-31T23:45:00Z",
            "2016-01-01T00:00:00Z",
            "2021-01-01T00:00:00Z",
        ], utc=True))
    )
    assert selected.astype(str).tolist() == ["2015-12-31 23:45:00+00:00"]
    assert all(value < b1.HOLDOUT_START for value in selected)
