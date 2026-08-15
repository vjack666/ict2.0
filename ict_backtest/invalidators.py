"""ict_backtest/invalidators.py — Fase B1 (R10.C): predicados de invalidación semántica.

Funciones PURAS que reciben un MarketObject + contexto (velas CANDLE previas)
y devuelven True si un evento de mercado invalida/mitiga la estructura.

Decision POR RELACIÓN DE PRECIO / CONTEXTO. NUNCA por nº de velas ni
resta de índices. Cualquier umbral es derivable del precio (zona/swing), no
de un conteo temporal — ver cláusula de constantes en DISENO_R10C_R11.md.
"""
from __future__ import annotations

from typing import Sequence

from ict_backtest.market_object import MarketObject, ObjectType


def _last_close(ctx: Sequence[MarketObject]) -> float | None:
    for v in reversed(ctx):
        c = v.meta.get("close")
        if c is not None:
            return float(c)
    return None


def _min_close(ctx: Sequence[MarketObject]) -> float | None:
    closes = [float(v.meta["close"]) for v in ctx if v.meta.get("close") is not None]
    return min(closes) if closes else None


def _max_close(ctx: Sequence[MarketObject]) -> float | None:
    closes = [float(v.meta["close"]) for v in ctx if v.meta.get("close") is not None]
    return max(closes) if closes else None


def rompio_swing_que_defendia(obj: MarketObject, ctx: Sequence[MarketObject]) -> bool:
    """True si el precio cerró POR DEBAJO del swing que el BOS defendía.

    Relación de PRECIO pura: obj.meta["swing_defended"] vs cierre del contexto.
    Ningún conteo de velas.
    """
    swing = obj.meta.get("swing_defended")
    if swing is None:
        return False
    last = _last_close(ctx)
    if last is None:
        return False
    # BOS alcista defiende un swing basso: cerrar abajo lo invalida.
    if obj.direction >= 0:
        return last < float(swing)
    return last > float(swing)


def liquidez_tomada_sin_continuacion(obj: MarketObject, ctx: Sequence[MarketObject]) -> bool:
    """True si el precio tocó la zona (liquidez tomada) y NO hubo seguimiento.

    "Tocó la zona" = algún cierre dentro de [zone_low, zone_high].
    "Sin continuación" = el máximo cierre del contexto NO supera la zona por
    arriba (en BOS alcista). Relación de PRECIO, no de tiempo.
    """
    if obj.zone_low == 0.0 and obj.zone_high == 0.0:
        return False
    closes = [float(v.meta["close"]) for v in ctx if v.meta.get("close") is not None]
    if not closes:
        return False
    touched = any(obj.zone_low <= c <= obj.zone_high for c in closes)
    if not touched:
        return False
    if obj.direction >= 0:
        # Sin continuación alcista: el máximo cierre no pasa la zona alta.
        return max(closes) <= obj.zone_high
    return min(closes) >= obj.zone_low


def bos_opuesto_en_misma_narrativa(obj: MarketObject, graph) -> bool:
    """True si hay un BOS de dirección opuesta en la misma narrativa.

    Usa el grafo (duck-typed): `graph.opuesto_en(obj)` devuelve el BOS
    opuesto o None. NUNCA mira índices ni nº de velas. La navegación
    por relaciones es responsabilidad del ObjectGraph (Fase C); aquí solo
    se consulta.
    """
    opuesto = graph.opuesto_en(obj)
    if opuesto is None:
        return False
    return opuesto.type == ObjectType.BOS and opuesto.direction != obj.direction
