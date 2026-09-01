"""Compatibility entrypoint.

Canonical implementation: scripts/lab/learning/train_choch_full.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "lab" /  "learning" /  "train_choch_full.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
