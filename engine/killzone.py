"""engine/killzone.py — Killzones ICT (PERMANENTE, B2).

Rescatado de ict_backtest/rules.py (que era duplicado del dashboard observador).
Unica fuente de verdad del motor. El backtest (ict_backtest/) LO CONSUME; nunca
al reves. Ley: engine/ NUNCA importa ict_backtest/.

Geometria de mercado + VOLUMEN (unico dato extra permitido, no indicador):
las bandas son puras horas del dia (UTC/ET via ZoneInfo, DST automatico).
El volumen es confirmacion OPCIONAL (no se fuerza): tick volume del bar para
saber si la ventana tuvo participacion real.

Regla de Ruben (2026-08-08): CERO indicadores tecnicos. Solo geometria + volumen.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional

from zoneinfo import ZoneInfo


# Bandas killzone en UTC canonico (convencion del proyecto / docs ict/01_KILLZONES).
# Clave -> (hora_ini, hora_fin) en horas decimales UTC.
KILLZONES_UTC: dict[str, tuple[float, float]] = {
    "Asia": (0.0, 3.0),
    "London Open": (7.0, 10.0),
    "New York AM": (12.5, 15.0),   # ~10-11 ET
    "New York PM": (15.0, 17.5),
    "London Close": (15.5, 17.5),
}

# Bandas killzone en ET FIJO (horario local del mentorship ICT). Se convierten a
# UTC POR DIA usando ZoneInfo('America/New_York') -> DST automatico. NUNCA offset fijo.
# Clave -> ((h_ini, m_ini), (h_fin, m_fin)) en ET local.
KILLZONES_ET: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "London Open": ((2, 0), (5, 0)),    # 02:00-05:00 ET  (London 07:00-10:00 UK)
    "New York AM": ((10, 0), (12, 0)),  # 10:00-12:00 ET  (Silver Bullet)
    "New York PM": ((14, 0), (17, 0)),  # 14:00-17:00 ET  (NY PM session)
}

# Etiqueta corta usada por detectors/killzones.py (pintar banda de fondo).
_KZ_ET_TO_SHORT = {
    "London Open": "LDN_OPEN",
    "New York AM": "NY_AM",
    "New York PM": "NY_PM",
}


def server_to_utc(ts: datetime, broker_tz) -> datetime:
    """Convierte hora del SERVIDOR (broker MT5) a UTC canonico del proyecto.

    PRINCIPIO DE RUBEN (DEC-009i): la hora la da el servidor (broker time); se
    CONVIERTE via ZoneInfo (DST automatico) a UTC. NUNCA offset fijo hardcodeado.
    """
    if isinstance(broker_tz, str):
        broker_tz = ZoneInfo(broker_tz)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=broker_tz)
    return ts.astimezone(timezone.utc)


def _et_band_to_utc(et_h: int, et_m: int, day_utc: datetime) -> datetime:
    """Convierte una hora ET fija del DIA de `day_utc` a su instante UTC real.

    Se ancla al dia UTC de la vela y se aplica el DST vigente ese dia via
    ZoneInfo('America/New_York'). Asi la ventana UTC correcta se calcula sin
    offset fijo.
    """
    ny = ZoneInfo("America/New_York")
    et_local = datetime(day_utc.year, day_utc.month, day_utc.day, et_h, et_m,
                        tzinfo=ny)
    return et_local.astimezone(timezone.utc)


def _killzone_en_utc(utc_ts: datetime) -> str:
    """Evalua las bandas KILLZONES_UTC (camino legacy, broker_tz=None)."""
    h = utc_ts.hour + utc_ts.minute / 60.0
    for nombre, (ini, fin) in KILLZONES_UTC.items():
        if ini <= h < fin:
            return nombre
    return ""


def killzone_en(ts: datetime, broker_tz: Optional[ZoneInfo | str] = None) -> str:
    """Killzone activa para un timestamp de vela. Backtest-safe.

    REGLA DE ZONA HORARIA (MDS_KILLZONES / DEC-009i):
    - Si `broker_tz` se pasa: PRIMERO server_to_utc (nunca evaluar sobre hora
      broker cruda). Luego se evalúan las bandas ICT definidas en ET fijo,
      convirtiendo ese ET a UTC POR DIA via ZoneInfo (DST automatico).
    - Si `broker_tz` es None: se asume que `ts` YA viene en UTC canonico (ruta
      legacy de canonical.py) y se evalúa contra KILLZONES_UTC.

    Devuelve 'London Open' | 'New York AM' | 'New York PM' | '' segun corresponda.
    """
    if broker_tz is not None:
        utc_ts = server_to_utc(ts, broker_tz)
        for nombre, ((h0, m0), (h1, m1)) in KILLZONES_ET.items():
            ini = _et_band_to_utc(h0, m0, utc_ts)
            fin = _et_band_to_utc(h1, m1, utc_ts)
            if ini <= utc_ts < fin:
                return nombre
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return _killzone_en_utc(ts)


def short_label(kz: str) -> str:
    """Etiqueta corta para pintar banda de fondo (detectors/killzones)."""
    return _KZ_ET_TO_SHORT.get(kz, kz)
