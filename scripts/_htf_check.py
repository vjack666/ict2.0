"""Compatibility entrypoint.

Canonical implementation: scripts/smoke/_htf_check.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "smoke" /  "_htf_check.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
