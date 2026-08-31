from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.daily import brief_lunes
from scripts.daily.update_mt5_ict import write_parquet_atomic


def _write_feed(root: Path, symbol: str, tf: str, timestamp: str) -> None:
    path = root / symbol / f"{symbol}_{tf}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "time": [pd.Timestamp(timestamp, tz="UTC")],
            "open": [1.1],
            "high": [1.2],
            "low": [1.0],
            "close": [1.1],
        }
    ).to_parquet(path, index=False)


def test_closed_bar_cutoff_excludes_open_bar():
    asof = pd.Timestamp("2026-08-24 15:39", tz="UTC")

    assert brief_lunes.closed_bar_cutoff(asof, "M15") == pd.Timestamp("2026-08-24 15:15", tz="UTC")
    assert brief_lunes.closed_bar_cutoff(asof, "M5") == pd.Timestamp("2026-08-24 15:30", tz="UTC")
    assert brief_lunes.closed_bar_cutoff(asof, "M1") == pd.Timestamp("2026-08-24 15:38", tz="UTC")
    assert brief_lunes.closed_bar_cutoff(asof, "H1") == pd.Timestamp("2026-08-24 14:00", tz="UTC")
    assert brief_lunes.closed_bar_cutoff(asof, "H4") == pd.Timestamp("2026-08-24 08:00", tz="UTC")
    assert brief_lunes.closed_bar_cutoff(asof, "D1") == pd.Timestamp("2026-08-23", tz="UTC")


def test_load_raw_uses_only_closed_bars(tmp_path: Path):
    path = tmp_path / "EURUSD" / "EURUSD_M15.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2026-08-24 15:00", "2026-08-24 15:15", "2026-08-24 15:30"],
                utc=True,
            ),
            "open": [1.1, 1.1, 1.1],
            "high": [1.2, 1.2, 1.2],
            "low": [1.0, 1.0, 1.0],
            "close": [1.1, 1.1, 1.1],
        }
    ).to_parquet(path, index=False)

    frame, latest = brief_lunes.load_raw(
        "EURUSD",
        "M15",
        data_dir=tmp_path,
        asof_time=pd.Timestamp("2026-08-24 15:39", tz="UTC"),
    )

    assert latest == pd.Timestamp("2026-08-24 15:15", tz="UTC")
    assert frame["time"].max() == latest


def test_check_mt5_freshness_requires_every_closed_feed(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(brief_lunes, "ROOT_PATH", tmp_path)
    asof = pd.Timestamp("2026-08-24 15:39", tz="UTC")
    required = {
        "D1": "2026-08-23 00:00",
        "H4": "2026-08-24 08:00",
        "H1": "2026-08-24 14:00",
        "M15": "2026-08-24 15:15",
        "M5": "2026-08-24 15:35",
        "M1": "2026-08-24 15:39",
    }
    raw_root = tmp_path / "data" / "raw"
    for tf, timestamp in required.items():
        _write_feed(raw_root, "EURUSD", tf, timestamp)

    observed, errors = brief_lunes.check_mt5_freshness(("EURUSD",), tuple(required), asof)

    assert errors == []
    assert observed["EURUSD_M15"]["latest"] == "2026-08-24T15:15:00+00:00"
    assert observed["EURUSD_M5"]["latest"] == "2026-08-24T15:35:00+00:00"
    assert observed["EURUSD_M1"]["latest"] == "2026-08-24T15:39:00+00:00"


def test_refresh_fails_closed_when_mt5_subprocess_fails(monkeypatch):
    monkeypatch.setattr(brief_lunes, "SYSTEM_PY", Path(__file__))
    monkeypatch.setattr(brief_lunes, "MT5_UPDATER", Path(__file__))

    class Result:
        returncode = 3
        stdout = "[!] initialize failed"
        stderr = "terminal unavailable"

    monkeypatch.setattr(brief_lunes.subprocess, "run", lambda *args, **kwargs: Result())

    with pytest.raises(RuntimeError, match="Refresh MT5 falló"):
        brief_lunes.refresh_mt5_or_fail(
            ("EURUSD",),
            ("M15",),
            asof_time=pd.Timestamp("2026-08-24 15:39", tz="UTC"),
        )


def test_console_safe_handles_cp1252_replacement_character(monkeypatch):
    class Stdout:
        encoding = "cp1252"

    monkeypatch.setattr(brief_lunes.sys, "stdout", Stdout())
    safe = brief_lunes._console_safe("MT5 \ufffd conectado")
    assert "MT5" in safe
    assert "conectado" in safe


def test_update_mt5_writes_parquet_atomically(tmp_path: Path):
    path = tmp_path / "EURUSD" / "EURUSD_M1.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    old = pd.DataFrame({"time": pd.to_datetime(["2026-08-24 15:38"], utc=True), "close": [1.1]})
    new = pd.DataFrame({"time": pd.to_datetime(["2026-08-24 15:39"], utc=True), "close": [1.2]})
    old.to_parquet(path, index=False)

    write_parquet_atomic(path, new)

    result = pd.read_parquet(path)
    assert result.iloc[0]["close"] == 1.2
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))
