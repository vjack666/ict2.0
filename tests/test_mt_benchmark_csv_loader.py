"""test_mt_benchmark_csv_loader.py — Tests del adaptador de carga CSV del benchmark.

Plan SDD_EPISODES_FUNNEL_V1.md §10.2 / §10.4:
- UTC y vela cerrada (bar_close_time <= T).
- M5 conflictivo: M5_3m es la fuente RECENT; M5_20y queda fuera del perfil RECENT.
- Duplicados: H1 == H1_20y byte-idénticos; el perfil RECENT usa H1.csv.
- No look-ahead: el filtro closed-only nunca expone velas con close > T.
- 1971/1972 fuera del universo EURUSD literal: D1/H4 no se certifican como transables.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from scripts.lab.experiments.mt_benchmark_csv_loader import (
    SOURCE_PROFILE_RECENT,
    closed_only,
    load_selected_frames,
    normalize_time_semantics,
)

UTC = timezone.utc
MANIFEST = "benchmark/eurusd_multitf/BENCHMARK_DATA_MANIFEST.json"

CONTROL_A = datetime(2026, 9, 17, 18, 20, tzinfo=UTC)
CONTROL_B = datetime(2026, 8, 24, 20, 35, tzinfo=UTC)
WINDOW_START = datetime(2026, 6, 18, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 17, 23, 59, tzinfo=UTC)


def test_profile_recent_uses_m5_3m():
    """Plan §10.4.2: M5 para CONTROL A/B es EURUSD_M5_3m.csv, no M5_20y ni M5.csv."""
    assert SOURCE_PROFILE_RECENT["M5"] == "EURUSD_M5_3m.csv"
    assert SOURCE_PROFILE_RECENT["M1"] == "EURUSD_M1.csv"


def test_load_control_a_closed_only():
    """CONTROL A: todos los TF cargan velas cerradas <= 18:20Z; M1 queda vacío (OUT_OF_RANGE)."""
    frames, meta = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("D1", "H4", "H1", "M15", "M5", "M1"),
        decision_time=CONTROL_A,
        source_profile="RECENT",
    )
    for tf in ("D1", "H4", "H1", "M15", "M5"):
        assert len(frames[tf]) > 0, f"{tf} vacío en CONTROL A"
        assert frames[tf]["time"].max() <= pd.Timestamp(CONTROL_A)
    # M1 termina 2026-08-24 => OUT_OF_RANGE en CONTROL A, no MISSING_DATA.
    assert len(frames["M1"]) == 0
    assert meta["coverage"]["M1"]["status"] == "OUT_OF_RANGE"
    assert meta["last_close"]["M1"] is not None


def test_load_control_b_m1_in_range():
    """CONTROL B: M1 tiene velas cerradas <= 20:35Z (última vela 20:34)."""
    frames, meta = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("D1", "H4", "H1", "M15", "M5", "M1"),
        decision_time=CONTROL_B,
        source_profile="RECENT",
    )
    assert len(frames["M1"]) > 0
    assert frames["M1"]["time"].max() <= pd.Timestamp(CONTROL_B)


def test_time_semantics_open_to_close():
    """time = apertura; bar_close_time = open de la vela siguiente (interior)."""
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2026-09-17 18:10:00+00:00", "2026-09-17 18:15:00+00:00",
                 "2026-09-17 18:20:00+00:00"],
                utc=True,
            ),
            "open": [1.14842, 1.14828, 1.14847],
            "high": [1.14846, 1.14848, 1.14848],
            "low": [1.14819, 1.14819, 1.14815],
            "close": [1.14828, 1.14847, 1.14815],
        }
    )
    out = normalize_time_semantics(df, "M5")
    assert out["bar_open_time"].iloc[0] == pd.Timestamp("2026-09-17 18:10:00+00:00")
    assert out["time"].iloc[0] == pd.Timestamp("2026-09-17 18:15:00+00:00")
    assert out["time"].iloc[1] == pd.Timestamp("2026-09-17 18:20:00+00:00")
    # Última vela: open + duración TF.
    assert out["time"].iloc[2] == pd.Timestamp("2026-09-17 18:25:00+00:00")


def test_no_lookahead_m5_close_matches_gpt():
    """Evidencia P0: la vela M5 que abre 18:15 cierra en 1.14847 = 'M5 close' GPT 18:20."""
    frames, _ = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("M5",),
        decision_time=CONTROL_A,
        source_profile="RECENT",
    )
    m5 = frames["M5"]
    last = m5.iloc[-1]
    # Con semántica close_time, la última vela cerrada <= 18:20 es la que abre 18:15
    # y cierra 18:20; su close es 1.14847 (coincide con el control GPT).
    assert last["time"] == pd.Timestamp("2026-09-17 18:20:00+00:00")
    assert last["bar_open_time"] == pd.Timestamp("2026-09-17 18:15:00+00:00")
    assert abs(float(last["close"]) - 1.14847) < 1e-5


def test_duplicate_h1_sources_rejected_in_profile():
    """H1 y H1_20y son byte-idénticos; el perfil RECENT usa H1.csv (no H1_20y)."""
    assert SOURCE_PROFILE_RECENT["H1"] == "EURUSD_H1.csv"
    assert "H1_20y" not in SOURCE_PROFILE_RECENT.values()


def test_historical_profile_keeps_m5_20y():
    """M5_20y queda disponible solo en el perfil HISTORICAL (estudio separado)."""
    from scripts.lab.experiments.mt_benchmark_csv_loader import SOURCE_PROFILE_HISTORICAL

    assert SOURCE_PROFILE_HISTORICAL["M5"] == "EURUSD_M5_20y.csv"


def test_closed_only_filter():
    """closed_only() nunca expone velas con close > T."""
    frames, _ = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("M15",),
        decision_time=CONTROL_A,
        source_profile="RECENT",
    )
    filtered = closed_only(frames, CONTROL_A)
    assert filtered["M15"]["time"].max() <= pd.Timestamp(CONTROL_A)


def test_pre_2000_data_not_certified():
    """D1 desde 1971 y H4 desde 1972 no se certifican como EURUSD transable literal."""
    frames, meta = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("D1", "H4"),
        decision_time=CONTROL_A,
        source_profile="RECENT",
    )
    # La ventana RECENT solo expone velas 2026; el manifiesto documenta el origen 1971/1972.
    assert frames["D1"]["time"].min() >= pd.Timestamp(WINDOW_START)
    assert frames["H4"]["time"].min() >= pd.Timestamp(WINDOW_START)
    assert meta["sources"]["D1"] == "EURUSD_D1.csv"
    assert meta["sources"]["H4"] == "EURUSD_H4.csv"


def test_mutate_future_hook_only_touches_future():
    """FUTURE INJECTION: el hook muta SOLO barras con close > T; el prefijo queda intacto."""

    def _mutate(df: pd.DataFrame, T: pd.Timestamp) -> pd.DataFrame:
        out = df.copy()
        mask = out["time"] > T
        out.loc[mask, "close"] = out.loc[mask, "close"] * 1.10
        return out

    frames, _ = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("M5",),
        decision_time=CONTROL_B,
        source_profile="RECENT",
        mutate_future=_mutate,
    )
    # El prefijo <= T no debe haber cambiado: recargar sin hook y comparar.
    clean, _ = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("M5",),
        decision_time=CONTROL_B,
        source_profile="RECENT",
    )
    pd.testing.assert_frame_equal(frames["M5"], clean["M5"])


def test_rejected_m5_csv_not_loadable_in_recent():
    """M5_20y (perfil HISTORICAL) no cubre CONTROL A: termina 2025-12-31 => OUT_OF_RANGE."""
    frames, meta = load_selected_frames(
        MANIFEST,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        selected_tfs=("M5",),
        decision_time=CONTROL_A,
        source_profile="HISTORICAL",
    )
    assert len(frames["M5"]) == 0
    assert meta["coverage"]["M5"]["status"] == "OUT_OF_RANGE"