"""Punto de entrada obligatorio de Hermes.

Uso local recomendado:
    python start_hermes.py

El primer paso SIEMPRE es ejecutar las auditorías. Si el resultado no alcanza
el umbral, Hermes no puede avanzar a la fase del plan. Para habilitar el loop
de corrección automática, definir HERMES_FIX_COMMAND con el comando local que
invoca al agente Hermes.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    os.environ.setdefault("PYTHONPATH", str(ROOT))
    command = [sys.executable, "-m", "audits.codigo.bootstrap"]
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
