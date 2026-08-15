"""engine.bos — CAPA 2 del motor ICT: Market Structure (BOS / CHOCH / MSS).

Después de que la capa 1 (`engine.bias`) definió el sesgo HTF, el motor
materializa la estructura de mercado: cuándo un BOS confirma la tendencia
vigente, cuándo un CHoCH avisa un giro, y cuándo un MSS (CHoCH + BOS de
confirmación) valida la reversión — SECUENCIA BOS -> CHoCH -> BOS.

Réplica fiel del canon `ict_backtest/market_structure.py`, pero SIN importar
nada del backtest (regla de separación motor <-> backtest): aquí vive la
decisión, allá solo la medición.

Ver contrato completo en `engine/bos/structure.py` y en `docs/ict/02_MSS_CHOCH.md`.
"""

from engine.bos.structure import (
    BEARISH,
    BULLISH,
    RANGING,
    MarketStructure,
    StructureConfig,
    detect_market_structure,
)

__all__ = [
    "BULLISH",
    "BEARISH",
    "RANGING",
    "StructureConfig",
    "MarketStructure",
    "detect_market_structure",
]
