"""Compatibility entrypoint.

Canonical implementation: scripts/daily/brief_lunes.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "daily" /  "brief_lunes.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
