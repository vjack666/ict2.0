"""Compatibility entrypoint.

Canonical implementation: scripts/presentation/make_bos_chart.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "presentation" /  "make_bos_chart.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
