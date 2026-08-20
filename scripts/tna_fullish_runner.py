"""Compatibility entrypoint.

Canonical implementation: scripts/audit/tna_fullish_runner.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "audit" /  "tna_fullish_runner.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
