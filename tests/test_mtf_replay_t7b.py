from audits.codigo.mtf_replay_t7b import _state_and_context
from audits.codigo.mtf_replay_t7 import derive_h4
import pandas as pd


def _m15(periods=640):
    times = pd.date_range("2025-01-01T00:15:00Z", periods=periods, freq="15min")
    rows = []
    value = 1.10
    for i, timestamp in enumerate(times):
        step = (0.0018 if (i // 24) % 2 == 0 else -0.0018) + (0.006 if i % 79 == 0 else 0)
        opened, closed = value, value + step
        rows.append({"time": timestamp, "open": opened, "high": max(opened, closed) + 0.0004,
                     "low": min(opened, closed) - 0.0004, "close": closed, "volume": 100.0})
        value = closed
    return pd.DataFrame(rows)


def test_t7b_context_uses_latest_published_bos_only():
    m15 = _m15(640)
    _, context, population = _state_and_context({"M15": m15, "H4": derive_h4(m15)})
    bos = [obj for obj in population["objects"] if obj.type.value == "BOS"]
    if bos:
        assert context(bos[0].tradable_time)["direction"] == bos[0].direction
