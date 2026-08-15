"""ict_backtest/market_object.py — SHIM de compatibilidad (B1).

El objeto de mercado ICT es ahora la FUENTE UNICA del motor y vive en
``engine.market_object``. Este modulo SOLO re-exporta para no romper a los
~40 importadores (backtest, scripts, tests). Cero logica duplicada.

Regla de capa (tesis 18 / ontologia): el POI institucional SOLO existe en
HTF (D1/H4/H1). Un FVG/OB de M15 es siempre REFINEMENT.
"""

from engine.market_object import (  # noqa: F401 — el motor es la fuente
    ObjectType,
    ObjectState,
    Role,
    MarketObject,
)

__all__ = [
    "ObjectType",
    "Role",
    "ObjectState",
    "MarketObject",
]
