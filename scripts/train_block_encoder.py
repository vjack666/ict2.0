"""Compatibility entrypoint.

Canonical implementation: scripts/lab/learning/train_block_encoder.py
"""
from pathlib import Path
import runpy

_TARGET = Path(__file__).resolve().parent / "lab" /  "learning" /  "train_block_encoder.py"

if __name__ == "__main__":
    runpy.run_path(str(_TARGET), run_name="__main__")
