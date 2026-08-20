"""Compatibility entrypoint.

Canonical implementation: scripts/audit/grok_run_funnel_20y_full.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "audit" /  "grok_run_funnel_20y_full.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
