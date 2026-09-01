"""SUITE FINAL MTF/LTF (Objetivo 11 — auditoría de regresiones).

Ejecuta todas las pruebas de la misión MTF/LTF y reporta el veredicto global.
Cada prueba es independiente (importa y corre main()).

No envía órdenes. OBSERVE_ONLY.
"""

from __future__ import annotations
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULES = [
    "tests.test_mtf_premium_discount_provenance",  # Obj 1
    "tests.test_mtf_zero_lookahead",               # Obj 2
    "tests.test_validate_mtf_ltf_intraday",        # Obj 3,5,8
    "tests.test_ahf_gates",                        # Obj 4
    "tests.test_ltf_m5_m1_structure",              # Obj 6,9
    "tests.test_mtf_historical_regression",        # Obj 10
]


def main() -> int:
    results = {}
    for mod in MODULES:
        try:
            m = importlib.import_module(mod)
            rc = m.main()
            results[mod] = rc
        except Exception as exc:  # noqa: BLE001
            results[mod] = f"EXC:{exc}"
        print("-" * 60)

    print("\n=== SUITE FINAL MTF/LTF ===")
    all_pass = True
    for mod, rc in results.items():
        ok = rc == 0
        all_pass = all_pass and ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {mod} -> {rc}")
    print("=" * 60)
    print(f"VEREDICTO GLOBAL: {'PASS' if all_pass else 'PARTIAL/BLOCKED'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
