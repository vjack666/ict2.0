#!/usr/bin/env python3
"""Cleanup consolidado: __pycache__, .pytest_cache, mapeo de bloqueos residuales de path bugs."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CACHES = [
    ROOT / ".pytest_cache",
    ROOT / "tests" / ".pytest_cache",
    ROOT / "scripts" / ".pytest_cache",
]

for c in CACHES:
    if c.exists():
        shutil.rmtree(c, ignore_errors=True)
        print(f"removed: {c}")

print("cleanup_done")
