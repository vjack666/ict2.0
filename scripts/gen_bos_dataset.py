"""Compatibility entrypoint.

Canonical implementation: scripts/data/gen_bos_dataset.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "data" /  "gen_bos_dataset.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
