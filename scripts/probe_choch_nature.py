"""Compatibility entrypoint.

Canonical implementation: scripts/lab/learning/probe_choch_nature.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "lab" /  "learning" /  "probe_choch_nature.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
