"""Compatibility entrypoint.

Canonical implementation: scripts/daily/update_mt5_ict.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "daily" /  "update_mt5_ict.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
