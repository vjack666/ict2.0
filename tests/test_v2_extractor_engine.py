import json

import pandas as pd
import pytest

from scripts.lab.experiments import v2_extractor_engine as extractor


def test_label_is_past_only_and_fails_without_horizon():
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2022-01-01", periods=3, freq="15min", tz="UTC"),
            "close": [1.1000, 1.1001, 1.1002],
        }
    )
    assert extractor._label(frame, 0, horizon=2) == ("continuation", frame.iloc[2].time.isoformat())
    assert extractor._label(frame, 1, horizon=2) == (None, None)


def test_features_are_diagnostic_and_never_emit_trade_levels():
    class State:
        def to_dict(self):
            return {
                "status": "OK",
                "constraints": {
                    "direction_hint": "BULLISH",
                    "allow_long": True,
                    "allow_short": False,
                    "notes": [],
                },
                "layers": {"H1": {"zones": [{"kind": "BSL"}]}},
            }

    payload = extractor._features(
        State(),
        {
            "M5": {"available": True, "bos_dir": 0, "momentum": 0},
            "M1": {"available": True, "bos_dir": 0, "momentum": 0},
        },
        1,
        3,
    )
    assert payload["schema_group"] == "engine_v2"
    assert payload["micro_confirmation"]["confirmed"] is False
    forbidden = {"sl", "tp", "entry", "stop_loss", "take_profit"}
    assert not forbidden.intersection(payload.keys())
    assert not forbidden.intersection(payload["zones"].keys())


def test_extract_fails_closed_when_a_canonical_timeframe_is_missing(tmp_path, monkeypatch):
    empty = {tf: pd.DataFrame() for tf in extractor.TIMEFRAMES}
    monkeypatch.setattr(extractor, "load_frames", lambda *args, **kwargs: empty)
    with pytest.raises(RuntimeError, match="MISSING_CANONICAL_TIMEFRAMES"):
        extractor.extract(
            "2022-01-02T00:00:00Z",
            "2022-01-02T23:59:59Z",
            tmp_path / "out.jsonl",
            tmp_path,
        )
