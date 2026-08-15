"""Compatibility shim for the canonical market-structure engine.

The live BOS/CHOCH ontology is ``engine.bos.structure``.  This module remains
as a stable DataFrame-returning facade for legacy consumers that still import
``engine.market_structure``; it contains no second detector or decision path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.bos.structure import (
    BEARISH,
    BULLISH,
    RANGING,
    MarketStructure,
    StructureConfig,
    detect_market_structure as _canonical_detect_market_structure,
)

__all__ = [
    "BEARISH",
    "BULLISH",
    "RANGING",
    "MarketStructure",
    "StructureConfig",
    "detect_market_structure",
]


def detect_market_structure(
    frame: pd.DataFrame,
    config: StructureConfig | None = None,
) -> pd.DataFrame:
    """Return the canonical structure frame through the legacy facade.

    New engine code should import ``engine.bos.detect_market_structure`` and
    receive ``MarketStructure``.  Older consumers expect the annotated frame;
    returning ``.frame`` preserves that API without preserving a duplicate
    implementation.  ``structure_label`` is a non-decision compatibility
    alias retained for historical reports and tests.
    """
    source = frame.copy()
    # Historical OHLC fixtures sometimes omit ``open``.  The canonical SDD
    # requires it for body geometry; close-as-open is a compatibility fallback
    # that makes those fixtures neutral rather than inventing displacement.
    if "open" not in source.columns and "close" in source.columns:
        source["open"] = source["close"]
    result = _canonical_detect_market_structure(source, config)
    out = result.frame.copy()
    if "structure_label" not in out.columns:
        out["structure_label"] = np.select(
            [out["bos_dir"] != 0, out["choch_dir"] != 0],
            ["BOS", "CHOCH"],
            default="NONE",
        )
    return out
