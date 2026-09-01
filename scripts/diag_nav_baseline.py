"""Compatibility entrypoint.

Canonical implementation: scripts/audit/diag_nav_baseline.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "audit" /  "diag_nav_baseline.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
