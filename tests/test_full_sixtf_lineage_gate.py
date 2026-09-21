from __future__ import annotations

import pandas as pd

from scripts.audit.verify_full_sixtf_lineage_gate import run_checks


DURATION = {
    "D1": pd.Timedelta(days=1),
    "H4": pd.Timedelta(hours=4),
    "H1": pd.Timedelta(hours=1),
    "M15": pd.Timedelta(minutes=15),
    "M5": pd.Timedelta(minutes=5),
    "M1": pd.Timedelta(minutes=1),
}


def _frames(t: pd.Timestamp) -> dict[str, pd.DataFrame]:
    # Open times chosen so the first row is the real last-closed geometry of
    # control B; a second future row proves the builder excludes open/future bars.
    opens = {
        "D1": pd.Timestamp("2026-08-21T00:00:00Z"),
        "H4": pd.Timestamp("2026-08-24T16:00:00Z"),
        "H1": pd.Timestamp("2026-08-24T19:00:00Z"),
        "M15": pd.Timestamp("2026-08-24T20:15:00Z"),
        "M5": pd.Timestamp("2026-08-24T20:30:00Z"),
        "M1": pd.Timestamp("2026-08-24T20:34:00Z"),
    }
    out = {}
    for tf, first in opens.items():
        out[tf] = pd.DataFrame(
            {
                "time": [first, t],
                "open": [1.10, 1.10],
                "high": [1.11, 1.11],
                "low": [1.09, 1.09],
                "close": [1.105, 1.106],
            }
        )
    return out


def test_full_six_tf_gate_reproducible_control_geometry():
    t = pd.Timestamp("2026-08-24T20:35:00Z")
    result = run_checks(_frames(t), t)

    assert result["all_pass"] is True
    assert result["full"]["valid"] is True
    assert result["prefix"]["valid"] is True
    assert result["full_prefix_identical"] is True
    assert result["save_load_roundtrip"] is True
    assert all(result["edge_fail_closed"].values())
    assert all(result["missing_tf_fail_closed"].values())
    assert result["future_object_rejected"] is True

    closes = {
        tf: layer["close_time"]
        for tf, layer in result["full_layers"].items()
    }
    assert closes == {
        "D1": "2026-08-22T00:00:00+00:00",
        "H4": "2026-08-24T20:00:00+00:00",
        "H1": "2026-08-24T20:00:00+00:00",
        "M15": "2026-08-24T20:30:00+00:00",
        "M5": "2026-08-24T20:35:00+00:00",
        "M1": "2026-08-24T20:35:00+00:00",
    }
