"""Compatibility entrypoint.

Canonical implementation: scripts/data/import_forex_data.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "data" /  "import_forex_data.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
