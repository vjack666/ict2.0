"""Compatibility entrypoint.

Canonical implementation: scripts/smoke/verify_engine.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "smoke" /  "verify_engine.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
