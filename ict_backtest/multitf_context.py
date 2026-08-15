"""ict_backtest/multitf_context.py — SHIM de compatibilidad (B1).

La infraestructura MultiTFContext es ahora la FUENTE UNICA del motor y
vive en ``engine.multitf_context`` (que delega en engine.plan). Este modulo
SOLO re-exporta para no romper a los importadores existentes. Cero logica
duplicada.
"""

from engine.multitf_context import (  # noqa: F401 — el motor es la fuente
    MultiTFContext,
    build_multitf_context,
    extract_htf_layer,
)

__all__ = [
    "MultiTFContext",
    "build_multitf_context",
    "extract_htf_layer",
]
