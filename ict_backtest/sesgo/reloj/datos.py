"""F0 — Cargador y validador del parquet M15 para el backtest del sesgo."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_M15_GLOB = "data/raw/*_M15.parquet"

REQUIRED_COLUMNS = {"open", "high", "low", "close"}
EXPECTED_STEP_MINUTES = 15


@dataclass(frozen=True)
class ValidatedM15:
    symbol: str
    timeframe: str
    tz: str
    df: pd.DataFrame
    path: Path
    sha256: str
    gaps: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _default_raw_root() -> Path:
    return REPO_ROOT / "data" / "raw"


def _normalize_index(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    if isinstance(df.index, pd.DatetimeIndex):
        index = df.index
    else:
        for col in ("timestamp", "time"):
            if col in df.columns:
                parsed = pd.to_datetime(df[col], utc=True, errors="coerce")
                if not parsed.isna().all():
                    df = df.set_index(parsed)
                    break

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(
                f"{path}: no datetime index or time-like column found"
            )

        index = df.index

    if not index.is_monotonic_increasing:
        raise ValueError(f"{path}: dataframe is not sorted by time")

    return df.sort_index()


def _load_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = _normalize_index(df, path)
    return df


def _detect_tz(df: pd.DataFrame) -> str:
    tz = getattr(df.index, "tz", None)
    if tz is None:
        return "UTC-naive"
    # datetime.timezone.utc / zoneinfo / pytz all stringify as their IANA name.
    return str(tz)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")


def _detect_time_gaps(df: pd.DataFrame) -> list[str]:
    if not isinstance(df.index, pd.DatetimeIndex):
        return []

    diffs = df.index.to_series().diff().dropna()
    expected = pd.Timedelta(minutes=EXPECTED_STEP_MINUTES)

    gap_mask = diffs > expected
    if not gap_mask.any():
        return []

    # Allow normal market closures: weekends and public holidays.
    # For FX we keep the strict 15-minute cadence during market hours;
    # anything longer than 24h is treated as a scheduled closure.
    intraday_mask = diffs <= pd.Timedelta(hours=24)
    suspicious_gaps = gap_mask & intraday_mask

    return [str(ts) for ts in diffs.index[suspicious_gaps][:20]]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_m15_parquet(symbol: str, raw_root: Path | None = None) -> ValidatedM15:
    raw_root = raw_root or _default_raw_root()
    path = Path(raw_root) / f"{symbol}_M15.parquet"
    if not path.exists():
        raise FileNotFoundError(f"M15 parquet not found: {path}")

    df = _load_parquet(path)
    _validate_required_columns(df)

    if df.index.duplicated().any():
        raise ValueError(f"{path}: duplicate timestamps detected")

    gaps = _detect_time_gaps(df)
    warnings: list[str] = []
    if gaps:
        warnings.append(f"suspicious time gaps detected: {gaps}")

    return ValidatedM15(
        symbol=symbol.upper(),
        timeframe="M15",
        tz=_detect_tz(df),
        df=df,
        path=path,
        sha256=_sha256(path),
        gaps=tuple(gaps),
        warnings=tuple(warnings),
    )
