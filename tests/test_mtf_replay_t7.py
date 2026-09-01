from pathlib import Path

import pandas as pd

from audits.codigo.mtf_replay_t7 import derive_h4


def test_derive_h4_is_closed_only_and_uses_utc_boundaries():
    opened = pd.date_range("2025-01-02T00:00:00Z", periods=16, freq="15min")
    frame = pd.DataFrame({
        "time": opened + pd.Timedelta(minutes=15),
        "open": range(16), "high": [value + 2 for value in range(16)],
        "low": [value - 1 for value in range(16)], "close": [value + 1 for value in range(16)],
        "volume": [1.0] * 16,
    })
    result = derive_h4(frame)
    assert len(result) == 1
    assert result.iloc[0]["time"] == pd.Timestamp("2025-01-02T04:00:00Z")
    assert result.iloc[0]["open"] == 0
    assert result.iloc[0]["close"] == 16
    assert result.iloc[0]["count"] == 16

