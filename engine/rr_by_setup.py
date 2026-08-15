"""engine/rr_by_setup.py — RR POR SETUP (C2, PERMANENTE).

Rescatado de ict_backtest/setups/rr_map.py. Unica fuente del motor; el backtest
LO CONSUME. Ley: engine/ NUNCA importa ict_backtest/. No depende de ICTSignal:
usa getattr defensivo para leer flags de setup (sb/turtle/ote) y setattr para
anotar rr_target. Asi funciona con el dataclass real o dobles ligeros de test.

Geometria: el RR es decision de diseno del setup traducida a nivel de precio
(tp = entry +/- rr*risk). Cero indicadores.
"""

from __future__ import annotations

from typing import Iterable, List, Optional


RR_BY_SETUP: dict[str, float] = {
    "silver_bullet": 2.0,   # 1:2
    "turtle_soup": 1.5,     # 1:1.5
    "ote": 3.0,             # 1:3
    "default": 3.0,         # PO3 y setups no reconocidos -> 1:3
}

_DEFAULT_SETUP = "default"


def rr_for(setup_name: Optional[str]) -> float:
    """RR objetivo del setup, o el default 3.0 si es None/desconocido."""
    if setup_name is None:
        return float(RR_BY_SETUP[_DEFAULT_SETUP])
    return float(RR_BY_SETUP.get(setup_name, RR_BY_SETUP[_DEFAULT_SETUP]))


def _setup_of(sig) -> str:
    """Resuelve el nombre del setup de una senal (precedencia SB > Turtle > OTE > default)."""
    sb = bool(getattr(sig, "sb_confirmed", False))
    turtle = bool(getattr(sig, "turtle_confirmed", False))
    ote = bool(getattr(sig, "ote_confirmed", False))
    if sb:
        return "silver_bullet"
    if turtle:
        return "turtle_soup"
    if ote:
        return "ote"
    return _DEFAULT_SETUP


def flag_rr(signals: Iterable) -> List:
    """Anota sig.rr_target en cada senal segun su setup detectado. Mutacion in-place."""
    sigs = signals if isinstance(signals, list) else list(signals)
    for sig in sigs:
        setup = _setup_of(sig)
        setattr(sig, "rr_target", rr_for(setup))
    return sigs
