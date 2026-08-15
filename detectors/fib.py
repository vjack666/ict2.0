"""
Fibonacci levels — port de LuxAlgo ICT Concepts a Python.

Dados dos precios y1 (origen) / y2 (fin), calcula los niveles de retorno/extension:
0.236, 0.382, 0.500, 0.618, 0.786, 1.000, 1.618 (sobre la diferencia df = y2 - y1).
Usado para pintar sobre el ultimo FVG / OB / Liq en el mapa.
"""
from __future__ import annotations

from typing import Dict

LEVELS = [0.236, 0.382, 0.500, 0.618, 0.786, 1.000, 1.618]


def fib_levels(y0: float, y1: float) -> Dict[float, float]:
    """Devuelve {nivel: precio} entre y0 (0.0) e y1 (1.0)."""
    df = y1 - y0
    return {lvl: y0 + df * lvl for lvl in LEVELS}
