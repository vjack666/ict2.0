"""engine.bias — CAPA 1 del motor ICT: Narrativa HTF (SPEC §1).

Lo primero que hace un trader profesional humano después de que el motor cargó
las barras: definir el sesgo del día desde los TF mayores (D1/H4/H1).

Ver contrato completo en `engine/bias/narrative.py` y en
`docs/ict/SPEC_TESIS_FORMAL.md` §1 (Narrativa HTF).
"""

from engine.bias.narrative import (
    BEARISH,
    BULLISH,
    NEUTRAL,
    HtfBias,
    compute_htf_bias,
    compute_htf_bias_series,
)

__all__ = [
    "BULLISH",
    "BEARISH",
    "NEUTRAL",
    "HtfBias",
    "compute_htf_bias",
    "compute_htf_bias_series",
]
