"""engine/silver_bullet.py — Silver Bullet (C2, PERMANENTE).

Rescatado de ict_backtest/setups/silver_bullet.py. Unica fuente de decision del
motor; el backtest LO CONSUME. Ley: engine/ NUNCA importa ict_backtest/.

Geometria pura (sin indicadores): Silver Bullet = retorno a una zona (FVG/OB)
DENTRO de una killzone 'limpia' tras un barrido (sweep) de liquidez reciente.
Solo opera en London Open / New York AM. El volumen es confirmacion OPCIONAL
(no se fuerza): tick volume del retorno para saber si hubo participacion.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

import pandas as pd

from engine._volume import volume_confirm as _volume_confirm


# Killzones validas para Silver Bullet. Se mapea 'London Open' -> 'L'.
_SB_KILLZONES = {
    "London Open": "L",
    "New York AM": "NY_AM",
}


def _to_ts(value: Any) -> Optional[datetime]:
    """Normaliza un timestamp (datetime / string) a datetime tz-aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        ts = ts.to_pydatetime()
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=__import__("datetime").timezone.utc)
    return ts


def is_silver_bullet(
    sweep_ts: Any,
    return_ts: Any,
    direction: int,
    killzone_fn: Callable[[datetime], str],
) -> tuple[bool, dict]:
    """Decide si sweep+retorno constituyen un Silver Bullet valido.

    Requisitos:
      1. sweep_ts y return_ts caen en la MISMA killzone SB (London Open o NY AM).
      2. return_ts >= sweep_ts (el retorno es posterior al barrido).

    Args:
        sweep_ts, return_ts: timestamp del barrido / retorno (datetime/str).
        direction: +1 long / -1 short (se propaga, no veta).
        killzone_fn: killzone_en(ts) -> str (de engine.killzone).

    Returns:
        (True, meta) / (False, meta). meta={'sb_killzone','direction','sweep_kz','return_kz'}.
    """
    sweep = _to_ts(sweep_ts)
    ret = _to_ts(return_ts)
    if sweep is None or ret is None:
        return False, {"sb_killzone": None, "direction": direction,
                       "sweep_kz": None, "return_kz": None}
    if ret < sweep:
        return False, {"sb_killzone": None, "direction": direction,
                       "sweep_kz": killzone_fn(sweep), "return_kz": killzone_fn(ret)}
    sweep_kz = killzone_fn(sweep)
    return_kz = killzone_fn(ret)
    sb_sweep = _SB_KILLZONES.get(sweep_kz)
    sb_return = _SB_KILLZONES.get(return_kz)
    if sb_sweep is not None and sb_sweep == sb_return:
        return True, {"sb_killzone": sb_sweep, "direction": direction,
                      "sweep_kz": sweep_kz, "return_kz": return_kz}
    return False, {"sb_killzone": None, "direction": direction,
                   "sweep_kz": sweep_kz, "return_kz": return_kz}


def volume_confirm(df: pd.DataFrame, idx: int, window: int = 20) -> Optional[float]:
    """Confirmacion OPCIONAL por volumen (unico dato extra permitido, no indicador).

    Devuelve el ratio volumen[vela] / media(volumen ventana previa). None si no
    hay columna 'volume'. Ratio > 1 = participacion por encima de la media.
    NO es senal direccional ni indicador suavizado; es dato crudo de mercado.

    DRY (MDS_VOLUMEN): delega en `engine._volume.volume_confirm`, unica fuente.
    """
    return _volume_confirm(df, idx, window)


def flag_silver_bullet(
    signals: list,
    frames: Any = None,
    killzone_fn: Callable[[datetime], str] | None = None,
    *,
    hard_filter: bool = False,
) -> list:
    """Anota sb_confirmed / sb_killzone en cada senal (atributos dinamicos).

    No filtra duro por defecto (Brecha D): solo anota. hard_filter=True devuelve
    solo las confirmadas. `frames` = DataFrame LTF con columna 'time'.
    """
    from engine.killzone import killzone_en as _default_kz

    kz_fn = killzone_fn or _default_kz
    ltf_df = frames if isinstance(frames, pd.DataFrame) else None
    out: list = []
    for sig in signals:
        sweep_ts = None
        return_ts = None
        if ltf_df is not None:
            sa = getattr(sig, "sweep_at", None)
            ea = getattr(sig, "entry_at", None)
            if sa is not None and 0 <= int(sa) < len(ltf_df):
                sweep_ts = ltf_df.iloc[int(sa)]["time"]
            if ea is not None and 0 <= int(ea) < len(ltf_df):
                return_ts = ltf_df.iloc[int(ea)]["time"]
        ok, meta = is_silver_bullet(
            sweep_ts, return_ts, int(getattr(sig, "direction", 0) or 0), kz_fn,
        )
        sig.sb_confirmed = bool(ok)
        sig.sb_killzone = meta["sb_killzone"]
        if hard_filter and not ok:
            continue
        out.append(sig)
    return out
