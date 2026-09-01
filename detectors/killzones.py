"""Killzones — port de LuxAlgo ICT Concepts a Python.

Sesiones (horario del exchange del símbolo, igual que TradingView time()):
  London Open   : 02:00-05:00 ET  (London 07:00-10:00 UK)
  New York AM   : 10:00-12:00 ET  (Silver Bullet)
  New York PM   : 14:00-17:00 ET
  Asian         : 10:00-14:00 Asia/Tokyo

Agrega columna 'kz' con etiqueta de sesion activa por vela (para pintar banda de
fondo).

PRINCIPIO DE ZONA HORARIA (MDS_KILLZONES / DEC-009i, bug KZ-2): la hora la da el
SERVIDOR (broker MT5). Se CONVIERTE a UTC canónico via ZoneInfo (DST automático)
y recién ahí se evalúan las bandas ICT. NUNCA offset fijo hardcodeado. Si no se
pasa broker_tz se asume que `time` YA está en UTC (convención del proyecto).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from engine.killzone import server_to_utc, _et_band_to_utc

# (nombre_corto, et_ini, et_fin) en horas/min ET locales del mentorship ICT.
# Se convierten a UTC POR DIA via ZoneInfo('America/New_York') -> DST automático.
# 'ASIA' usa Asia/Tokyo (sin DST) convertido igual por ZoneInfo.
SESSIONS = [
    ("LDN_OPEN", (2, 0), (5, 0)),
    ("NY_AM", (10, 0), (12, 0)),
    ("NY_PM", (14, 0), (17, 0)),
    ("ASIA", (10, 0), (14, 0)),
]

_TOKYO = ZoneInfo("Asia/Tokyo")


def _session_window_utc(name: str, h0: int, h1: int,
                        day_utc: datetime) -> tuple[datetime, datetime]:
    """Devuelve (ini_utc, fin_utc) de la sesión para el dia de la vela, vía ZoneInfo.

    ET (DST-aware por día) para LDN_OPEN/NY_AM/NY_PM; Tokyo para ASIA.
    """
    if name == "ASIA":
        ini = datetime(day_utc.year, day_utc.month, day_utc.day, h0, 0,
                       tzinfo=_TOKYO).astimezone(timezone.utc)
        fin = datetime(day_utc.year, day_utc.month, day_utc.day, h1, 0,
                       tzinfo=_TOKYO).astimezone(timezone.utc)
        return ini, fin
    return _et_band_to_utc(h0, 0, day_utc), _et_band_to_utc(h1, 0, day_utc)


def detect_killzones(df: pd.DataFrame, broker_tz=None) -> pd.DataFrame:
    """Marca sesiones activas por vela.

    broker_tz: ZoneInfo | str (nombre IANA) del servidor (broker MT5). Si se da,
    convierte server->UTC via ZoneInfo (DST) y evalúa en UTC canónico. Si None,
    asume que `time` ya viene en UTC (convención proyecto).
    """
    out = df.copy()
    out["kz"] = ""

    t = pd.to_datetime(out["time"])
    if broker_tz is not None:
        utc_times = t.map(lambda x: server_to_utc(
            datetime(x.year, x.month, x.day, x.hour, x.minute, x.second),
            broker_tz))
    else:
        utc_times = (t.dt.tz_localize("UTC")
                     if t.dt.tz is None else t.dt.tz_convert("UTC"))

    for name, (h0, _m0), (h1, _m1) in SESSIONS:
        mask = pd.Series(False, index=out.index)
        for i in out.index:
            utc_dt = utc_times.iloc[i].to_pydatetime()
            ini, fin = _session_window_utc(name, h0, h1, utc_dt)
            if ini <= utc_dt < fin:
                mask.iloc[i] = True
        out.loc[mask, "kz"] = out.loc[mask, "kz"].astype(str) + (name + " ")

    out["kz"] = out["kz"].str.strip()
    return out
