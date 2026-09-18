#!/usr/bin/env python3
"""Cleanup consolidado de caches locales sin efectos secundarios al importar."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CACHES = [
    ROOT / ".pytest_cache",
    ROOT / "tests" / ".pytest_cache",
    ROOT / "scripts" / ".pytest_cache",
]


def main() -> int:
    for cache in CACHES:
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
            print(f"removed: {cache}")
    print("cleanup_done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
