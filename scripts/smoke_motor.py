"""Compatibility entrypoint.

Canonical implementation: scripts/smoke/smoke_motor.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "smoke" /  "smoke_motor.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
