from datetime import datetime, timezone

import pytest

from engine.killzone import killzone_en


UTC = timezone.utc


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        (datetime(2026, 1, 15, 7, 30, tzinfo=UTC), "London Open"),
        (datetime(2026, 7, 15, 7, 30, tzinfo=UTC), "London Open"),
        (datetime(2026, 1, 15, 15, 30, tzinfo=UTC), "New York AM"),
        (datetime(2026, 7, 15, 15, 30, tzinfo=UTC), "New York AM"),
        (datetime(2026, 1, 15, 19, 30, tzinfo=UTC), "New York PM"),
        (datetime(2026, 7, 15, 19, 30, tzinfo=UTC), "New York PM"),
    ],
)
def test_killzone_uses_one_dst_aware_utc_path(stamp, expected):
    assert killzone_en(stamp) == expected


def test_broker_time_is_normalized_before_the_same_killzone_evaluation():
    server_time = datetime(2026, 7, 15, 11, 30)
    assert killzone_en(server_time, broker_tz="America/New_York") == "New York AM"
