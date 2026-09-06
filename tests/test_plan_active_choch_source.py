import pandas as pd

from engine.plan import _bias_from_frame


def test_active_choch_uses_frame_columns_not_event_row_columns():
    frame = pd.DataFrame({
        "time": pd.to_datetime(["2026-08-01T00:00:00Z", "2026-08-01T01:00:00Z"]),
        "bos_dir": [0, 0], "bos_status": ["none", "none"],
        "bos_active_dir": [0, 0], "bos_active_source_bar": [-1, -1],
        "choch_active_dir": [0, 1], "choch_active_source_bar": [-1, 0],
    })
    assert _bias_from_frame(frame, frame["time"].iloc[-1]) == "BULLISH"
