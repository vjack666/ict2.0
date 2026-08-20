"""Compatibility entrypoint.

Canonical implementation: scripts/lab/experiments/exp_sequence_x_context_state.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "lab" /  "experiments" /  "exp_sequence_x_context_state.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
