"""Guardas estructurales del repositorio.

Este archivo no decide semántica de mercado. Evita que una reorganización
vuelva a introducir módulos retirados, rutas documentales normativas duplicadas
o entrypoints fuera de sus carpetas clasificadas.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "engine/daily_motor.py",
    "engine/mtf_navigation.py",
    "engine/ahf.py",
    "engine/sequential_events.py",
    "engine/lineage.py",
    "engine/Wyckoff/__init__.py",
    "engine/compat/htf_narrative.py",
    "engine/htf_narrative.py",
    "docs/contratos/CONTRATO_CONTEXT_STATE.md",
    "docs/historical/compatibility/README.md",
    "lab/README.md",
    "runtime/README.md",
)

FORBIDDEN_IMPORTS = (
    "from engine.ote",
    "import engine.ote",
    "from detectors.fib",
    "import detectors.fib",
    "from engine.rr_by_setup",
    "import engine.rr_by_setup",
)


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required path: {relative}")

    for scope in ("engine", "agents", "analysis", "orchestration", "detectors", "scripts", "tests"):
        base = ROOT / scope
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            for marker in FORBIDDEN_IMPORTS:
                if marker in text:
                    errors.append(f"forbidden retired import {marker!r}: {path.relative_to(ROOT)}")

    if (ROOT / "docs/CONTRATO_CONTEXT_STATE.md").exists():
        errors.append("normative duplicate exists: docs/CONTRATO_CONTEXT_STATE.md")
    if (ROOT / "DATA_INVENTARIO_ACTUALIZADO.md").exists():
        errors.append("historical inventory remains at repository root")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("PASS: repository architecture boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
