"""Compatibility entrypoint.

Canonical implementation: scripts/presentation/plot_tradingview_zones.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "presentation" /  "plot_tradingview_zones.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
