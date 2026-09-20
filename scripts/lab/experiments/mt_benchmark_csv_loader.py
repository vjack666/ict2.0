"""mt_benchmark_csv_loader.py — Adaptador aislado de carga CSV para el benchmark multi-TF.

Plan SDD_EPISODES_FUNNEL_V1.md §10.2 / §10.3 / §10.4.

Semántica temporal (verificada en P0, 2026-09-19):
- Los CSV del paquete EURUSD.zip usan ``time`` = APERTURA de vela (convención MT5).
  Evidencia: la vela M5 con timestamp 2026-09-17T18:15:00Z cierra en 1.14847, que es
  exactamente el "M5 close ~1.14847" del control GPT a las 18:20Z. Si ``time`` fuera
  cierre, la vela 18:15 cubriría 18:10→18:15 (close 1.14828) y no coincidiría.
- El motor (MarketState.advance_bar / lifecycle.evaluate) opera con velas CERRADAS cuyo
  ``time`` es el instante de CIERRE (plan §10.6.2: {"time": close_time, ...}).
- Este loader normaliza internamente: ``bar_close_time`` = open de la vela siguiente
  (interior de la serie) u open + duración de TF (última vela). Nunca modifica el CSV
  original. La vela siguiente como cierre maneja gaps/DST sin sumar duraciones a ciegas.

Selección de fuentes (plan §10.4.2 — por perfil temporal, NO por mayor número de años):
- RECENT (CONTROL A/B y ventana 2026-06-18 → 2026-09-17):
  D1→EURUSD_D1.csv, H4→EURUSD_H4.csv, H1→EURUSD_H1.csv, M15→EURUSD_M15.csv,
  M5→EURUSD_M5_3m.csv, M1→EURUSD_M1.csv.
- HISTORICAL (estudio separado): M5→EURUSD_M5_20y.csv (termina 2025-12-31).
- EURUSD_M5.csv queda REJECTED (conflicto OHLC con M5_20y y M5_3m). Prohibido concatenar.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping

import pandas as pd

# Duración nominal por TF (segundos). Solo se usa para la ÚLTIMA vela de cada serie;
# el interior usa el open de la vela siguiente (maneja gaps y DST).
TF_DURATION_SECONDS: dict[str, int] = {
    "D1": 86400,
    "H4": 14400,
    "H1": 3600,
    "M15": 900,
    "M5": 300,
    "M3": 180,
    "M1": 60,
}

# Perfiles de selección de fuentes (plan §10.4.2).
SOURCE_PROFILE_RECENT: dict[str, str] = {
    "D1": "EURUSD_D1.csv",
    "H4": "EURUSD_H4.csv",
    "H1": "EURUSD_H1.csv",
    "M15": "EURUSD_M15.csv",
    "M5": "EURUSD_M5_3m.csv",
    "M1": "EURUSD_M1.csv",
}
SOURCE_PROFILE_HISTORICAL: dict[str, str] = {
    "M5": "EURUSD_M5_20y.csv",
}

_OHLC_COLS = ["open", "high", "low", "close"]
_EXTRA_COLS = ["tick_volume", "spread"]


def _as_utc(value) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True, errors="coerce")


def _load_csv(path: Path) -> pd.DataFrame:
    """Carga un CSV del paquete sin tocar el archivo original."""
    df = pd.read_csv(path)
    if "time" not in df.columns:
        raise ValueError(f"{path.name}: columna 'time' ausente")
    df["time"] = _as_utc(df["time"])
    if df["time"].isna().any():
        raise ValueError(f"{path.name}: timestamps inválidos (NaT) presentes")
    df = df.sort_values("time").reset_index(drop=True)
    return df


def normalize_time_semantics(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Convierte ``time`` (apertura) a close_time y conserva bar_open_time.

    bar_close_time = open de la vela siguiente (interior) u open + duración (última).
    Devuelve un DataFrame con columnas: time (=close), bar_open_time, OHLC y extras.
    """
    if tf not in TF_DURATION_SECONDS:
        raise ValueError(f"TF no soportado: {tf}")
    out = df.copy()
    out["bar_open_time"] = out["time"]
    close = out["time"].shift(-1)
    last_idx = out.index[-1]
    close.iloc[last_idx] = out["time"].iloc[last_idx] + timedelta(
        seconds=TF_DURATION_SECONDS[tf]
    )
    out["time"] = close
    return out


def _source_for(manifest: Mapping, tf: str, source_profile: str) -> str:
    if source_profile == "RECENT":
        profile = SOURCE_PROFILE_RECENT
    elif source_profile == "HISTORICAL":
        profile = SOURCE_PROFILE_HISTORICAL
    else:
        raise ValueError(f"source_profile desconocido: {source_profile}")
    if tf not in profile:
        raise ValueError(
            f"TF {tf} no definido en perfil {source_profile}; "
            f"disponibles: {sorted(profile)}"
        )
    return profile[tf]


def load_selected_frames(
    manifest_path: Path | str,
    *,
    window_start: datetime,
    window_end: datetime,
    selected_tfs: tuple[str, ...],
    decision_time: datetime | None = None,
    source_profile: str = "RECENT",
    mutate_future: Callable[[pd.DataFrame, pd.Timestamp], pd.DataFrame] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Carga los frames seleccionados del manifiesto con semántica close_time.

    - ``window_start``/``window_end``: ventana causal de interés (filtro de lectura).
    - ``decision_time``: si se pasa, filtra closed-only con bar_close_time <= T.
    - ``mutate_future``: hook para FUTURE INJECTION (rama B); recibe el frame completo
      con time=close y debe mutar SOLO barras con bar_close_time > decision_time.
    - Devuelve (frames, meta) donde frames[tf] tiene time=close_time y bar_open_time.
    """
    manifest_path = Path(manifest_path)
    with manifest_path.open("r", encoding="utf-8-sig") as fh:
        manifest = json.load(fh)
    root = manifest_path.parent / "EURUSD"
    if not root.exists():
        raise FileNotFoundError(f"Directorio de CSV no encontrado: {root}")

    frames: dict[str, pd.DataFrame] = {}
    meta: dict = {
        "source_profile": source_profile,
        "sources": {},
        "rows": {},
        "coverage": {},
    }
    ws = _as_utc(window_start)
    we = _as_utc(window_end)
    dt = _as_utc(decision_time) if decision_time is not None else None

    for tf in selected_tfs:
        filename = _source_for(manifest, tf, source_profile)
        path = root / filename
        if not path.exists():
            raise FileNotFoundError(f"CSV faltante: {path}")
        df = _load_csv(path)
        df = normalize_time_semantics(df, tf)
        if mutate_future is not None and dt is not None:
            df = mutate_future(df, dt)
        # Cobertura: la fuente cubre T si su última vela cerrada (serie completa) >= T - duración.
        last_close_full = df["time"].iloc[-1] if len(df) else None
        out_of_range = (
            dt is not None
            and last_close_full is not None
            and last_close_full < dt - timedelta(seconds=TF_DURATION_SECONDS[tf])
        )
        # Filtro de lectura por ventana (causal: solo velas cerradas dentro de la ventana).
        df = df[(df["time"] > ws) & (df["time"] <= we)].copy()
        if out_of_range:
            meta["coverage"][tf] = {
                "status": "OUT_OF_RANGE",
                "last_close": str(last_close_full),
                "decision_time": str(dt),
            }
            frames[tf] = df.iloc[0:0].copy()
            meta["sources"][tf] = filename
            meta["rows"][tf] = 0
            meta.setdefault("last_close", {})[tf] = str(last_close_full)
            meta.setdefault("first_close", {})[tf] = None
            continue
        if dt is not None:
            df = df[df["time"] <= dt].copy()
        df = df.reset_index(drop=True)
        frames[tf] = df
        meta["sources"][tf] = filename
        meta["rows"][tf] = int(len(df))
        meta["coverage"][tf] = {"status": "IN_RANGE"}
        if len(df):
            meta.setdefault("last_close", {})[tf] = str(df["time"].iloc[-1])
            meta.setdefault("first_close", {})[tf] = str(df["time"].iloc[0])
        else:
            meta.setdefault("last_close", {})[tf] = None
            meta.setdefault("first_close", {})[tf] = None

    return frames, meta


def closed_only(frames: Mapping[str, pd.DataFrame], T: datetime) -> dict[str, pd.DataFrame]:
    """Filtro closed-only explícito: bar_close_time <= T en cada TF."""
    tt = _as_utc(T)
    return {tf: df[df["time"] <= tt].reset_index(drop=True) for tf, df in frames.items()}