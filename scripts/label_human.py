"""Compatibility entrypoint.

Canonical implementation: scripts/lab/learning/label_human.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "lab" /  "learning" /  "label_human.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
