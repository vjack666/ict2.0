"""Compatibility entrypoint.

Canonical implementation: scripts/smoke/smoke_consensus.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "smoke" /  "smoke_consensus.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
