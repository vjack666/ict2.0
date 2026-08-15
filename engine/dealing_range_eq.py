"""ict_backtest/dealing_range.py — Brecha C: dealing range premium/discount (Fase 5).

Tesis (libro 21 §0/§2, libro 08 PO3): un POI valido debe estar en la ZONA
CORRECTA del dealing range. EQ = 50% fib del swing HTF. discount (< EQ) para
long; premium (> EQ) para short; EQ central (~12% del rango) es ambiguo.

classify_zone marca la zona (no borra). zone_ok_for_direction dice si la zona
favorece la direccion del setup. EQ es ambiguo: no cuenta como bonificada pero
NO descarta la senal (BONUS, no filtro duro; libro 21 §4).
"""

from __future__ import annotations

_EQ_BAND = 0.12  # 12% del rango alrededor del EQ se considera ambiguo


def _eq(swing_high: float, swing_low: float) -> float:
    return (swing_high + swing_low) / 2.0


def classify_zone(
    zone_high: float,
    zone_low: float,
    swing_high: float,
    swing_low: float,
) -> str:
    """Clasifica la zona segun el dealing range del swing HTF.

    Usa el midpoint de la zona vs EQ (50% del swing). Devuelve
    'PREMIUM' | 'DISCOUNT' | 'EQ'.
    """
    if swing_high <= swing_low:
        raise ValueError("swing_high debe ser > swing_low")
    eq = _eq(swing_high, swing_low)
    rng = swing_high - swing_low
    band = rng * _EQ_BAND
    mid = (zone_high + zone_low) / 2.0
    if abs(mid - eq) <= band:
        return "EQ"
    return "DISCOUNT" if mid < eq else "PREMIUM"


def zone_ok_for_direction(zone_class: str, direction: int) -> bool:
    """Si la zona favorece la direccion del setup.

    long (1) quiere DISCOUNT; short (-1) quiere PREMIUM. EQ es ambiguo
    (no bonifica, no descarta).
    """
    if zone_class == "DISCOUNT":
        return direction == 1
    if zone_class == "PREMIUM":
        return direction == -1
    return False  # EQ ambiguo


from dataclasses import dataclass, field
from typing import Sequence, Tuple


@dataclass(frozen=True)
class DealingRangeInput:
    symbol: str
    htf_tf: str
    swing_high: float
    swing_low: float
    eq_band: float = _EQ_BAND
    meta: dict = field(default_factory=dict)

    @property
    def eq(self) -> float:
        return _eq(self.swing_high, self.swing_low)

    @property
    def rng(self) -> float:
        return self.swing_high - self.swing_low

    def classify(self, zone_high: float, zone_low: float) -> str:
        return classify_zone(zone_high, zone_low, self.swing_high, self.swing_low)

    def ok_for_direction(self, zone_class: str, direction: int) -> bool:
        return zone_ok_for_direction(zone_class, direction)


def _is_close_to(v: float, target: float, tol: float) -> bool:
    return abs(v - target) <= tol


def compute_zone_class(
    *,
    sig_dir: int,
    swing_high_htf: float | None,
    swing_low_htf: float | None,
    entry: float,
    zone_low: float | None = None,
    zone_high: float | None = None,
) -> str | None:
    """Devuelve la clase del deal range para la señal actual, o ``None``
    cuando no hay swing HTF válido (no hay dealing range que clasificar).

    - ``None``: swing ausente, parcial o inválido (high <= low).
    - ``"EQ"``: precio dentro de la banda ambigua (±12% del midpoint).
    - ``"DISCOUNT"`` / ``"PREMIUM"``: precio por debajo / encima de EQ.
    - Usa la zona FVG/OB del setup cuando está disponible; si no, usa entry.
    """
    if swing_high_htf is None or swing_low_htf is None:
        return None
    if swing_high_htf <= swing_low_htf:
        return None
    eq = _eq(swing_high_htf, swing_low_htf)
    rng = swing_high_htf - swing_low_htf
    price = entry
    if zone_high is not None and zone_low is not None:
        price = (zone_high + zone_low) / 2.0
    tol = _EQ_BAND * rng
    if _is_close_to(price, eq, tol):
        return "EQ"
    return "DISCOUNT" if price < eq else "PREMIUM"


def resolve_swing_from_ms(
    ms: dict[str, object],
    htf_tf: str,
    at_time: object,
) -> Tuple[float, float] | None:
    """Swing HTF cerrado antes de ``at_time``.

    Anti look-ahead: solo velas con ``time <= at_time``.
    Devuelve ``(high, low)`` o ``None`` cuando no hay datos suficientes.
    """
    df = ms.get(htf_tf)
    if df is None or len(df) == 0:
        return None
    try:
        import pandas as pd

        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        tt = pd.to_datetime(at_time, utc=True, errors="coerce")
        win = df.loc[times <= tt]
    except Exception:
        return None
    if len(win) < 3:
        return None
    return float(win["high"].max()), float(win["low"].min())
