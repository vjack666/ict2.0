"""Compatibility entrypoint.

Canonical implementation: scripts/presentation/plot_htf_reading.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "presentation" /  "plot_htf_reading.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
