"""ict_backtest/setups/ote.py — Optimal Trade Entry (OTE) 62-79% Fib retrace.

Implementacion AISLADA de OTE (MDS_D1_OTE, SPEC §21, libro 15/23). NO edita
canonical.py / engine.py / sequence.py / poi_filter.py ni datos reales. Solo
LEE swings de un DataFrame de mercado y anota ICTSignal dinamicamente (setattr,
sin modificar engine.py).

OTE = entry en el RETRACE al 62%-79% de Fib de la pierna (swing) que precede
al setup. NO es "cualquier retorno a FVG": es el retrace profundo y concreto
de la pierna impulsiva previa.

  - Para LONG (pierna impulsiva low->high): el retrace se mide desde el
    swing_high hacia abajo -> [high - 0.786*r, high - 0.618*r].
  - Para SHORT (pierna impulsiva high->low): el retrace se mide desde el
    swing_low hacia arriba -> [low + 0.618*r, low + 0.786*r].

donde r = swing_high - swing_low (rango de la pierna).
"""
from __future__ import annotations

import pandas as pd

from engine.market_structure import detect_market_structure

# Niveles Fib canonicos OTE (ICT, libro 15/23).
OTE_FIB_LOW = 0.618
OTE_FIB_HIGH = 0.786


def ote_zone(swing_high: float, swing_low: float) -> tuple[float, float]:
    """Banda OTE (62-79% de retrace de la pierna) referenciada desde el high.

    Devuelve ``(ote_low, ote_high)`` = ``(swing_high - 0.786*r, swing_high -
    0.618*r)`` con ``r = swing_high - swing_low``. Para LONG es la zona OTE
    exacta (la pierna subio low->high y el retrace baja desde el high). Para
    SHORT usar la banda espejo (ver ``is_ote_entry`` / ``flag_ote``).
    """
    r = float(swing_high) - float(swing_low)
    ote_high = float(swing_high) - OTE_FIB_LOW * r
    ote_low = float(swing_high) - OTE_FIB_HIGH * r
    return ote_low, ote_high


def is_ote_entry(
    entry_price: float,
    swing_high: float,
    swing_low: float,
    direction: int,
) -> tuple[bool, dict]:
    """True si ``entry_price`` cae en la banda OTE de la pierna, segun ``direction``.

    LONG  (direction == +1): entry en [high - 0.786*r, high - 0.618*r].
    SHORT (direction == -1): entry en [low + 0.618*r, low + 0.786*r].

    Devuelve ``(confirmado, metadata)`` con la zona usada y el rango de la
    pierna. Si el rango no es positivo, devuelve ``(False, ...)`` sin inventar.
    """
    r = float(swing_high) - float(swing_low)
    if r <= 0:
        return False, {
            "ote_confirmed": False,
            "reason": "rango de pierna no positivo",
            "swing_high": float(swing_high),
            "swing_low": float(swing_low),
        }
    if direction == 1:
        ote_low = float(swing_high) - OTE_FIB_HIGH * r
        ote_high = float(swing_high) - OTE_FIB_LOW * r
    else:
        ote_low = float(swing_low) + OTE_FIB_LOW * r
        ote_high = float(swing_low) + OTE_FIB_HIGH * r
    confirmed = (ote_low <= float(entry_price) <= ote_high)
    meta = {
        "ote_confirmed": confirmed,
        "direction": int(direction),
        "swing_high": float(swing_high),
        "swing_low": float(swing_low),
        "ote_low": ote_low,
        "ote_high": ote_high,
        "entry_price": float(entry_price),
        "leg_range": r,
    }
    return confirmed, meta


def _swing_for_signal(sig, ltf_df: pd.DataFrame):
    """Extrae (swing_high, swing_low) del row de entry de ``sig``.

    Devuelve ``(None, None)`` si no hay indice valido o el swing no esta
    claro (NaN). No inventa swings.
    """
    if sig.entry_at is None:
        return None, None
    idx = int(sig.entry_at)
    if not (0 <= idx < len(ltf_df)):
        return None, None
    if "swing_high" not in ltf_df.columns or "swing_low" not in ltf_df.columns:
        return None, None
    row = ltf_df.iloc[idx]
    sh = row.get("swing_high")
    sl = row.get("swing_low")
    if pd.isna(sh) or pd.isna(sl):
        return None, None
    return float(sh), float(sl)


def flag_ote(signals, frames, ltf: str = "M15") -> list:
    """Anota ``ote_confirmed`` / ``ote_zone`` en cada ICTSignal leyendo el swing
    del row de entry en ``frames[ltf]``.

    NO edita engine.py: usa ``setattr`` dinamico sobre las senales (el
    dataclass ICTSignal no declara esos campos, pero Python los admite en
    runtime). Si ``frames[ltf]`` ya trae columnas ``swing_high``/``swing_low``
    (p.ej. un ``ms`` precomputado) las usa tal cual; si no, aplica
    ``detect_market_structure`` para obtenerlas. Sin swing claro en el row de
    entry -> ``ote_confirmed=False``, ``ote_zone=None`` (no inventa).

    Devuelve la misma lista de senales, anotadas in-place y devueltas.
    """
    if not signals:
        return list(signals)
    ltf_df = frames.get(ltf)
    if ltf_df is None:
        return list(signals)
    ltf_df = ltf_df.reset_index(drop=True)
    if "swing_high" not in ltf_df.columns or "swing_low" not in ltf_df.columns:
        ltf_df = detect_market_structure(ltf_df)

    out = []
    for sig in signals:
        sh, sl = _swing_for_signal(sig, ltf_df)
        if sh is None or sl is None:
            sig.ote_confirmed = False
            sig.ote_zone = None
            out.append(sig)
            continue
        confirmed, meta = is_ote_entry(sig.entry, sh, sl, sig.direction)
        # Zona OTE efectiva (por direction) que se anota como metadato.
        sig.ote_confirmed = confirmed
        sig.ote_zone = (meta["ote_low"], meta["ote_high"])
        out.append(sig)
    return out
