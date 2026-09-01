"""Compatibility wrapper for the former HTF narrative module.

The implementation lives in ``engine.compat.htf_narrative``. The canonical
daily reading is ``engine.daily_motor`` + ``engine.mtf_navigation``; this
wrapper exists only to preserve existing imports and smoke scripts.
"""

from engine.compat.htf_narrative import build_htf_narrative, narrative_ready_for_trade

__all__ = ["build_htf_narrative", "narrative_ready_for_trade"]
